from instruments.classifier import classify_symbol
from instruments.models import Instrument


class MT5InstrumentDiscovery:

    def discover(self) -> list[Instrument]:
        import MetaTrader5 as mt5

        symbols = mt5.symbols_get()

        if symbols is None:
            raise RuntimeError(
                f"Unable to retrieve MT5 symbols: {mt5.last_error()}"
            )

        instruments = []

        for item in symbols:
            symbol = item.name

            description = getattr(
                item,
                "description",
                "",
            ) or ""

            asset_class = classify_symbol(
                symbol,
                description,
            )

            instruments.append(
                Instrument(
                    symbol=symbol,
                    asset_class=asset_class,
                    description=description,
                    currency=getattr(
                        item,
                        "currency_base",
                        "",
                    ) or "",
                    point=float(
                        getattr(item, "point", 0.0)
                        or 0.0
                    ),
                    digits=int(
                        getattr(item, "digits", 0)
                        or 0
                    ),
                    trade_contract_size=float(
                        getattr(
                            item,
                            "trade_contract_size",
                            0.0,
                        )
                        or 0.0
                    ),
                )
            )

        return instruments

    def discover_by_class(
        self,
        asset_class: str,
    ) -> list[Instrument]:

        return [
            instrument
            for instrument in self.discover()
            if instrument.asset_class == asset_class
        ]
