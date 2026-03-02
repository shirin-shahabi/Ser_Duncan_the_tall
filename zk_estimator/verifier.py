from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import onnxruntime as ort

from zk_estimator.recompute import recompute_risk
from zk_estimator.zkproxy import get_zkproxy_client

log = logging.getLogger(__name__)

APP_ROOT = Path(__file__).resolve().parent.parent
ONNX_MODEL_PATH = APP_ROOT / "models" / "risk_verifier.onnx"

RELATIVE_TOLERANCE = 1e-6


@dataclass
class VerificationResult:
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
    zk_timings: dict[str, float] = field(default_factory=dict)


def verify_risk(
    prices: list[str],
    reported_vol: float,
    reported_var: float,
    enable_proof: bool = False,
) -> VerificationResult:
    t0 = time.perf_counter()

    recomputed = recompute_risk(prices)

    vol_dev = abs(recomputed.volatility - reported_vol) / max(abs(reported_vol), 1e-12)
    var_dev = abs(recomputed.var_95 - reported_var) / max(abs(reported_var), 1e-12)
    match = vol_dev < RELATIVE_TOLERANCE and var_dev < RELATIVE_TOLERANCE

    price_count_norm = min(recomputed.n_observations, 500) / 500.0
    vol_norm = min(recomputed.volatility, 1.0)
    features = [float(vol_dev), float(var_dev), price_count_norm, vol_norm]

    features_np = np.array([features], dtype=np.float32)
    onnx_score = 0.0
    if ONNX_MODEL_PATH.exists():
        session = ort.InferenceSession(str(ONNX_MODEL_PATH), providers=["CPUExecutionProvider"])
        onnx_score = float(session.run(["output"], {"features": features_np})[0].reshape(-1)[0])

    proof_hash = ""
    verified = False
    details = ""
    zk_timings: dict[str, float] = {}

    if enable_proof and ONNX_MODEL_PATH.exists():
        try:
            client = get_zkproxy_client()
            zk_result = client.guard_check(str(ONNX_MODEL_PATH), features)
            proof_hash = zk_result.proof_hash
            verified = zk_result.verified
            zk_timings = zk_result.timings
            if zk_result.error:
                details = zk_result.error
            else:
                details = f"zkproxy: score={zk_result.score:.6f}, verified={verified}"
        except Exception as e:
            log.warning("zkproxy proof failed: %s", e)
            details = f"zkproxy error: {e}"

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return VerificationResult(
        match=match,
        vol_deviation=vol_dev,
        var_deviation=var_dev,
        recomputed_vol=recomputed.volatility,
        recomputed_var=recomputed.var_95,
        onnx_score=onnx_score,
        proof_hash=proof_hash,
        verified=verified,
        timing_ms=round(elapsed_ms, 3),
        details=details,
        zk_timings=zk_timings,
    )
