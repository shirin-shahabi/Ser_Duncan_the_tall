FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system --no-build-isolation fastapi 'uvicorn[standard]' yfinance numpy onnxruntime onnx prometheus-client pydantic python-dotenv pyyaml

COPY gateway/ gateway/
COPY risk_builder/ risk_builder/
COPY zk_estimator/ zk_estimator/
COPY models/ models/
COPY ui/ ui/
COPY .env.example .env

EXPOSE 3000

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "3000"]
