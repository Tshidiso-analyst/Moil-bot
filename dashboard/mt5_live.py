"""Read-only MetaTrader 5 connection and market-data service."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MT5ConnectionResult:
    connected: bool
    message: str
    login: int = 0
    server: str = ""
    account_type: str = ""
    currency: str = ""
    balance: float = 0.0
    equity: float = 0.0
    free_margin: float = 0.0
    profit: float = 0.0


class MT5LiveService:
    """Provides read-only account, position and market information."""

    def __init__(self):
        self.mt5 = None
        self.connected = False

    def connect(
        self,
        login: int,
        password: str,
        server: str,
        requested_mode: str = "DEMO",
    ) -> MT5ConnectionResult:
        requested_mode = str(requested_mode).strip().upper()

        if requested_mode not in {"DEMO", "REAL"}:
            return MT5ConnectionResult(
                False, "Invalid account mode. Choose DEMO or REAL."
            )

        try:
            import MetaTrader5 as mt5
        except ImportError:
            return MT5ConnectionResult(
                False,
                "MetaTrader5 package is unavailable. Install the project's "
                "requirements and try again.",
            )

        self.mt5 = mt5

        # Disconnect any session previously opened by this service.
        try:
            mt5.shutdown()
        except Exception:
            pass

        initialized = mt5.initialize(
            login=int(login),
            password=password,
            server=server,
        )

        if not initialized:
            error = mt5.last_error()
            mt5.shutdown()
            self.connected = False
            return MT5ConnectionResult(
                False, f"MT5 initialization failed: {error}"
            )

        info = mt5.account_info()

        if info is None:
            error = mt5.last_error()
            mt5.shutdown()
            self.connected = False
            return MT5ConnectionResult(
                False, f"Could not read MT5 account information: {error}"
            )

        # MT5: 0 = demo, 1 = contest, 2 = real.
        trade_mode = int(info.trade_mode)

        if requested_mode == "REAL" and trade_mode != 2:
            mt5.shutdown()
            self.connected = False
            return MT5ConnectionResult(
                False,
                "Account-mode mismatch: REAL mode requires a real MT5 account.",
            )

        if requested_mode == "DEMO" and trade_mode == 2:
            mt5.shutdown()
            self.connected = False
            return MT5ConnectionResult(
                False,
                "Account-mode mismatch: DEMO mode cannot connect to a real account.",
            )

        self.connected = True
        account_type = "REAL" if trade_mode == 2 else "DEMO"

        return MT5ConnectionResult(
            connected=True,
            message="MT5 connected successfully in read-only dashboard mode.",
            login=int(info.login),
            server=str(info.server),
            account_type=account_type,
            currency=str(info.currency),
            balance=float(info.balance),
            equity=float(info.equity),
            free_margin=float(info.margin_free),
            profit=float(info.profit),
        )

    def _require_connection(self):
        if not self.connected or self.mt5 is None:
            raise RuntimeError("MT5 is not connected.")

    def positions(self) -> list[dict]:
        """Return current open positions; never sends trade requests."""
        self._require_connection()

        positions = self.mt5.positions_get()

        if positions is None:
            return []

        type_names = {
            self.mt5.POSITION_TYPE_BUY: "BUY",
            self.mt5.POSITION_TYPE_SELL: "SELL",
        }

        results = []

        for position in positions:
            results.append({
                "ticket": int(position.ticket),
                "symbol": str(position.symbol),
                "type": type_names.get(
                    position.type, str(position.type)
                ),
                "volume": float(position.volume),
                "price_open": float(position.price_open),
                "price_current": float(position.price_current),
                "profit": float(position.profit),
            })

        return results

    def _market_item(self, symbol: str) -> Optional[dict]:
        info = self.mt5.symbol_info(symbol)

        if info is None:
            return None

        # Request visibility for symbols not currently in Market Watch.
        if not info.visible:
            self.mt5.symbol_select(symbol, True)
            info = self.mt5.symbol_info(symbol)

            if info is None:
                return None

        tick = self.mt5.symbol_info_tick(symbol)

        if tick is None:
            return None

        bid = float(tick.bid)
        ask = float(tick.ask)
        digits = int(info.digits)

        return {
            "symbol": str(info.name),
            "description": str(info.description or info.name),
            "bid": bid,
            "ask": ask,
            "spread": max(0.0, ask - bid),
            "digits": digits,
        }

    def symbols(self) -> list[dict]:
        """Return symbols with available current bid/ask quotes."""
        self._require_connection()

        all_symbols = self.mt5.symbols_get()

        if all_symbols is None:
            return []

        results = []

        for info in all_symbols:
            item = self._market_item(info.name)

            if item is not None:
                results.append(item)

        return results

    def symbol(self, symbol: str) -> Optional[dict]:
        """Return current quote details for one symbol."""
        self._require_connection()
        return self._market_item(str(symbol).strip())

    def shutdown(self):
        """Disconnect this service from the MT5 terminal."""
        if self.mt5 is not None:
            try:
                self.mt5.shutdown()
            finally:
                self.connected = False
                self.mt5 = None
        else:
            self.connected = False
