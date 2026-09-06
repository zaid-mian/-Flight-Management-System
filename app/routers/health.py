from fastapi import APIRouter, HTTPException
from app.database import check_db_health, pool_instance

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check():
    try:
        db_info = check_db_health()
        pool_status = {
            "min_connections": pool_instance.minconn if pool_instance else 0,
            "max_connections": pool_instance.maxconn if pool_instance else 0,
            "pool_active": bool(pool_instance and not pool_instance.closed)
        }
        return {
            "service": "Flight Management System FastAPI REST Engine",
            "status": "OK",
            "database": db_info,
            "pool": pool_status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database health check failed: {str(e)}")
