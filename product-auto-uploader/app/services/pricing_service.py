from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class PricingService:
    def __init__(self, pricing_path: Path):
        self._config: Dict[str, Any] = json.loads(pricing_path.read_text(encoding="utf-8"))

    def calculate(self, site: str, cost: int) -> int:
        cfg = self._config.get(site, {})
        base = cost + int(cfg.get("margin", 0))

        if "tier1_divisor" in cfg:
            return self._calc_tiered(base, cfg)
        return self._calc_rate(base, cfg)

    def _calc_rate(self, base: int, cfg: Dict[str, Any]) -> int:
        if base <= 0:
            return 0
        fee_rate = float(cfg["fee_rate"])
        rounding = int(cfg.get("rounding", -3))
        # base / (1 - fee_rate/100) — 수수료 떼고 base가 남도록 역산
        return int(round(base * 100 / (100 - fee_rate), rounding))

    def _calc_tiered(self, base: int, cfg: Dict[str, Any]) -> int:
        threshold = int(cfg["tier_threshold"])
        d1 = float(cfg["tier1_divisor"])  # 1000 * (1 - tier1_fee_rate)
        d2 = float(cfg["tier2_divisor"])  # 1000 * (1 - tier2_fee_rate)
        rounding = int(cfg.get("rounding", -4))
        deduction = int(cfg.get("fixed_deduction", 0))

        # 필웨이 구간별 공식: base * 1000 / divisor == base / (divisor/1000)
        if base <= threshold:
            raw = round(base * 1000 / d1, rounding)
        else:
            raw = round(threshold * 1000 / d1, rounding) + round((base - threshold) * 1000 / d2, rounding)
        return int(raw) - deduction
