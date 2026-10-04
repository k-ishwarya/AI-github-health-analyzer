from fastapi import APIRouter, Query, HTTPException
from app.schemas.repo import AnalyzeRequest, AnalyzeResponse
from app.services.github_service import parse_github_url, fetch_repository_data, fetch_user_repositories
from app.services.scoring_service import calculate_health_scores
from app.services.ai_service import generate_ai_insights

router = APIRouter()

async def _process_analysis(repo_url: str):
    owner, repo = parse_github_url(repo_url)
    if not repo:
        user_repos = await fetch_user_repositories(owner)
        if user_repos:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"'{owner}' is a GitHub user profile, not a repository.",
                    "is_profile": True,
                    "username": owner,
                    "repositories": [r["full_name"] for r in user_repos]
                }
            )
        raise HTTPException(
            status_code=400,
            detail=f"'{owner}' is a user profile or invalid repository. Please specify a repository: https://github.com/{owner}/<repo_name>"
        )

    repo_data = await fetch_repository_data(owner, repo)
    scores = calculate_health_scores(repo_data)
    insights = await generate_ai_insights(repo_data, scores)

    return AnalyzeResponse(
        repository=repo_data,
        scores=scores,
        insights=insights
    )

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest):
    """Analyze a GitHub repository from JSON payload."""
    return await _process_analysis(request.repo_url)

@router.get("/analyze", response_model=AnalyzeResponse)
async def analyze_repository_get(
    repo_url: str = Query(
        "https://github.com/fastapi/fastapi",
        min_length=1,
        max_length=500,
        description="GitHub URL or owner/repo"
    )
):
    """Analyze a GitHub repository via GET query param."""
    return await _process_analysis(repo_url)
