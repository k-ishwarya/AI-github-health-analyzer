from fastapi import APIRouter, Depends
from app.core.security import verify_admin_access

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/repository", dependencies=[Depends(verify_admin_access)])
async def repository_root():
    """Protected admin endpoint to inspect internal repository cache and metrics."""
    return {"message": "Admin repository management access granted"}
