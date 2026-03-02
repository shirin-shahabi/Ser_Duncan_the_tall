from __future__ import annotations

import hashlib
from decimal import Decimal

import yfinance as yf


def fetch_spy_prices(ticker: str = "SPY", window_days: int = 252) -> tuple[list[str], str]:
    data = yf.download(ticker, period=f"{window_days}d", auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError(f"No price data returned for {ticker}")

    close_col = data["Close"]
    if hasattr(close_col, "squeeze"):
        close_col = close_col.squeeze()
    closes = close_col.dropna().tolist()
    if not closes:
        raise ValueError(f"No close prices for {ticker}")

    prices = [str(Decimal(str(float(p)))) for p in closes]
    price_hash = hashlib.sha256(",".join(prices).encode()).hexdigest()
    return prices, price_hash
