# Authentication database setup

The authentication repository expects PostgreSQL tables named `users`, `user_sessions`, and `notification_preferences`.

## Apply the initial schema

Back up the database first. Then apply the migration once using a PostgreSQL client with the application's database credentials:

```powershell
psql "host=$env:DB_HOST port=$env:DB_PORT dbname=$env:DB_NAME user=$env:DB_USER" -f database/migrations/001_authentication.sql
```

The password should be entered through the PostgreSQL client's secure prompt or configured through a supported password file; do not put it in the command line or commit it.

## Enable authentication

Only after the migration succeeds and database connectivity has been verified, set:

- `MOILBOT_AUTH_REQUIRED=true`
- `MOILBOT_COOKIE_SECURE=true` when served over HTTPS

Cloud mode should always require authentication. The cookie is HttpOnly, SameSite=Lax, host-only, and has a 24-hour lifetime.

## Important limitations

This is the initial persistence schema, not a complete production identity system. Email verification, persistent login rate limiting, password reset, account recovery, multi-factor authentication, per-user MT5 bridge ownership, and security monitoring remain outstanding. Do not claim production readiness until those controls are implemented and independently tested.

The hosted dashboard must not connect to a shared local MT5 terminal. Broker execution remains in the trusted local Windows bridge and is DEMO-only.
