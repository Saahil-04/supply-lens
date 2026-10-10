import logging

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.analysis.service import analyze_repository

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SupplyLens API",
    description="Repository-wide JavaScript/TypeScript dependency and supply-chain risk analysis",
    version="0.3.0",
)


class AnalyzeRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=2048, examples=["https://github.com/owner/repo"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_repository_endpoint(request: AnalyzeRequest):
    try:
        return await analyze_repository(request.repository_url)
    except ValueError as exc:
        # Invalid URL, unsupported oversized tree, or no supported manifests.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="A GitHub API request timed out; retry the analysis") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {403, 429}:
            raise HTTPException(status_code=503, detail="GitHub API rate limit or access restriction encountered; try again later") from exc
        if status == 404:
            raise HTTPException(status_code=404, detail="GitHub repository, branch, or required file was not found") from exc
        if status in {401}:
            raise HTTPException(status_code=502, detail="GitHub rejected the configured credentials") from exc
        raise HTTPException(status_code=502, detail="GitHub API request failed") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not communicate with GitHub API") from exc
    except Exception as exc:
        logger.exception("Unexpected repository analysis failure")
        raise HTTPException(status_code=500, detail="Unexpected repository analysis failure; check server logs") from exc


# Kept for compatibility with clients of the earlier prototype. The primary workflow is /analyze.
@app.post("/analyze/impact")
async def analyze_impact_legacy_endpoint(request: dict):
    raise HTTPException(
        status_code=410,
        detail="The targeted impact workflow is not available in this API version; use repository-wide POST /analyze.",
    )
