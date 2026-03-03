# ZK Proxy

Zero-knowledge proof generation and verification for ONNX risk models via DSperse/JSTprove.

## MCP Tools

The `zk-proxy` MCP server exposes five tools over stdio transport:

| Tool | Parameters | Description |
|---|---|---|
| `health` | none | Returns JSTprove availability and cached circuit list |
| `compile` | `model_path` (optional, defaults to `models/risk_verifier.onnx`) | Compiles an ONNX model into a ZK circuit |
| `guard_check` | `features: list[float]`, `model_path` (optional) | End-to-end: witness generation, proving, and verification |
| `prove` | `witness_path`, `circuit_path` | Generates a ZK proof from witness and circuit files |
| `verify` | `proof_path`, `circuit_path`, `input_path`, `output_path`, `witness_path` | Verifies a ZK proof |

## Modes

**Local** (default) — instantiates `ZkProxyWorker` in-process. Requires `dsperse` installed locally.

**Remote** — set `ZKPROXY_URL=http://localhost:8100` to proxy requests to the Docker container instead.

## Typical Workflow

```
compile → guard_check → (proof is generated and verified automatically)
```

1. `compile` the ONNX model into a circuit (one-time, cached by content hash)
2. `guard_check` with feature vector to get risk score + ZK proof + verification in one call
3. Use `prove`/`verify` individually for fine-grained control

## Running

**MCP server (stdio):**
```sh
uv run python -m zk_estimator.zkproxy_mcp
```

**Docker container (HTTP on port 8100):**
```sh
docker compose up zkproxy
curl http://localhost:8100/health
```
