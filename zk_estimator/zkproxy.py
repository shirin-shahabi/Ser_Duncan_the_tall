from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

APP_ROOT = Path(__file__).resolve().parent.parent
WORKER_SCRIPT = APP_ROOT / "zk_estimator" / "zkproxy_worker.py"


@dataclass
class ZkProxyResult:
    success: bool
    score: float
    proof_hash: str
    verified: bool
    timings: dict[str, float] = field(default_factory=dict)
    error: str = ""


class ZkProxyClient:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._req_id = 0
        self._compiled = False

    def _ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        log.info("Starting zkproxy worker subprocess")
        self._proc = subprocess.Popen(
            ["python3", str(WORKER_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        startup = self._proc.stdout.readline().strip()
        if startup:
            parsed = json.loads(startup)
            log.info("zkproxy worker started: %s", parsed)
        self._compiled = False

    def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self._ensure_started()
            self._req_id += 1
            request = {"jsonrpc": "2.0", "id": self._req_id, "method": method, "params": params or {}}
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline().strip()
            if not line:
                return {"error": {"code": -32000, "message": "No response from worker"}}
            return json.loads(line)

    def compile(self, model_path: str) -> dict[str, Any]:
        resp = self._call("compile", {"model_path": model_path})
        if "result" in resp and resp["result"].get("success"):
            self._compiled = True
        return resp

    def guard_check(self, model_path: str, features: list[float]) -> ZkProxyResult:
        if not self._compiled:
            compile_resp = self.compile(model_path)
            if "error" in compile_resp:
                return ZkProxyResult(
                    success=False, score=0.0, proof_hash="", verified=False,
                    error=str(compile_resp["error"]),
                )

        resp = self._call("guard_check", {"model_path": model_path, "features": features})
        if "error" in resp:
            return ZkProxyResult(
                success=False, score=0.0, proof_hash="", verified=False,
                error=resp["error"].get("message", str(resp["error"])),
            )

        r = resp.get("result", {})
        return ZkProxyResult(
            success=r.get("success", False),
            score=r.get("score", 0.0),
            proof_hash=r.get("proof_hash", ""),
            verified=r.get("verified", False),
            timings=r.get("timings", {}),
            error=r.get("error", "") or r.get("note", ""),
        )

    def health(self) -> dict[str, Any]:
        resp = self._call("health")
        return resp.get("result", resp)

    def shutdown(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=5)
            self._proc = None


_client: ZkProxyClient | None = None


def get_zkproxy_client() -> ZkProxyClient:
    global _client
    if _client is None:
        _client = ZkProxyClient()
    return _client
