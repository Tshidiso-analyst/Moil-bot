import MetaTrader5 as mt5


MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"


def main() -> int:
    """Run an explicit MT5 terminal connection check.

    Keeping connection work inside main() prevents pytest from connecting to
    a live terminal merely because it imports this module during collection.
    """
    if not mt5.initialize(path=MT5_PATH):
        print("MT5 connection failed:", mt5.last_error())
        return 1

    try:
        print("MT5 connected successfully.")
        print("MT5 version:", mt5.version())

        account = mt5.account_info()
        if account is not None:
            print("Account:", account.login)
            print("Server:", account.server)
            print("Balance:", account.balance)
        else:
            print("No trading account is currently logged in.")
            return 1
    finally:
        mt5.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
