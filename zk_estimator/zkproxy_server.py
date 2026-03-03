"""FastAPI HTTP wrapper around ZkProxyWorker."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from zk_estimator.zkproxy_worker import ZkProxyWorker

APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = str(APP_ROOT / "models" / "risk_verifier.onnx")

app = FastAPI(title="ZK Proxy", version="0.1.0")
worker = ZkProxyWorker()


class CompileRequest(BaseModel):
    model_path: str = Field(default=DEFAULT_MODEL)


class GuardCheckRequest(BaseModel):
    model_path: str = Field(default=DEFAULT_MODEL)
    features: list[float]


class ProveRequest(BaseModel):
    witness_path: str
    circuit_path: str


class VerifyRequest(BaseModel):
    proof_path: str
    circuit_path: str
    input_path: str
    output_path: str
    witness_path: str


@app.get("/health")
def health() -> dict:
    result = worker.handle({"method": "health", "params": {}, "id": 1})
    return result.get("result", result)


@app.post("/compile")
def compile_model(req: CompileRequest) -> dict:
    result = worker.handle({
        "method": "compile",
        "params": {"model_path": req.model_path},
        "id": 1,
    })
    return result.get("result", result)


@app.post("/guard_check")
def guard_check(req: GuardCheckRequest) -> dict:
    result = worker.handle({
        "method": "guard_check",
        "params": {"model_path": req.model_path, "features": req.features},
        "id": 1,
    })
    return result.get("result", result)


@app.post("/prove")
def prove(req: ProveRequest) -> dict:
    result = worker.handle({
        "method": "prove",
        "params": {"witness_path": req.witness_path, "circuit_path": req.circuit_path},
        "id": 1,
    })
    return result.get("result", result)


@app.post("/verify")
def verify(req: VerifyRequest) -> dict:
    result = worker.handle({
        "method": "verify",
        "params": {
            "proof_path": req.proof_path,
            "circuit_path": req.circuit_path,
            "input_path": req.input_path,
            "output_path": req.output_path,
            "witness_path": req.witness_path,
        },
        "id": 1,
    })
    return result.get("result", result)
