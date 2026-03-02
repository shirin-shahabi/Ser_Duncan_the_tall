from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from risk_builder.fetcher import fetch_spy_prices
from risk_builder.calculator import compute_risk
from zk_estimator.verifier import verify_risk
from risk_builder.router import router as risk_router
from zk_estimator.router import router as zk_router

load_dotenv()

APP_ROOT = Path(__file__).resolve().parent.parent
ACCESS_LOG = APP_ROOT / "data" / "pipeline_audit.jsonl"
ENABLE_PROOF = os.getenv("ENABLE_DSPERSE_PROOF", "0") == "1"

MOTTO = "Verify first. Act second. Prove always."

pipeline_total = Counter("pipeline_requests_total", "Total pipeline runs", ["status"])
pipeline_seconds = Histogram("pipeline_duration_seconds", "Pipeline end-to-end latency")
proof_total = Counter("pipeline_proof_total", "Proof runs by status", ["status"])

app = FastAPI(title="Ser Duncan the Tall")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(risk_router)
app.include_router(zk_router)

_request_seq = 0


def _next_request_id() -> str:
    global _request_seq
    _request_seq += 1
    return f"req_{_request_seq:06d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_log(entry: dict[str, Any]) -> None:
    ACCESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ACCESS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@app.post("/pipeline")
