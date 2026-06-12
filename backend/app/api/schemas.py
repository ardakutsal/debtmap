from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    repo_url: HttpUrl
    branch: str = Field(default="main", max_length=200)
    github_token: Optional[str] = Field(default=None, max_length=200)
    # Skip the recent-scan reuse cache and force a fresh run.
    force: bool = False


class AnalyzeResponse(BaseModel):
    analysis_id: str
    status: str
    status_url: str


class AnalysisStatus(BaseModel):
    analysis_id: str
    status: str
    progress_pct: int
    current_step: str


class AnalysisResult(BaseModel):
    analysis_id: str
    status: str
    owner: str
    repo: str
    branch: str
    debt_score: float
    grade: str
    # % of sampled commits carrying AI-agent signatures (git metadata evidence)
    ai_generated_pct: float
    provenance: Optional[dict] = None
    files_analyzed: int
    elapsed_seconds: float
    analyzers: dict
    file_summary: list[dict]
    action_plan: list[dict]
