import re
from typing import Any
import httpx
import base64

GITHUB_API_URL = "https://api.github.com"

class GitHubClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url= GITHUB_API_URL,
            headers = {
                "Accept":"application/vnd.github+json",
                "X-GitHub-Api-Version":"2022-11-28",
            },
            timeout=10.0,
        )
        
    @staticmethod
    def parse_repository_url(url:str)->tuple[str,str]:
        pattern = r"^https?://github.com/([^/]+)/([^/#]+?)/?$"
        match = re.match(pattern,url.strip())

        if not match:
            raise ValueError("Invalid GitHub repository URL")

        owner,repository = match.groups()
        if repository.endswith(".git"):
            repository = repository[:-4]
        
        return owner,repository
        
    async def get_repository(self,url:str)->dict[str,Any]:
        owner,repository = self.parse_repository_url(url)
        
        response = await self.client.get(
            f"/repos/{owner}/{repository}"
        )
        
        if response.status_code == 404:
            raise ValueError("GitHub repository not found")
        response.raise_for_status()
        return response.json()
    
    async def get_latest_commit_sha(
        self,
        owner:str,
        repository:str,
        branch:str
        )->str:
        response = await self.client.get(
            f"/repos/{owner}/{repository}/commits/{branch}"
        )
        
        if response.status_code == 404:
            raise ValueError("Branch or repository not found")
        response.raise_for_status()
        
        return response.json()["sha"]
        
    async def get_repository_tree(
        self,
        owner:str,
        repository:str,
        commit_sha:str,
    ) -> list[dict[str,Any]]:
        response = await self.client.get(
            f"/repos/{owner}/{repository}/git/trees/{commit_sha}",
            params = {"recursive":"1"}
        )
        response.raise_for_status()
        data =  response.json()
        
        if data.get("truncated"):
            raise ValueError(
                "Repository tree is too large to analyze safely"
            ) 
        return data["tree"]    
    
    async def get_file_content(
        self,
        owner:str,
        repository:str,
        blob_sha:str,
    ) -> str:
        response = await self.client.get(
            f"/repos/{owner}/{repository}/git/blobs/{blob_sha}"
        )
        if response.status_code == 404:
            raise ValueError("File blob not found")
        
        response.raise_for_status()
        data = response.json()
        
        if data.get("encoding") != "base64":
            raise ValueError("Unsupported GitHub blob encoding")
        
        content = base64.b64decode(data["content"])
        return content.decode("utf-8")
    
        
    async def close(self):
        await self.client.aclose()