$target = "qualification/ict_rules.py"

if (Test-Path $target) {
    throw "STOP: $target already exists. Nothing was changed."
}

@'
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


VALID_DIRECTIONS = {"bullish", "bearish"}
VALID_SWEEPS = {"buy_side", "sell_side"}
VALID_STRUCTURE_SHIFTS = {"BOS", "CHoCH"}


@dataclass(frozen=True)
class ICTSetupEvidence:
    symbol: str
    direction: str

    daily_trend: str
    h4_trend: str
    h1_trend: str

    liquidity_sweep: str
    order_block_confirmed: bool
    order_block_direction: str

    displacement_confirmed: bool
    structure_shift: str
    structure_shift_direction: str

    fvg_confirmed: bool
    fvg_direction: str

    dealing_range_location: str
    entry_confirmation_15m: bool
    entry_confirmation_direction: str

    h4_objective_confirmed: bool
    h4_objective_direction: str

    fundamental_bias: str
    high_impact_news_clear: bool

    entry: float
    stop_loss: float
    take_profit: float


@dataclass(frozen=True)
class ICTQualificationResult:
    qualified: bool
    direction: str
    risk_reward: float | None
    checks: dict
    failed_checks: list[str]
    reasons: list[str]
    status: str
    execution_enabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class ICTSetupQualifier:
    """
    Strict ICT research qualification gate.

    This class evaluates supplied evidence. It does not detect patterns
    from candles, approve a strategy rule, or place trading orders.
    """

    def __init__(self, minimum_risk_reward: float = 2.0):
        try:
            minimum_risk_reward = float(minimum_risk_reward)
        except (TypeError, ValueError) as exc:
            raise ValueError("minimum_risk_reward must be numeric.") from exc

        if (
            not math.isfinite(minimum_risk_reward)
            or minimum_risk_reward <= 0
        ):
            raise ValueError(
                "minimum_risk_reward must be finite and greater than zero."
            )

        self.minimum_risk_reward = minimum_risk_reward

    @staticmethod
    def _direction(value: str, field: str) -> str:
        if value not in {"bullish", "bearish", "neutral"}:
            raise ValueError(
                f"{field} must be bullish, bearish, or neutral."
            )
        return value

    @staticmethod
    def _positive_price(value: float, field: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be numeric.") from exc

        if not math.isfinite(number) or number <= 0:
            raise ValueError(
                f"{field} must be finite and greater than zero."
            )
        return number

    def qualify(self, evidence: ICTSetupEvidence) -> ICTQualificationResult:
        if not isinstance(evidence, ICTSetupEvidence):
            raise TypeError("evidence must be an ICTSetupEvidence instance.")

        if not isinstance(evidence.symbol, str) or not evidence.symbol.strip():
            raise ValueError("symbol must be a non-empty string.")

        direction = evidence.direction
        if direction not in VALID_DIRECTIONS:
            raise ValueError("direction must be bullish or bearish.")

        daily = self._direction(evidence.daily_trend, "daily_trend")
        h4 = self._direction(evidence.h4_trend, "h4_trend")
        h1 = self._direction(evidence.h1_trend, "h1_trend")
        ob_direction = self._direction(
            evidence.order_block_direction,
            "order_block_direction",
        )
        shift_direction = self._direction(
            evidence.structure_shift_direction,
            "structure_shift_direction",
        )
        fvg_direction = self._direction(
            evidence.fvg_direction,
            "fvg_direction",
        )
        entry_direction = self._direction(
            evidence.entry_confirmation_direction,
            "entry_confirmation_direction",
        )
        objective_direction = self._direction(
            evidence.h4_objective_direction,
            "h4_objective_direction",
        )
        fundamental = self._direction(
            evidence.fundamental_bias,
            "fundamental_bias",
        )

        if evidence.liquidity_sweep not in VALID_SWEEPS:
            raise ValueError(
                "liquidity_sweep must be buy_side or sell_side."
            )

        if evidence.structure_shift not in VALID_STRUCTURE_SHIFTS:
            raise ValueError("structure_shift must be BOS or CHoCH.")

        if evidence.dealing_range_location not in {"premium", "discount"}:
            raise ValueError(
                "dealing_range_location must be premium or discount."
            )

        boolean_fields = (
            "order_block_confirmed",
            "displacement_confirmed",
            "fvg_confirmed",
            "entry_confirmation_15m",
            "h4_objective_confirmed",
            "high_impact_news_clear",
        )

        for field in boolean_fields:
            if not isinstance(getattr(evidence, field), bool):
                raise ValueError(f"{field} must be a boolean.")

        entry = self._positive_price(evidence.entry, "entry")
        stop = self._positive_price(evidence.stop_loss, "stop_loss")
        target = self._positive_price(evidence.take_profit, "take_profit")

        if direction == "bullish":
            if not stop < entry < target:
                raise ValueError(
                    "Bullish prices must satisfy stop_loss < entry < take_profit."
                )
            expected_sweep = "sell_side"
            expected_location = "discount"
        else:
            if not target < entry < stop:
                raise ValueError(
                    "Bearish prices must satisfy take_profit < entry < stop_loss."
                )
            expected_sweep = "buy_side"
            expected_location = "premium"

        risk = abs(entry - stop)
        reward = abs(target - entry)
        risk_reward = reward / risk

        checks = {
            "daily_trend_aligned": daily == direction,
            "h4_trend_aligned": h4 == direction,
            "h1_trend_aligned": h1 == direction,
            "correct_liquidity_sweep": (
                evidence.liquidity_sweep == expected_sweep
            ),
            "order_block_confirmed": (
                evidence.order_block_confirmed
                and ob_direction == direction
            ),
            "displacement_confirmed": evidence.displacement_confirmed,
            "structure_shift_confirmed": shift_direction == direction,
            "fvg_confirmed": (
                evidence.fvg_confirmed
                and fvg_direction == direction
            ),
            "correct_premium_discount": (
                evidence.dealing_range_location == expected_location
            ),
            "15m_entry_confirmed": (
                evidence.entry_confirmation_15m
                and entry_direction == direction
            ),
            "h4_objective_confirmed": (
                evidence.h4_objective_confirmed
                and objective_direction == direction
            ),
            "fundamentals_not_conflicting": (
                fundamental in {direction, "neutral"}
            ),
            "high_impact_news_clear": evidence.high_impact_news_clear,
            "minimum_risk_reward_met": (
                risk_reward >= self.minimum_risk_reward
            ),
        }

        failed_checks = [
            name for name, passed in checks.items() if not passed
        ]

        reasons = [
            f"{name.replace('_', ' ').capitalize()}: "
            f"{'passed' if passed else 'failed'}."
            for name, passed in checks.items()
        ]

        qualified = not failed_checks

        return ICTQualificationResult(
            qualified=qualified,
            direction=direction,
            risk_reward=risk_reward,
            checks=checks,
            failed_checks=failed_checks,
            reasons=reasons,
            status="research_qualified" if qualified else "rejected",
            execution_enabled=False,
        )
'@ | Set-Content -Path $target -Encoding UTF8

Write-Host "Created $target" -ForegroundColor Green