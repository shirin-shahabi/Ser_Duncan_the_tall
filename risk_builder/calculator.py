from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RiskMetrics:
    volatility: float
    var_95: float
    mean_return: float
    std_return: float
    n_observations: int


def compute_risk(prices: list[str]) -> RiskMetrics:
    floats = [float(p) for p in prices]
    if len(floats) < 2:
        raise ValueError("Need at least 2 prices to compute risk")

    log_returns = [math.log(floats[i] / floats[i - 1]) for i in range(1, len(floats))]
    n = len(log_returns)
    mean_ret = sum(log_returns) / n
    variance = sum((r - mean_ret) ** 2 for r in log_returns) / (n - 1)
    std_ret = math.sqrt(variance)
    annualized_vol = std_ret * math.sqrt(252)
    var_95 = mean_ret - 1.645 * std_ret

    return RiskMetrics(
        volatility=annualized_vol,
        var_95=var_95,
        mean_return=mean_ret,
        std_return=std_ret,
        n_observations=n,
    )
