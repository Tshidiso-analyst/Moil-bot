import MetaTrader5 as mt5


MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"


if not mt5.initialize(path=MT5_PATH):
    print("MT5 connection failed:", mt5.last_error())
    raise SystemExit


print("MT5 connected successfully.")
print("MT5 version:", mt5.version())

account = mt5.account_info()

if account is not None:
    print("Account:", account.login)
    print("Server:", account.server)
    print("Balance:", account.balance)
else:
    print("No trading account is currently logged in.")


mt5.shutdown()