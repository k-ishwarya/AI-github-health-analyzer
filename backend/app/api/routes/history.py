from fastapi import APIRouter, Depends
from app.core.security import verify_admin_access

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/history", dependencies=[Depends(verify_admin_access)])
async def get_analysis_history():
    """Protected admin endpoint to retrieve analysis logs/history."""
    return {"message": "Admin history log access granted", "history": []}
