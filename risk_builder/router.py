from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from risk_builder.calculator import compute_risk
from risk_builder.fetcher import fetch_spy_prices

router = APIRouter(prefix="/risk", tags=["risk_builder"])


class ComputeRequest(BaseModel):
    ticker: str = "SPY"
    window_days: int = 252


class RiskPayload(BaseModel):
    asset: str
    volatility: float
    var_95: float
    mean_return: float
    std_return: float
    timestamp: str
    prices: list[str]
    price_hash: str
    n_observations: int


@router.post("/compute", response_model=RiskPayload)
def compute(req: ComputeRequest) -> RiskPayload:
    try:
        prices, price_hash = fetch_spy_prices(req.ticker, req.window_days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {e}")

    metrics = compute_risk(prices)
    return RiskPayload(
        asset=req.ticker,
        volatility=metrics.volatility,
        var_95=metrics.var_95,
        mean_return=metrics.mean_return,
        std_return=metrics.std_return,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        prices=prices,
        price_hash=price_hash,
        n_observations=metrics.n_observations,
    )
