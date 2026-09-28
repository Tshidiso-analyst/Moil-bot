from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_price_chart(
    candles: list[dict[str, Any]],
    symbol: str,
    title: str | None = None,
) -> go.Figure:
    """Create an interactive OHLC candlestick chart."""

    if not candles:
        raise ValueError("Candles must not be empty.")

    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
    }

    for index, candle in enumerate(candles):
        missing = required - candle.keys()

        if missing:
            raise ValueError(
                f"Candle {index} is missing required fields: "
                f"{sorted(missing)}"
            )

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=[candle["timestamp"] for candle in candles],
                open=[candle["open"] for candle in candles],
                high=[candle["high"] for candle in candles],
                low=[candle["low"] for candle in candles],
                close=[candle["close"] for candle in candles],
                name=symbol,
            )
        ]
    )

    fig.update_layout(
        title=title or f"{symbol} Price Chart",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        height=600,
    )

    return fig


def create_volume_chart(
    candles: list[dict[str, Any]],
    symbol: str,
) -> go.Figure:
    """Create a volume chart from OHLCV candle data."""

    if not candles:
        raise ValueError("Candles must not be empty.")

    for index, candle in enumerate(candles):
        if "volume" not in candle:
            raise ValueError(
                f"Candle {index} is missing required field: volume"
            )

    fig = go.Figure(
        data=[
            go.Bar(
                x=[candle["timestamp"] for candle in candles],
                y=[candle["volume"] for candle in candles],
                name="Volume",
            )
        ]
    )

    fig.update_layout(
        title=f"{symbol} Volume",
        xaxis_title="Time",
        yaxis_title="Volume",
        template="plotly_white",
        height=300,
    )

    return fig


def create_price_and_volume_chart(
    candles: list[dict[str, Any]],
    symbol: str,
) -> go.Figure:
    """Create a combined interactive price and volume chart."""

    if not candles:
        raise ValueError("Candles must not be empty.")

    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    for index, candle in enumerate(candles):
        missing = required - candle.keys()

        if missing:
            raise ValueError(
                f"Candle {index} is missing required fields: "
                f"{sorted(missing)}"
            )

    timestamps = [candle["timestamp"] for candle in candles]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.75, 0.25],
    )

    fig.add_trace(
        go.Candlestick(
            x=timestamps,
            open=[candle["open"] for candle in candles],
            high=[candle["high"] for candle in candles],
            low=[candle["low"] for candle in candles],
            close=[candle["close"] for candle in candles],
            name=symbol,
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=timestamps,
            y=[candle["volume"] for candle in candles],
            name="Volume",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=f"{symbol} Market Chart",
        template="plotly_white",
        height=750,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)

    return fig