def pipeline(
    ticker: str = Query("SPY"),
    window_days: int = Query(252),
) -> dict[str, Any]:
    request_id = _next_request_id()
    ts = _utc_now_iso()
    t0 = time.perf_counter()
    stages: list[dict[str, Any]] = []

    try:
        # Stage 1: Data fetch
        s1 = time.perf_counter()
        prices, price_hash = fetch_spy_prices(ticker, window_days)
        s1_ms = (time.perf_counter() - s1) * 1000
        stages.append({
            "stage": 1,
            "agent": "risk_builder",
            "action": "yfinance_fetch",
            "description": f"Fetched {len(prices)} close prices for {ticker}",
            "duration_ms": round(s1_ms, 3),
            "output": {"n_prices": len(prices), "price_hash": price_hash},
        })

        # Stage 2: Risk computation (Agent 1)
        s2 = time.perf_counter()
        risk = compute_risk(prices)
        s2_ms = (time.perf_counter() - s2) * 1000
        stages.append({
            "stage": 2,
            "agent": "risk_builder",
            "action": "compute_risk",
            "description": f"Computed log returns, annualized vol={risk.volatility:.6f}, VaR95={risk.var_95:.6f}",
            "duration_ms": round(s2_ms, 3),
            "output": {
                "volatility": risk.volatility,
                "var_95": risk.var_95,
                "mean_return": risk.mean_return,
                "std_return": risk.std_return,
                "n_observations": risk.n_observations,
            },
        })

        # Stage 3: Independent recomputation (Agent 2 - Decimal arithmetic)
        s3 = time.perf_counter()
        verification = verify_risk(
            prices=prices,
            reported_vol=risk.volatility,
            reported_var=risk.var_95,
            enable_proof=ENABLE_PROOF,
        )
        s3_ms = (time.perf_counter() - s3) * 1000

        stages.append({
            "stage": 3,
            "agent": "zk_estimator",
            "action": "decimal_recompute",
            "description": f"Recomputed vol={verification.recomputed_vol:.6f} using Decimal-only arithmetic (no numpy)",
            "duration_ms": round(s3_ms, 3),
            "output": {
                "recomputed_vol": verification.recomputed_vol,
                "recomputed_var": verification.recomputed_var,
                "vol_deviation": verification.vol_deviation,
                "var_deviation": verification.var_deviation,
            },
        })

        # Stage 4: Cross-agent comparison
        stages.append({
            "stage": 4,
            "agent": "zk_estimator",
            "action": "cross_verify",
            "description": f"Compared Agent1 vs Agent2: vol_dev={verification.vol_deviation:.2e}, var_dev={verification.var_deviation:.2e}, match={verification.match}",
            "duration_ms": 0.0,
            "output": {"match": verification.match, "tolerance": "1e-6 relative"},
        })

        # Stage 5: ONNX inference
        stages.append({
            "stage": 5,
            "agent": "zk_estimator",
            "action": "onnx_inference",
            "description": f"Risk verifier model scored features -> score={verification.onnx_score:.6f}",
            "duration_ms": round(verification.timing_ms, 3),
            "output": {"onnx_score": verification.onnx_score, "model": "risk_verifier.onnx"},
        })

        # Stage 6: ZK proof generation
        proof_hash_display = verification.proof_hash if verification.proof_hash else hashlib.sha256(
            f"{price_hash}:{verification.recomputed_vol}:{verification.recomputed_var}:{verification.onnx_score}".encode()
        ).hexdigest()

        zk_timing_total = sum(verification.zk_timings.values()) if verification.zk_timings else 0.0
        if verification.verified:
            zk_desc = f"ZK proof generated and verified (witness={verification.zk_timings.get('witness_ms',0):.1f}ms, prove={verification.zk_timings.get('prove_ms',0):.1f}ms, verify={verification.zk_timings.get('verify_ms',0):.1f}ms)"
        elif ENABLE_PROOF and verification.details:
            zk_desc = f"ZK proof attempted: {verification.details}"
        elif not ENABLE_PROOF:
            zk_desc = "DSperse proof disabled - computed attestation hash from pipeline data"
        else:
            zk_desc = "ZK proof generation failed"

        stages.append({
            "stage": 6,
            "agent": "zk_estimator",
            "action": "zk_proof",
            "description": zk_desc,
            "duration_ms": round(zk_timing_total, 3),
            "output": {
                "proof_hash": proof_hash_display,
                "verified": verification.verified,
                "dsperse_enabled": ENABLE_PROOF,
                "zk_timings": verification.zk_timings,
            },
        })

        elapsed_ms = (time.perf_counter() - t0) * 1000
        pipeline_total.labels(status="ok").inc()
        if ENABLE_PROOF:
            proof_total.labels(status="ok" if verification.verified else "fail").inc()

        result = {
            "request_id": request_id,
            "timestamp": ts,
            "motto": MOTTO,
            "risk": {
                "asset": ticker,
                "volatility": risk.volatility,
                "var_95": risk.var_95,
                "mean_return": risk.mean_return,
                "std_return": risk.std_return,
                "n_observations": risk.n_observations,
                "price_hash": price_hash,
                "prices": prices,
            },
            "verification": {
                "match": verification.match,
                "vol_deviation": verification.vol_deviation,
                "var_deviation": verification.var_deviation,
                "recomputed_vol": verification.recomputed_vol,
                "recomputed_var": verification.recomputed_var,
                "onnx_score": verification.onnx_score,
                "proof_hash": proof_hash_display,
                "verified": verification.verified,
                "timing_ms": verification.timing_ms,
                "zk_timings": verification.zk_timings,
            },
            "stages": stages,
            "pipeline_ms": round(elapsed_ms, 3),
        }

        _write_log({
            "timestamp": ts,
            "request_id": request_id,
            "asset": ticker,
            "status": "ok",
            "volatility": risk.volatility,
            "var_95": risk.var_95,
            "match": verification.match,
            "proof_hash": proof_hash_display,
            "verified": verification.verified,
            "pipeline_ms": round(elapsed_ms, 3),
        })

        return result

    except Exception as e:
        pipeline_total.labels(status="error").inc()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        error_result = {
            "request_id": request_id,
            "timestamp": ts,
            "motto": MOTTO,
            "error": str(e),
            "stages": stages,
            "pipeline_ms": round(elapsed_ms, 3),
        }
        _write_log({
            "timestamp": ts,
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "pipeline_ms": round(elapsed_ms, 3),
        })
        return error_result


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/events")
def events(limit: int = 200) -> list[dict[str, Any]]:
    if limit < 1:
        limit = 1
    if limit > 2000:
        limit = 2000
    if not ACCESS_LOG.exists():
        return []

    lines = ACCESS_LOG.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "motto": MOTTO}


UI_DIR = APP_ROOT / "ui"
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
