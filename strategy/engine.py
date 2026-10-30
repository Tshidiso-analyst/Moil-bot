from __future__ import annotations

from typing import Callable

import pandas as pd

from analysis.market_structure import analyse_structure
from analysis.smc_patterns import analyze_market_context
from analysis.top_down import TopDownAnalyzer
from strategy.models import SourcePassage, StrategyDecision


VALID_DIRECTIONS = {"bullish", "bearish", "neutral"}


class StrategyEngine:
    """
    Explainable candidate evaluator.

    This component does not submit orders. Retrieved source passages are
    references for review, not proof that a strategy rule is valid.
    Source-specific entry/exit rules must be encoded and backtested before
    the strategy can become execution-ready.
    """

    def __init__(
        self,
        source_search: Callable | None = None,
    ):
        self.source_search = source_search

    def evaluate(
        self,
        symbol: str,
        datasets: dict[str, pd.DataFrame],
        fundamental_bias: str = "neutral",
        execution_timeframe: str | None = None,
    ) -> StrategyDecision:
        symbol = str(symbol).strip().upper()
        if not symbol:
            raise ValueError("Symbol must not be empty.")

        if not datasets:
            raise ValueError("At least one timeframe dataset is required.")

        fundamental_bias = str(fundamental_bias).strip().lower()
        if fundamental_bias not in VALID_DIRECTIONS:
            raise ValueError("fundamental_bias must be bullish, bearish or neutral.")

        required = {"open", "high", "low", "close"}
        for timeframe, dataframe in datasets.items():
            if not isinstance(dataframe, pd.DataFrame):
                raise ValueError(f"Dataset for {timeframe} must be a pandas DataFrame.")
            if dataframe.empty:
                raise ValueError(f"Dataset for {timeframe} is empty.")
            missing = required - set(dataframe.columns)
            if missing:
                raise ValueError(
                    f"Dataset for {timeframe} is missing columns: {sorted(missing)}"
                )

        if execution_timeframe is None:
            execution_timeframe = list(datasets)[-1]
        if execution_timeframe not in datasets:
            raise ValueError(f"Unknown execution timeframe: {execution_timeframe}")

        top_down = TopDownAnalyzer().analyse(datasets)
        alignment = str(top_down.alignment).lower()
        trends = {str(item.timeframe): str(item.trend).lower() for item in top_down.analyses}

        direction = alignment if alignment in {"bullish", "bearish"} else "neutral"
        reasons = []
        score = sum(1 for trend in trends.values() if direction != "neutral" and trend == direction)

        for timeframe, trend in trends.items():
            reasons.append(f"{timeframe} market structure: {trend}.")

        if direction == "neutral":
            reasons.append("No clear directional top-down alignment; a directional candidate is not justified.")
        else:
            reasons.append(f"Top-down alignment is {direction}.")

        dataframe = datasets[execution_timeframe]
        market_context = analyze_market_context(dataframe, execution_timeframe)

        session_reason = (
            "Session is active and valid for directional execution."
            if market_context.session in {"london", "new_york", "london_new_york_overlap"}
            else "Session is off the active kill-zone window; trade is not preferred."
        )
        reasons.append(session_reason)
        reasons.extend(market_context.reasons)

        if market_context.distribution and direction == "bullish":
            reasons.append("Distribution is active; waiting for deeper confirmation is required before long entries.")
        if market_context.distribution and direction == "bearish":
            reasons.append("Distribution is active; waiting for deeper confirmation is required before short entries.")
        if market_context.consolidation:
            reasons.append("Consolidation indicates the market is building energy, so only a confirmed breakout or sweep candidate should be traded.")

        gap_direction = None
        if market_context.fair_value_gaps:
            gap_direction = market_context.fair_value_gaps[-1].direction
            if gap_direction == direction:
                score += 2
                reasons.append(
                    f"Latest fair value gap confirms {direction} intent on {execution_timeframe}."
                )
            else:
                reasons.append(
                    "The latest fair value gap disagrees with the top-down direction; wait for confirmation."
                )
        else:
            reasons.append(f"No fair value gap was detected on {execution_timeframe}.")

        if market_context.liquidity:
            latest_sweep = market_context.liquidity[-1]
            reasons.append(
                f"Latest liquidity sweep is {latest_sweep.direction} at {latest_sweep.level:.5f}, which matters for entry context."
            )

        if market_context.premium_discount != "neutral":
            reasons.append(
                f"Current premium/discount state is {market_context.premium_discount}; entries should be aligned to this zone."
            )

        conflict = (
            direction != "neutral"
            and fundamental_bias in {"bullish", "bearish"}
            and fundamental_bias != direction
        )

        if conflict:
            reasons.append(
                f"Fundamental bias ({fundamental_bias}) conflicts with technical direction ({direction})."
            )
        elif fundamental_bias == direction and direction != "neutral":
            score += 1
            reasons.append("Supplied fundamental bias agrees with technical direction.")
        else:
            reasons.append("Fundamental bias is neutral or there is no directional technical setup; fundamental confirmation is absent.")

        if market_context.distribution and direction != "neutral":
            direction = "neutral"
            reasons.append("Distribution status makes the setup invalid until a clean confirmation arrives.")

        technical_candidate = (
            direction in {"bullish", "bearish"}
            and gap_direction == direction
            and not conflict
            and market_context.session in {"london", "new_york", "london_new_york_overlap"}
        )

        passages = ()
        if direction != "neutral":
            passages = tuple(self._find_sources(direction))

        source_types = {item.source_type for item in passages}
        has_pdf_and_video = {"pdf", "video"}.issubset(source_types)

        if not technical_candidate:
            status = "rejected"
            rule_status = "not_qualified"
            reasons.append("The current evidence does not meet the candidate criteria.")
        elif not has_pdf_and_video:
            status = "needs_source_evidence"
            rule_status = "incomplete_source_coverage"
            reasons.append(
                "Both PDF and video source passages are required for this research candidate. Retrieved passages must still be reviewed."
            )
        else:
            status = "research_candidate"
            rule_status = "source_passages_found_rules_unvalidated"
            reasons.append(
                "PDF and video passages were retrieved for review. Their presence does not establish that the rule is profitable."
            )

        reasons.append(
            "Not ready for backtesting or execution: source-specific entry, invalidation, stop-loss and exit rules have not yet been registered and validated by this engine."
        )

        return StrategyDecision(
            symbol=symbol,
            status=status,
            direction=direction,
            score=score,
            timeframe_trends=trends,
            top_down_alignment=alignment,
            fair_value_gap={
                "index": market_context.fair_value_gaps[-1].index,
                "direction": market_context.fair_value_gaps[-1].direction,
                "lower": market_context.fair_value_gaps[-1].lower,
                "upper": market_context.fair_value_gaps[-1].upper,
            } if market_context.fair_value_gaps else None,
            fundamental_bias=fundamental_bias,
            reasons=tuple(reasons),
            source_passages=passages,
            source_rule_status=rule_status,
            backtest_ready=False,
            execution_ready=False,
        )

    def _find_sources(self, direction: str) -> list[SourcePassage]:
        search = self.source_search

        if search is None:
            try:
                from knowledge.unified_search import search_all_knowledge
                search = search_all_knowledge
            except ImportError:
                return []

        queries = [
            f"{direction} fair value gap",
            f"{direction} market structure",
            "risk management stop loss take profit",
            "liquidity sweep confirmation",
            "smart money liquidity and session",
        ]

        found = []
        seen = set()

        for query in queries:
            try:
                results = search(query, limit=4) or []
            except Exception:
                continue

            for result in results:
                if not isinstance(result, dict):
                    continue

                source_type = str(result.get("source_type") or result.get("type") or "").strip().lower()
                if source_type not in {"pdf", "video"}:
                    continue

                title = str(result.get("title") or result.get("source") or "")
                page = result.get("page")
                video_id = str(result.get("video_id") or "")
                url = str(result.get("url") or "")

                if source_type == "pdf":
                    locator = f"page {page}" if page is not None else "PDF page unknown"
                else:
                    locator = f"video ID {video_id}" if video_id else (url or "video ID unknown")

                key = (source_type, title, locator)
                if key in seen:
                    continue
                seen.add(key)

                try:
                    source_score = float(result.get("score") or 0.0)
                except (TypeError, ValueError):
                    source_score = 0.0

                found.append(
                    SourcePassage(
                        source_type=source_type,
                        title=title or "Untitled source",
                        locator=locator,
                        snippet=str(result.get("snippet") or "")[:1000],
                        score=source_score,
                        url=url,
                    )
                )

        return found[:8]
