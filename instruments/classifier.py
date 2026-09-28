import re


FOREX_PATTERN = re.compile(
    r"^[A-Z]{6}[A-Za-z0-9._-]*$"
)


INDEX_KEYWORDS = {
    "US30",
    "DJ30",
    "DJI",
    "NAS100",
    "NASDAQ",
    "USTEC",
    "SPX500",
    "SP500",
    "US500",
    "GER40",
    "DAX",
    "UK100",
    "FTSE",
    "FRA40",
    "CAC",
    "JPN225",
    "NIKKEI",
    "AUS200",
    "HK50",
}


COMMODITY_KEYWORDS = {
    "XAU",
    "GOLD",
    "XAG",
    "SILVER",
    "WTI",
    "BRENT",
    "OIL",
    "NGAS",
    "NATGAS",
}


CRYPTO_KEYWORDS = {
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "DOGE",
    "ADA",
}


def _contains_keyword(
    symbol: str,
    description: str,
    keywords: set[str],
) -> bool:

    return any(
        keyword in symbol
        or keyword in description
        for keyword in keywords
    )


def classify_symbol(
    symbol: str,
    description: str = "",
) -> str:

    normalized = symbol.upper()
    description_upper = description.upper()

    # Specific asset classes must be checked BEFORE
    # the generic six-letter Forex pattern.

    if _contains_keyword(
        normalized,
        description_upper,
        COMMODITY_KEYWORDS,
    ):
        return "commodity"

    if _contains_keyword(
        normalized,
        description_upper,
        CRYPTO_KEYWORDS,
    ):
        return "crypto"

    if _contains_keyword(
        normalized,
        description_upper,
        INDEX_KEYWORDS,
    ):
        return "index"

    # Forex is intentionally checked after commodities,
    # crypto and indices because symbols such as XAUUSD
    # and BTCUSD also contain six letters.
    if FOREX_PATTERN.match(normalized):
        return "forex"

    return "stock_or_other"
