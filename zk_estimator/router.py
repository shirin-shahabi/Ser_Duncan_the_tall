from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from zk_estimator.verifier import verify_risk

router = APIRouter(prefix="/risk", tags=["zk_estimator"])


class VerifyRequest(BaseModel):
    prices: list[str]
    reported_vol: float
    reported_var: float
    enable_proof: bool = False


class VerifyResponse(BaseModel):
    match: bool
    vol_deviation: float
    var_deviation: float
    recomputed_vol: float
    recomputed_var: float
    onnx_score: float
    proof_hash: str
    verified: bool
    timing_ms: float
    details: str


@router.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest) -> VerifyResponse:
    result = verify_risk(
        prices=req.prices,
        reported_vol=req.reported_vol,
        reported_var=req.reported_var,
        enable_proof=req.enable_proof,
    )
    return VerifyResponse(
        match=result.match,
        vol_deviation=result.vol_deviation,
        var_deviation=result.var_deviation,
        recomputed_vol=result.recomputed_vol,
        recomputed_var=result.recomputed_var,
        onnx_score=result.onnx_score,
        proof_hash=result.proof_hash,
        verified=result.verified,
        timing_ms=result.timing_ms,
        details=result.details,
    )
