from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext

getcontext().prec = 28


@dataclass
class RecomputedRisk:
    volatility: float
    var_95: float
    mean_return: float
    std_return: float
    n_observations: int


def recompute_risk(prices: list[str]) -> RecomputedRisk:
    decimals = [Decimal(p) for p in prices]
    if len(decimals) < 2:
        raise ValueError("Need at least 2 prices")

    log_returns: list[Decimal] = []
    for i in range(1, len(decimals)):
        ratio = decimals[i] / decimals[i - 1]
        ln_ratio = _decimal_ln(ratio)
        log_returns.append(ln_ratio)

    n = len(log_returns)
    mean_ret = sum(log_returns) / n
    variance = sum((r - mean_ret) ** 2 for r in log_returns) / (n - 1)
    std_ret = variance.sqrt()
    sqrt_252 = Decimal("252").sqrt()
    annualized_vol = std_ret * sqrt_252
    var_95 = mean_ret - Decimal("1.645") * std_ret

    return RecomputedRisk(
        volatility=float(annualized_vol),
        var_95=float(var_95),
        mean_return=float(mean_ret),
        std_return=float(std_ret),
        n_observations=n,
    )


def _decimal_ln(x: Decimal) -> Decimal:
    if x <= 0:
        raise ValueError("ln(x) requires x > 0")
    # Taylor series for ln(x) around 1: ln(1+u) = u - u^2/2 + u^3/3 - ...
    # For better convergence, reduce x to near 1 using ln(x) = ln(x/2^k) + k*ln(2)
    ln2 = Decimal("0.6931471805599453094172321214581765680755")
    k = 0
    val = x
    while val > Decimal("2"):
        val /= 2
        k += 1
    while val < Decimal("0.5"):
        val *= 2
        k -= 1

    u = val - 1
    result = Decimal(0)
    term = u
    for n in range(1, 60):
        if n % 2 == 1:
            result += term / n
        else:
            result -= term / n
        term *= u
    return result + k * ln2
