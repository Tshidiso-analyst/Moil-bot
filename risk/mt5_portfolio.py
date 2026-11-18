"""Fail-closed MT5 portfolio snapshot for execution risk checks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
import math
from typing import Any
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


class PortfolioSnapshotError(RuntimeError):
    """Raised when live portfolio state cannot be verified safely."""


@dataclass(frozen=True)
class MT5PortfolioSnapshot:
    as_of_utc: datetime
    ny_trade_date: str
    daily_entries: int
    open_positions: int
    exposure_percent: float
    daily_loss_percent: float
    daily_net_pnl: float
    balance: float


def _number(value: Any, label: str, *, allow_zero: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise PortfolioSnapshotError(f"Invalid {label} in MT5 response.") from None
    if not math.isfinite(number) or (number < 0 if allow_zero else number <= 0):
        raise PortfolioSnapshotError(f"Invalid {label} in MT5 response.")
    return number


def _signed_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise PortfolioSnapshotError(f"Invalid {label} in MT5 response.") from None
    if not math.isfinite(number):
        raise PortfolioSnapshotError(f"Invalid {label} in MT5 response.")
    return number


def build_mt5_portfolio_snapshot(
    mt5: Any,
    *,
    magic: int,
    now: datetime | None = None,
) -> MT5PortfolioSnapshot:
    """Read account-wide positions/P&L and this NY-day's Moil-bot entries.

    Entry count is filtered by the bot magic number but spans every broker
    symbol. Open positions and daily loss/exposure are account-wide.
    """
    if mt5 is None:
        raise PortfolioSnapshotError("MT5 module is unavailable.")
    if isinstance(magic, bool) or not isinstance(magic, int):
        raise ValueError("magic must be an integer.")

    as_of = now or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("now must be timezone-aware.")
    as_of = as_of.astimezone(timezone.utc)
    local_now = as_of.astimezone(NEW_YORK)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=NEW_YORK)
    start_utc = local_start.astimezone(timezone.utc)

    try:
        account = mt5.account_info()
        if account is None:
            raise PortfolioSnapshotError(f"MT5 account information unavailable: {mt5.last_error()}")
        balance = _number(getattr(account, "balance", None), "account balance")

        positions = mt5.positions_get()
        if positions is None:
            raise PortfolioSnapshotError(f"MT5 open positions unavailable: {mt5.last_error()}")
        deals = mt5.history_deals_get(start_utc, as_of)
        if deals is None:
            raise PortfolioSnapshotError(f"MT5 deal history unavailable: {mt5.last_error()}")

        deal_entry_in = getattr(mt5, "DEAL_ENTRY_IN", None)
        if deal_entry_in is None:
            raise PortfolioSnapshotError("MT5 deal-entry constants are unavailable.")
        entry_codes = {deal_entry_in}
        inout_code = getattr(mt5, "DEAL_ENTRY_INOUT", None)
        if inout_code is not None:
            entry_codes.add(inout_code)
        out_codes = {
            value for value in (
                getattr(mt5, "DEAL_ENTRY_OUT", None),
                getattr(mt5, "DEAL_ENTRY_OUT_BY", None),
            ) if value is not None
        }
        if not out_codes:
            raise PortfolioSnapshotError("MT5 deal-exit constants are unavailable; daily P&L cannot be verified safely.")
        todays_position_ids = {
            int(getattr(deal, "position_id", 0) or 0)
            for deal in deals
            if getattr(deal, "entry", None) in entry_codes
            and int(getattr(deal, "position_id", 0) or 0) > 0
        }
        for deal in deals:
            if getattr(deal, "entry", None) in out_codes:
                position_id = int(getattr(deal, "position_id", 0) or 0)
                if position_id <= 0 or position_id not in todays_position_ids:
                    raise PortfolioSnapshotError(
                        "A position opened before the New York trading day was closed today; starting equity cannot be reconstructed safely."
                    )
        entry_order_ids: set[int] = set()
        for deal in deals:
            if int(getattr(deal, "magic", -1)) != magic or getattr(deal, "entry", None) not in entry_codes:
                continue
            order_id = getattr(deal, "order", None)
            if order_id is None or int(order_id) <= 0:
                raise PortfolioSnapshotError("MT5 entry deal has no verifiable order ID.")
            entry_order_ids.add(int(order_id))
        daily_entries = len(entry_order_ids)

        trade_types = {
            value for value in (
                getattr(mt5, "DEAL_TYPE_BUY", None),
                getattr(mt5, "DEAL_TYPE_SELL", None),
            ) if value is not None
        }
        if not trade_types:
            raise PortfolioSnapshotError("MT5 deal-type constants are unavailable; daily P&L cannot be classified safely.")
        daily_realized = 0.0
        for deal in deals:
            cash_effect = sum(
                float(getattr(deal, field, 0.0) or 0.0)
                for field in ("profit", "commission", "swap", "fee")
            )
            if not math.isfinite(cash_effect):
                raise PortfolioSnapshotError("MT5 returned invalid deal P&L.")
            if getattr(deal, "type", None) in trade_types:
                daily_realized += cash_effect
            elif abs(cash_effect) > 1e-9:
                raise PortfolioSnapshotError(
                    "A non-trading account adjustment occurred today; the daily equity baseline cannot be verified safely."
                )
        if not math.isfinite(daily_realized):
            raise PortfolioSnapshotError("MT5 returned invalid daily realized P&L.")

        floating_pnl = 0.0
        exposure_amount = 0.0
        for position in positions:
            symbol = str(getattr(position, "symbol", "") or "").strip()
            volume = _number(getattr(position, "volume", None), "position volume")
            entry_price = _number(getattr(position, "price_open", None), "position entry price")
            stop_loss = _number(getattr(position, "sl", None), "position stop loss")
            if not symbol:
                raise PortfolioSnapshotError("An open position has no symbol.")
            opened_at = getattr(position, "time", None)
            if opened_at is None:
                opened_at = (getattr(position, "time_msc", None) or 0) / 1000.0
            try:
                opened_utc = datetime.fromtimestamp(float(opened_at), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError):
                raise PortfolioSnapshotError(f"Open position {symbol} has no verifiable open time.") from None
            if opened_utc < start_utc:
                raise PortfolioSnapshotError(
                    f"Open position {symbol} predates the New York trading day; starting equity cannot be reconstructed safely."
                )
            position_type = getattr(position, "type", None)
            if position_type == getattr(mt5, "POSITION_TYPE_BUY", object()):
                order_type = getattr(mt5, "ORDER_TYPE_BUY", None)
                if stop_loss >= entry_price:
                    raise PortfolioSnapshotError(f"Open position {symbol} has an invalid stop loss.")
            elif position_type == getattr(mt5, "POSITION_TYPE_SELL", object()):
                order_type = getattr(mt5, "ORDER_TYPE_SELL", None)
                if stop_loss <= entry_price:
                    raise PortfolioSnapshotError(f"Open position {symbol} has an invalid stop loss.")
            else:
                raise PortfolioSnapshotError(f"Unsupported position type for {symbol}.")
            if order_type is None:
                raise PortfolioSnapshotError("MT5 order type constants are unavailable.")
            pnl_at_stop = mt5.order_calc_profit(order_type, symbol, volume, entry_price, stop_loss)
            if pnl_at_stop is None:
                raise PortfolioSnapshotError(
                    f"Broker could not calculate stop-loss exposure for {symbol}: {mt5.last_error()}"
                )
            loss = _number(abs(float(pnl_at_stop)), f"{symbol} stop-loss exposure", allow_zero=True)
            exposure_amount += loss
            floating_pnl += _signed_number(getattr(position, "profit", None), f"{symbol} floating profit")
            floating_pnl += _signed_number(getattr(position, "swap", None), f"{symbol} swap")

        if not math.isfinite(floating_pnl) or not math.isfinite(exposure_amount):
            raise PortfolioSnapshotError("MT5 returned invalid open-position P&L or exposure.")
        starting_balance = balance - daily_realized
        if not math.isfinite(starting_balance) or starting_balance <= 0:
            raise PortfolioSnapshotError("Could not establish a valid New York day starting balance.")
        daily_net_pnl = daily_realized + floating_pnl
        daily_loss_percent = max(0.0, -daily_net_pnl / starting_balance * 100.0)
        exposure_percent = exposure_amount / balance * 100.0

        return MT5PortfolioSnapshot(
            as_of_utc=as_of,
            ny_trade_date=local_now.date().isoformat(),
            daily_entries=daily_entries,
            open_positions=len(positions),
            exposure_percent=exposure_percent,
            daily_loss_percent=daily_loss_percent,
            daily_net_pnl=daily_net_pnl,
            balance=balance,
        )
    except PortfolioSnapshotError:
        raise
    except Exception as exc:
        raise PortfolioSnapshotError(f"Could not verify MT5 portfolio state: {exc}") from exc


__all__ = [
    "MT5PortfolioSnapshot",
    "PortfolioSnapshotError",
    "build_mt5_portfolio_snapshot",
]
