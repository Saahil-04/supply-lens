"""SupplyLens HTTP API: compact analysis creation and paginated result resources."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.analysis.service import analyze_repository
from app.analysis.store import AnalysisEntry, analysis_store

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SupplyLens API",
    description="Repository-wide JavaScript/TypeScript dependency and supply-chain risk analysis",
    version="0.5.0",
)


class AnalyzeRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=2048, examples=["https://github.com/owner/repo"])


def _timestamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _entry_or_404(analysis_id: str) -> AnalysisEntry:
    entry = analysis_store.get(analysis_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Analysis not found or expired; submit POST /analyze again")
    return entry


def _compact(entry: AnalysisEntry) -> dict[str, Any]:
    result = entry.result
    metadata = result.get("analysis_metadata", {})
    vulnerability_status = metadata.get("vulnerability_analysis_status", "unknown")
    inventory_status = metadata.get("status", "unknown")
    overall_status = "complete" if inventory_status == "inventory_complete" and vulnerability_status == "complete" else "partial"
    return {
        "analysis_id": entry.analysis_id,
        "status": overall_status,
        "inventory_status": inventory_status,
        "vulnerability_analysis_status": vulnerability_status,
        "created_at": _timestamp(entry.created_at),
        "expires_at": _timestamp(entry.expires_at),
        "repository": result.get("repository", {}),
        "summary": result.get("summary", {}),
        "analysis_metadata": result.get("analysis_metadata", {}),
        "links": {
            "self": f"/analyses/{entry.analysis_id}",
            "projects": f"/analyses/{entry.analysis_id}/projects",
            "packages": f"/analyses/{entry.analysis_id}/packages",
            "vulnerabilities": f"/analyses/{entry.analysis_id}/vulnerabilities",
            "recommendations": f"/analyses/{entry.analysis_id}/recommendations",
            "graph": f"/analyses/{entry.analysis_id}/graph?package_id=<package_id>",
            "sbom": f"/analyses/{entry.analysis_id}/sbom",
        },
    }


def _page(items: list[dict[str, Any]], offset: int, limit: int, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    total = len(items)
    return {
        "items": items[offset:offset + limit],
        "pagination": {"offset": offset, "limit": limit, "total": total, "has_more": offset + limit < total},
        "filters": filters or {},
    }


def _contains(item: dict[str, Any], query: str, fields: tuple[str, ...]) -> bool:
    needle = query.casefold()
    return any(needle in str(item.get(field) or "").casefold() for field in fields)


def _get_list(entry: AnalysisEntry, key: str) -> list[dict[str, Any]]:
    value = entry.result.get(key, [])
    return value if isinstance(value, list) else []


def _finding_id(item: dict[str, Any]) -> str:
    """Stable identifier for an advisory affecting a particular package instance."""
    identity = "\0".join((
        str(item.get("id") or ""),
        str(item.get("package_id") or ""),
        str(item.get("installed_version") or ""),
    ))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _compact_vulnerability(item: dict[str, Any], analysis_id: str) -> dict[str, Any]:
    """Keep the list payload small; full details and references live on the detail route."""
    return {
        "finding_id": _finding_id(item),
        "id": item.get("id"),
        "aliases": item.get("aliases", []),
        "summary": item.get("summary"),
        "severity": item.get("severity", "UNKNOWN"),
        "cvss_score": item.get("cvss_score"),
        "package_id": item.get("package_id"),
        "package_name": item.get("package_name"),
        "installed_version": item.get("installed_version"),
        "package_path": item.get("package_path"),
        "lockfile": item.get("lockfile"),
        "fixed_versions": item.get("fixed_versions", []),
        "modified": item.get("modified"),
        "published": item.get("published"),
        "links": {"detail": f"/analyses/{analysis_id}/vulnerabilities/{_finding_id(item)}"},
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/analyze", status_code=201)
async def analyze_repository_endpoint(request: AnalyzeRequest):
    """Run a scan and return a compact handle; large resources are fetched separately."""
    try:
        result = await analyze_repository(request.repository_url)
        entry = analysis_store.create(result)
        return _compact(entry)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="A GitHub or OSV API request timed out; retry the analysis") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {403, 429}:
            raise HTTPException(status_code=503, detail="GitHub or OSV API rate limit/access restriction encountered; try again later") from exc
        if status == 404:
            raise HTTPException(status_code=404, detail="GitHub repository, branch, file, or OSV advisory was not found") from exc
        if status == 401:
            raise HTTPException(status_code=502, detail="An upstream API rejected the configured credentials") from exc
        raise HTTPException(status_code=502, detail="An upstream API request failed") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not communicate with GitHub or OSV API") from exc
    except Exception as exc:
        logger.exception("Unexpected repository analysis failure")
        raise HTTPException(status_code=500, detail="Unexpected repository analysis failure; check server logs") from exc


@app.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str):
    return _compact(_entry_or_404(analysis_id))


@app.get("/analyses/{analysis_id}/projects")
async def get_projects(
    analysis_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
):
    entry = _entry_or_404(analysis_id)
    items = _get_list(entry, "projects")
    if q:
        items = [item for item in items if _contains(item, q, ("name", "path", "manifest_path", "lockfile_path"))]
    return _page(items, offset, limit, {"q": q})


@app.get("/analyses/{analysis_id}/packages")
async def get_packages(
    analysis_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
    direct: bool | None = None,
    is_dev: bool | None = None,
    lockfile: str | None = Query(None, max_length=500),
):
    entry = _entry_or_404(analysis_id)
    items = _get_list(entry, "packages")
    if q:
        items = [item for item in items if _contains(item, q, ("name", "version", "path", "id"))]
    if direct is not None:
        items = [item for item in items if bool(item.get("is_direct")) is direct]
    if is_dev is not None:
        items = [item for item in items if item.get("is_dev") is is_dev]
    if lockfile:
        items = [item for item in items if item.get("lockfile") == lockfile]
    return _page(items, offset, limit, {"q": q, "direct": direct, "is_dev": is_dev, "lockfile": lockfile})


@app.get("/analyses/{analysis_id}/vulnerabilities")
async def get_vulnerabilities(
    analysis_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
    severity: str | None = Query(None, pattern="^(CRITICAL|HIGH|MEDIUM|LOW|UNKNOWN)$"),
    package_name: str | None = Query(None, max_length=500),
    has_fix: bool | None = None,
):
    entry = _entry_or_404(analysis_id)
    items = _get_list(entry, "vulnerabilities")
    if q:
        items = [item for item in items if _contains(item, q, ("id", "summary", "package_name", "package_path", "aliases"))]
    if severity:
        items = [item for item in items if str(item.get("severity", "UNKNOWN")).upper() == severity]
    if package_name:
        items = [item for item in items if package_name.casefold() in str(item.get("package_name", "")).casefold()]
    if has_fix is not None:
        items = [item for item in items if bool(item.get("fixed_versions")) is has_fix]
    items.sort(key=lambda item: (-(float(item.get("cvss_score") or 0)), {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(str(item.get("severity", "UNKNOWN")).upper(), 4), str(item.get("package_name", "")), str(item.get("id", ""))))
    compact_items = [_compact_vulnerability(item, analysis_id) for item in items[offset:offset + limit]]
    total = len(items)
    return {
        "items": compact_items,
        "pagination": {"offset": offset, "limit": limit, "total": total, "has_more": offset + limit < total},
        "filters": {"q": q, "severity": severity, "package_name": package_name, "has_fix": has_fix},
    }


@app.get("/analyses/{analysis_id}/vulnerabilities/{finding_id}")
async def get_vulnerability_detail(analysis_id: str, finding_id: str):
    """Return the full advisory details for one specific affected package instance."""
    entry = _entry_or_404(analysis_id)
    for item in _get_list(entry, "vulnerabilities"):
        if _finding_id(item) == finding_id:
            return {"finding_id": finding_id, **item}
    raise HTTPException(status_code=404, detail="Vulnerability finding not found in this analysis")


@app.get("/analyses/{analysis_id}/recommendations")
async def get_recommendations(
    analysis_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
    has_fix: bool | None = None,
):
    entry = _entry_or_404(analysis_id)
    items = _get_list(entry, "recommendations")
    if q:
        items = [item for item in items if _contains(item, q, ("package_name", "installed_version", "recommendation", "vulnerability_ids"))]
    if has_fix is not None:
        items = [item for item in items if bool(item.get("fixed_versions")) is has_fix]
    return _page(items, offset, limit, {"q": q, "has_fix": has_fix})


@app.get("/analyses/{analysis_id}/graph")
async def get_graph_neighborhood(
    analysis_id: str,
    package_id: str,
    depth: int = Query(1, ge=0, le=3),
    direction: str = Query("both", pattern="^(in|out|both)$"),
):
    """Return a bounded neighborhood around one package ID, not the entire large graph."""
    entry = _entry_or_404(analysis_id)
    graph = entry.result.get("dependency_graph") or {}
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    node_by_id = {node.get("id"): node for node in nodes if isinstance(node, dict) and node.get("id")}
    if package_id not in node_by_id:
        raise HTTPException(status_code=404, detail="Package ID not found in this analysis")
    outgoing: dict[str, list[dict[str, Any]]] = {}
    incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        outgoing.setdefault(edge.get("source"), []).append(edge)
        incoming.setdefault(edge.get("target"), []).append(edge)
    visited = {package_id}
    frontier = {package_id}
    selected_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for _ in range(depth):
        next_frontier: set[str] = set()
        for current in frontier:
            candidates = []
            if direction in ("out", "both"):
                candidates.extend(outgoing.get(current, []))
            if direction in ("in", "both"):
                candidates.extend(incoming.get(current, []))
            for edge in candidates:
                selected_edges[(str(edge.get("source")), str(edge.get("target")), str(edge.get("dependency_type")))] = edge
                other = edge.get("target") if edge.get("source") == current else edge.get("source")
                if other in node_by_id and other not in visited:
                    visited.add(other)
                    next_frontier.add(other)
        frontier = next_frontier
    return {
        "root_package_id": package_id,
        "depth": depth,
        "direction": direction,
        "nodes": [node_by_id[node_id] for node_id in sorted(visited)],
        "edges": [selected_edges[key] for key in sorted(selected_edges)],
        "truncated": False,
    }


@app.get("/analyses/{analysis_id}/sbom")
async def download_sbom(analysis_id: str):
    entry = _entry_or_404(analysis_id)
    sbom = entry.result.get("sbom")
    if not isinstance(sbom, dict):
        raise HTTPException(status_code=404, detail="CycloneDX SBOM is not available for this analysis")
    filename = f"supplylens-{analysis_id}.cdx.json"
    return Response(
        content=json.dumps(sbom, separators=(",", ":")),
        media_type="application/vnd.cyclonedx+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Kept for compatibility with clients of the earlier prototype.
@app.post("/analyze/impact")
async def analyze_impact_legacy_endpoint(request: dict):
    raise HTTPException(status_code=410, detail="The targeted impact workflow is not available in this API version; use repository-wide POST /analyze.")
