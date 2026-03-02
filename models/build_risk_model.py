from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
import torch
from torch import nn


class RiskVerifierNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.fc1 = nn.Linear(4, 8)
        self.fc2 = nn.Linear(8, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = torch.relu(x)
        x = self.fc2(x)
        return x


def build_model(out_path: Path) -> None:
    torch.manual_seed(42)
    model = RiskVerifierNet().eval()
    sample = torch.zeros((1, 4), dtype=torch.float32)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        sample,
        str(out_path),
        input_names=["features"],
        output_names=["output"],
        dynamic_axes={"features": {0: "batch"}, "output": {0: "batch"}},
        opset_version=13,
        do_constant_folding=True,
    )


def print_ops(path: Path) -> None:
    model = onnx.load(path)
    ops = sorted({node.op_type for node in model.graph.node})
    print("ONNX ops:", ", ".join(ops))


if __name__ == "__main__":
    output_file = Path(__file__).resolve().parent / "risk_verifier.onnx"
    build_model(output_file)
    print_ops(output_file)
    sample_vec = np.array([[0.001, 0.002, 0.5, 0.18]], dtype=np.float32)
    print("Sample feature vector shape:", sample_vec.shape)
