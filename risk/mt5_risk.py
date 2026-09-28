from risk.models import InstrumentRisk


class MT5RiskSpecification:

    def get(self, symbol: str) -> InstrumentRisk:
        import MetaTrader5 as mt5

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        info = mt5.symbol_info(symbol)

        if info is None:
            raise RuntimeError(
                f"Unable to retrieve MT5 information for {symbol}: "
                f"{mt5.last_error()}"
            )

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Unable to select MT5 symbol {symbol}: "
                f"{mt5.last_error()}"
            )

        return InstrumentRisk(
            symbol=info.name,
            point=float(info.point or 0.0),
            tick_size=float(
                getattr(info, "trade_tick_size", 0.0) or 0.0
            ),
            tick_value=float(
                getattr(info, "trade_tick_value", 0.0) or 0.0
            ),
            contract_size=float(
                getattr(info, "trade_contract_size", 0.0) or 0.0
            ),
            volume_min=float(
                getattr(info, "volume_min", 0.0) or 0.0
            ),
            volume_max=float(
                getattr(info, "volume_max", 0.0) or 0.0
            ),
            volume_step=float(
                getattr(info, "volume_step", 0.0) or 0.0
            ),
        )
