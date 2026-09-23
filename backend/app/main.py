from fastapi import FastAPI
from pydantic import BaseModel
from app.analysis.service import analyze_repository_impact

app = FastAPI(
    title = "Supply-Lens API",
    description = "Software Supply Chain risk analyzer",
    version="0.1.0",
)

class ImpactRequest(BaseModel):
    repository_url:str
    target:str

@app.get("/health")
async def health_check():
    return {"status":"ok"}

@app.post("/analyze/impact")
async def analyze_impact_endpoint(
    request:ImpactRequest,
    ):
    return await analyze_repository_impact(
        repository_url=request.repository_url,
        target=request.target
    )