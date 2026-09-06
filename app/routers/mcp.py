from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.mcp.mcp_tools import (
    get_booking_context,
    query_pinecone_policy,
    calculate_fare_refund_entitlement,
    evaluate_fraud_risk
)

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Tools"])

class PolicyQueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 3

class BookingContextRequest(BaseModel):
    booking_id: str

class RefundCalculationRequest(BaseModel):
    booking_id: str

class FraudEvaluationRequest(BaseModel):
    booking_id: str


@router.post("/get-booking-context")
@router.get("/get-booking-context")
def api_get_booking_context(booking_id: str = Query(..., description="Booking ID or Idempotency Key")):
    res = get_booking_context(booking_id)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail=res.get("error"))
    return res


@router.post("/query-policy")
def api_query_policy(req: PolicyQueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Policy query string cannot be empty")
    return query_pinecone_policy(query=req.query, top_k=req.top_k or 3)


@router.post("/calculate-refund")
@router.get("/calculate-refund")
def api_calculate_refund(booking_id: str = Query(..., description="Booking ID")):
    res = calculate_fare_refund_entitlement(booking_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/evaluate-fraud")
@router.get("/evaluate-fraud")
def api_evaluate_fraud(booking_id: str = Query(..., description="Booking ID")):
    res = evaluate_fraud_risk(booking_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res
