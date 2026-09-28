import pandas as pd


REQUIRED_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def validate_market_data(dataframe: pd.DataFrame) -> None:
    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    if dataframe.empty:
        raise ValueError("Market data is empty.")

    if dataframe["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps detected.")

    if dataframe[REQUIRED_COLUMNS].isnull().any().any():
        raise ValueError("Missing values detected.")

    if (dataframe["high"] < dataframe["low"]).any():
        raise ValueError("Invalid high/low relationship.")

    if (
        (dataframe["open"] < dataframe["low"])
        | (dataframe["open"] > dataframe["high"])
    ).any():
        raise ValueError("Invalid open prices.")

    if (
        (dataframe["close"] < dataframe["low"])
        | (dataframe["close"] > dataframe["high"])
    ).any():
        raise ValueError("Invalid close prices.")

    if (dataframe["volume"] < 0).any():
        raise ValueError("Negative volume detected.")
