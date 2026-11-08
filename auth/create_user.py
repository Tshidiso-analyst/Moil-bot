from __future__ import annotations

from getpass import getpass

from auth.service import AuthService, RegistrationError


def main() -> int:
    print("Create a Moil-bot user account")
    full_name = input("Full name: ").strip()
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    password = getpass("Password (minimum 8 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 1
    try:
        user = AuthService().register(full_name, username, email, password)
    except (RegistrationError, RuntimeError) as exc:
        print(f"Account creation failed: {exc}")
        return 1
    print(f"Created user '{user.username}' (id={user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
