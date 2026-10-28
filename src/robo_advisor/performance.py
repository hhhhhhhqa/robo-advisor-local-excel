"""Incremental daily portfolio and ETF performance metrics."""

from __future__ import annotations

from math import sqrt


class Performance:
    def __init__(self, annual_risk_free: float):
        self.annual_risk_free = annual_risk_free
        self.base: float | None = None
        self.previous: float | None = None
        self.peak = 0.0
        self.max_drawdown = 0.0
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0

    def add(self, value: float) -> dict[str, float | None]:
        if value <= 0:
            raise ValueError("Daily asset value must be positive")
        if self.base is None:
            self.base = value
        if self.previous is not None:
            daily = value / self.previous - 1
            self.count += 1
            delta = daily - self.mean
            self.mean += delta / self.count
            self.m2 += delta * (daily - self.mean)
        self.previous = value
        self.peak = max(self.peak, value)
        drawdown = value / self.peak - 1
        self.max_drawdown = min(self.max_drawdown, drawdown)
        variance = self.m2 / (self.count - 1) if self.count >= 2 else 0.0
        sharpe = sqrt(252) * (self.mean - self.annual_risk_free / 252) / sqrt(variance) if variance > 0 else None
        return {"return": value / self.base - 1, "sharpe": sharpe,
                "max_drawdown": self.max_drawdown, "drawdown": drawdown}
