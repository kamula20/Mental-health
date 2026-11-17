# Operating and hosting Between

The application now includes a production WSGI entry point, private-account mode, readiness checks and encrypted backup/restore tooling. Hosting infrastructure, DNS, TLS certificates, SMTP credentials, verified service contacts and a staffed clinical process must be supplied by the operator. No public hosting has been provisioned by these changes.

## Local presentation

```powershell
cd "C:\Users\PC\Youth Mental Health App"
.\.venv\Scripts\python.exe -m pip install -r requirements-deploy.txt
.\.venv\Scripts\python.exe -m ml.check
.\.venv\Scripts\python.exe serve.py
```

Open http://127.0.0.1:5000. The server stays in the terminal. `Start-Between.cmd` is an alternative that selects `.venv` when present and uses Flask's local development server. Run one server on the port at a time. The core application can still run with `requirements.txt` only; Waitress and encrypted-backup support use `requirements-deploy.txt`.

The default demonstration includes example accounts, a temporary access code and local mail previews. It never sends email unless SMTP delivery is explicitly configured. Use fictional information for demonstrations.

## Private deployment

Use Python 3.10 or later, install `requirements-deploy.txt`, and run `python serve.py` behind a managed HTTPS reverse proxy or hosting platform. `Procfile` provides the same entry point. Use a persistent, private disk for SQLite; an ephemeral hosting filesystem will lose records when replaced. Run a single app instance with SQLite rather than independent replicas with separate local databases.

Set these environment variables in the hosting provider or process manager. `.env` files are **not loaded automatically**; `.env.example` is a reference template only.

| Setting | Purpose |
| --- | --- |
| `BETWEEN_ENV=production` | Enforces secure startup requirements |
| `BETWEEN_DEMO=0` | Disables public example access and seeding |
| `BETWEEN_SECRET_KEY` | Private, stable, randomly generated value of at least 32 characters |
| `BETWEEN_HTTPS=1` | Secure session cookies and HSTS; the reverse proxy must actually provide TLS |
| `BETWEEN_BASE_URL=https://your-domain` | Trusted public URL used in account links; never derived from an untrusted request header |
| `BETWEEN_DATABASE` | Absolute path to a fresh database on private persistent storage |
| `BETWEEN_BIND_HOST` | Defaults to `127.0.0.1`; set `0.0.0.0` only when the platform's routing requires it |
| `PORT` | Local WSGI listening port; defaults to `5000` |
| `BETWEEN_MAIL_MODE` | `manual` or `smtp`; production refuses development `preview` mode |
| `BETWEEN_BACKUP_KEY` | Fernet key stored in a protected secret store, separately from encrypted backups |

Production startup refuses a database containing active `@between.demo` accounts. Create a fresh private database instead of exposing the public example passwords. Migrations create additional tables without deleting existing records. The application remains a research tool; production web-server configuration does not constitute approval for clinical care.

Create the first administrator locally on the deployment host:

```powershell
python tools/manage.py bootstrap-admin --email operator@example.org --name "Workspace operator"
```

The command asks for a password twice without echoing it. It refuses duplicate emails and never prints or emails the password. Then use Administration → Invite account to invite staff and participants. No public registration route grants staff roles.

Sources for serving behaviour: [Waitress usage](https://docs.pylonsproject.org/projects/waitress/en/latest/usage.html) and [Waitress command-line options](https://docs.pylonsproject.org/projects/waitress/en/stable/runner.html).

## Account mail and reminders

`BETWEEN_MAIL_MODE=preview` stores local invitation/reset previews under Administration → Account mail. `manual` explicitly requires the administrator to provide the single-use setup link securely to its intended recipient. Neither mode sends email. Preview/manual mail contains account-access links and is restricted to administrators.

For actual email, configure:

```text
BETWEEN_MAIL_MODE=smtp
BETWEEN_SMTP_HOST=your-provider-host
BETWEEN_SMTP_PORT=587
BETWEEN_SMTP_FROM=your-workspace-address
BETWEEN_SMTP_USERNAME=your-smtp-login
BETWEEN_SMTP_PASSWORD=your-provider-secret
```

SMTP uses STARTTLS. Successful delivery clears the message body from the outbox so raw setup tokens are not retained there. Failed delivery remains labelled Failed; the app does not claim an email was delivered. Expiring account tokens are hashed in the database and single-use; a new token supersedes an earlier token of the same purpose. Password changes revoke prior signed-in sessions. Password reset responses do not disclose whether an email has an account.

To prepare reminders for appointments in the next 24 hours:

```powershell
python tools/manage.py send-reminders
```

Schedule that command using the host's scheduler, for example hourly, with the same environment as the application. No scheduler has been installed automatically. Reminder event keys prevent duplicate preparation for the same appointment version. Emails contain only a generic appointment message and a sign-in link, not clinical results, notes or contact details. Appointment creation and shared feedback also create in-app messages immediately.

## Encrypted backups

```powershell
python tools/manage.py backup
```

The command takes a consistent online SQLite snapshot, verifies it, encrypts it with Fernet, then removes the temporary plaintext snapshot. The default encrypted destination is under ignored `instance/backups/`. In local demonstration mode, a key is generated in `instance/backup.key`; keep a protected, separate copy of that key. Production requires `BETWEEN_BACKUP_KEY` from the secret store. Losing the key makes backups unrecoverable; storing it alongside exported backups defeats the intended separation.

To restore into a **new** database file:

```powershell
python tools/manage.py restore --file instance/backups/YOUR_BACKUP.sqlite3.fernet --destination instance/restored.sqlite3
```

Restore checks authentication/integrity and refuses to overwrite an existing file. Stop the server, configure `BETWEEN_DATABASE` to the reviewed restored database and restart. Restoring a database can invalidate newer invitations, password changes and recorded activity; use an appropriate recovery process. Protect the session-signing key separately. The live SQLite database is **not encrypted by the app**: restrict filesystem access, use encrypted host storage and protect the volume and secret store.

## Monitoring and upgrades

`GET /healthz` checks process liveness. `GET /readyz` checks database access and an in-memory model prediction without saving an assessment or exposing sensitive information. It returns 503 if readiness fails.

```powershell
python tools/check_deployment.py --base-url https://your-domain --require-production
```

Point the host's uptime/readiness checks at those endpoints. Keep `ml/artifacts/model.json`, `model.joblib`, `evaluation.json` and `manifest.json` from the same commit. `python -m ml.check` validates the local setup. Use a backup before upgrades and retain it until the new workflows have been checked.

## Clinical and instrument setup still required

PHQ-9 and GAD-7 wording, answer values, two-week timeframe and score bands are versioned in `instruments.py`. Appropriate age-group administration, local interpretation, staff competence and a direct response process require professional review before real collection, especially for participants under 18. A positive PHQ-9 harm-related response creates a separate direct-check-in indicator; it does not turn the ML class into an urgency score or automatically provide an emergency response.

WEMWBS text is not distributed: a clinician can record a total only while explicitly confirming a licensed source administration. [Warwick requires an appropriate licence](https://warwick.ac.uk/services/innovations/wemwbs/licenses/); a non-commercial licence does not grant public redistribution rights.

Support-directory entries require an official HTTPS source, a checked date, hours, eligibility and explicit administrator confirmation. No fictional test contact is seeded into the real directory. Published contacts are staff-entered checks, not a promise of availability or an emergency response. Real guardian authorisation, retention/removal policy, staffed response arrangements and study approvals remain operator responsibilities.
