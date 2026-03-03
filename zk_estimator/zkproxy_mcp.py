"""FastMCP stdio server exposing ZK proxy tools.

Two modes:
  - Local (default): instantiates ZkProxyWorker in-process.
  - Remote: if ZKPROXY_URL is set, proxies HTTP requests to the Docker container.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("zk-proxy")

ZKPROXY_URL = os.environ.get("ZKPROXY_URL", "")
APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = str(APP_ROOT / "models" / "risk_verifier.onnx")

_worker = None


def _get_worker():
    global _worker
    if _worker is None:
        from zk_estimator.zkproxy_worker import ZkProxyWorker
        _worker = ZkProxyWorker()
    return _worker


def _local_call(method: str, params: dict) -> dict:
    result = _get_worker().handle({"method": method, "params": params, "id": 1})
    return result.get("result", result.get("error", result))


def _remote_call(endpoint: str, payload: dict | None = None) -> dict:
    url = f"{ZKPROXY_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    if payload is None:
        resp = httpx.get(url, timeout=120)
    else:
        resp = httpx.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def health() -> dict:
    """Check ZK proxy health and JSTprove availability."""
    if ZKPROXY_URL:
        return _remote_call("health")
    return _local_call("health", {})


@mcp.tool()
def compile(model_path: str = DEFAULT_MODEL) -> dict:
    """Compile an ONNX model into a ZK circuit."""
    if ZKPROXY_URL:
        return _remote_call("compile", {"model_path": model_path})
    return _local_call("compile", {"model_path": model_path})


@mcp.tool()
def guard_check(features: list[float], model_path: str = DEFAULT_MODEL) -> dict:
    """Run witness generation, proving, and verification in one shot."""
    if ZKPROXY_URL:
        return _remote_call("guard_check", {"model_path": model_path, "features": features})
    return _local_call("guard_check", {"model_path": model_path, "features": features})


@mcp.tool()
def prove(witness_path: str, circuit_path: str) -> dict:
    """Generate a ZK proof from a witness and circuit."""
    if ZKPROXY_URL:
        return _remote_call("prove", {"witness_path": witness_path, "circuit_path": circuit_path})
    return _local_call("prove", {"witness_path": witness_path, "circuit_path": circuit_path})


@mcp.tool()
def verify(proof_path: str, circuit_path: str, input_path: str, output_path: str, witness_path: str) -> dict:
    """Verify a ZK proof against a circuit."""
    payload = {
        "proof_path": proof_path,
        "circuit_path": circuit_path,
        "input_path": input_path,
        "output_path": output_path,
        "witness_path": witness_path,
    }
    if ZKPROXY_URL:
        return _remote_call("verify", payload)
    return _local_call("verify", payload)


if __name__ == "__main__":
    mcp.run(transport="stdio")
