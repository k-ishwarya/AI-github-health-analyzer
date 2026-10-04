from fastapi import APIRouter

router = APIRouter()

@router.get("/history")
async def history_root():
    return {"message": "History endpoint placeholder"}
