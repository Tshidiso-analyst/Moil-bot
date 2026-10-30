    def open_trade_count(self) -> int:
        """Return the number of live MT5 positions currently open."""
        if not self.connected or self.mt5 is None:
            return 0
        return len(self.positions())

    def open_trade_summary(self) -> dict[str, float | int]:
        """Return the live open-trade aggregate for risk checks."""
        if not self.connected or self.mt5 is None:
            return {"count": 0, "volume": 0.0, "profit": 0.0}

        positions = self.positions()
        return {
            "count": len(positions),
            "volume": sum(float(item.get("volume", 0.0)) for item in positions),
            "profit": sum(float(item.get("profit", 0.0)) for item in positions),
        }
