from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx

from app.analysis.service import analyze_repository

app = FastAPI(
    title="SupplyLens API",
    description="Repository-wide JavaScript/TypeScript dependency and supply-chain risk analysis",
    version="0.2.0",
)


class AnalyzeRequest(BaseModel):
    repository_url: str = Field(min_length=1, examples=["https://github.com/owner/repo"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_repository_endpoint(request: AnalyzeRequest):
    try:
        return await analyze_repository(request.repository_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 403:
            detail = "GitHub API rate limit or access restriction encountered. Try again later."
            raise HTTPException(status_code=503, detail=detail) from exc
        if status == 404:
            raise HTTPException(status_code=404, detail="GitHub repository or required file was not found") from exc
        raise HTTPException(status_code=502, detail="GitHub API request failed") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not communicate with GitHub API") from exc


# Backward-compatible targeted endpoint. The dashboard's primary workflow uses /analyze.
@app.post("/analyze/impact")
async def analyze_impact_legacy_endpoint(request: dict):
    raise HTTPException(
        status_code=410,
        detail="This targeted endpoint is being replaced by repository-wide POST /analyze.",
    )
