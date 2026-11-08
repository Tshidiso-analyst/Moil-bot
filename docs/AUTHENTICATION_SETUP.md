# Authentication database setup

The authentication repository expects PostgreSQL tables named `users`, `user_sessions`, and `notification_preferences`.

## Apply the initial schema

Back up the database first. Then apply the migration once using a PostgreSQL client with the application's database credentials:

```powershell
psql "host=$env:DB_HOST port=$env:DB_PORT dbname=$env:DB_NAME user=$env:DB_USER" -f database/migrations/001_authentication.sql
psql "host=$env:DB_HOST port=$env:DB_PORT dbname=$env:DB_NAME user=$env:DB_USER" -f database/migrations/002_persistent_alerts.sql
```

The password should be entered through the PostgreSQL client's secure prompt or configured through a supported password file; do not put it in the command line or commit it.

## Provision the first account

After the migration succeeds and the database connection is configured, run the interactive provisioning command from the repository root:

```powershell
python -m auth.create_user
```

It prompts for the password without echoing it. Do not pass passwords as command-line arguments. The hosted configuration disables public self-registration by default.

## Enable authentication

Only after the migration succeeds and database connectivity has been verified, set:

- `MOILBOT_AUTH_REQUIRED=true`
- `MOILBOT_COOKIE_SECURE=true` when served over HTTPS
- `MOILBOT_ALLOW_REGISTRATION=false` unless controlled self-registration is intentionally enabled

Cloud mode should always require authentication. The cookie is HttpOnly, SameSite=Lax, host-only, and has a 24-hour lifetime.

## Important limitations

The dashboard now requires authentication in cloud mode, supports login/logout, enforces same-origin POST requests, uses secure session cookies, and applies a process-local login-attempt throttle. This is still not a complete production identity system. Email verification, persistent/distributed login rate limiting, password reset, account recovery, multi-factor authentication, per-user MT5 bridge ownership, and security monitoring remain outstanding. Do not claim production readiness until those controls are implemented and independently tested.

The hosted application now refuses to start when the authentication or persistent-alert tables are unavailable. Cloud mode uses PostgreSQL for alert history and delivery-attempt records, so apply both migrations before deployment. Configure all five database variables (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) and apply the migration before deployment. The hosted dashboard must not connect to a shared local MT5 terminal. Broker execution remains in the trusted local Windows bridge and is DEMO-only.
