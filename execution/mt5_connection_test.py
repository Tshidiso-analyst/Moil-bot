"""Manual MT5 connection diagnostic; never runs during pytest collection."""
from __future__ import annotations


def main() -> int:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 is not installed. Run this diagnostic on the Windows trading workstation.")
        return 2

    mt5_path = r"C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    if not mt5.initialize(path=mt5_path):
        print("MT5 connection failed:", mt5.last_error())
        return 1

    try:
        print("MT5 connected successfully.")
        print("MT5 version:", mt5.version())
        account = mt5.account_info()
        if account is None:
            print("No trading account is currently logged in.")
            return 1
        print("Account:", account.login)
        print("Server:", account.server)
        print("Balance:", account.balance)
        print("Trade mode:", account.trade_mode)
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
