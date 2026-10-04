from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AnalyzeRequest(BaseModel):
    repo_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="GitHub repository URL or slug, e.g. 'owner/repo' or 'https://github.com/owner/repo'"
    )

class CategoryScore(BaseModel):
    score: int
    label: str
    weight: int
    days_since_last_commit: Optional[int] = None
    has_readme: Optional[bool] = None
    has_license: Optional[bool] = None
    has_contributing: Optional[bool] = None
    has_code_of_conduct: Optional[bool] = None
    open_issues: Optional[int] = None
    closed_issues: Optional[int] = None
    merged_ratio: Optional[float] = None

class HealthScores(BaseModel):
    overall_score: int
    grade: str
    status: str
    status_color: str
    categories: Dict[str, Any]

class Recommendation(BaseModel):
    priority: str
    title: str
    description: str

class AIInsights(BaseModel):
    summary: str
    strengths: List[str]
    risks: List[str]
    recommendations: List[Recommendation]
    ai_powered: bool = False

class AnalyzeResponse(BaseModel):
    repository: Dict[str, Any]
    scores: HealthScores
    insights: AIInsights
