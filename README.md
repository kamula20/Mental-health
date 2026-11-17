# Between

A youth mental-health research workspace for assessments, clinician review and follow-up.

Young people describe their online habits and can complete optional wellbeing questionnaires. The app saves a model estimate and an explanation, keeps questionnaire scores separate, and gives assigned clinicians a workspace for review, shared feedback and appointments. Repeat assessments preserve previous visits and show questionnaire history.

**Status:** working final-year research prototype. PHQ-9 and GAD-7 screening scores are implemented. The ML model's training and evaluation data are generated; clinical validation with an independently assessed participant study is still pending. Support requests are not an emergency or monitored counselling service. Use fictional information for the demonstration.

## Start on Windows

From the folder containing `app.py`, use Python 3.10 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-deploy.txt
.\.venv\Scripts\python.exe -m ml.check
.\.venv\Scripts\python.exe serve.py
```

Open **http://127.0.0.1:5000** and leave the terminal running. Press Ctrl+C to stop it. `Start-Between.cmd` is another launcher: it prefers `.venv`, checks setup, and runs the local Flask development server.

The model is included. You do not need an AI API key, a separate model server, Node, or the ML training libraries to obtain predictions. `requirements.txt` contains the Flask runtime; `requirements-deploy.txt` adds Waitress and encrypted-backup support. Training and tests use separate development requirements.

On macOS/Linux, use `python3 -m venv .venv` and replace `.\.venv\Scripts\python.exe` with `./.venv/bin/python`.

Open the Flask/Waitress URL, not an HTML file. The nested `Youth Mental Health App/` directory preserves an older website and is not the current application.

## Accounts and presentation

Default demonstration accounts all use **`BetweenDemo!26`**. Buttons on the sign-in page fill the example credentials.

| Account | Workspace |
| --- | --- |
| `participant@between.demo` | Own assessments, history, shared feedback, appointments and messages |
| `counsellor@between.demo` | Assigned cases, independent conclusions, private notes and follow-up |
| `counsellor2@between.demo` | A separate clinician assignment for checking access boundaries |
| `researcher@between.demo` | Aggregate Insights and model evaluation |
| `admin@between.demo` | Accounts, invitations, assignments, support directory, account mail and audit history |

`BETWEEN-DEMO` creates a fresh temporary assessment session. It cannot recover the same participant after sign-out. Use the named participant account when demonstrating returning later.

Follow [the presentation walkthrough](docs/demo-day-walkthrough.md) for a complete participant-to-clinician demonstration.

## What is implemented

| Area | Behaviour |
| --- | --- |
| Participation | Ages 13-24, separate under-18 guardian/assent example choices, consent checks and saved drafts |
| Assessment | Background and online-habit questions; optional full PHQ-9/GAD-7 responses and difficulty questions |
| Questionnaire scoring | Validated integer inputs, deterministic totals/bands, explicit missing scores when skipped |
| Model | Saved Low/Moderate/High estimates, individual answer-based explanations, integrity-checked portable inference |
| Results | Plain-language participant summary; technical model details available to authorised staff |
| History | Repeat assessments, preserved earlier answers/results/reviews, questionnaire timeline and equivalent data table |
| Clinician review | Assignment restrictions, independent conclusion, model agreement/disagreement with reasons, private notes and explicitly shared feedback |
| Follow-up | Appointments, rescheduling/cancellation/completion, upcoming and overdue actions, in-app messages and operator-run reminder delivery |
| Support | Administrator-maintained directory with source URLs, check dates, hours and eligibility |
| Account lifecycle | Role-controlled invitations, one-time expiring setup/reset links, password recovery and prior-session revocation |
| Operations | Waitress entry point, private deployment configuration, liveness/readiness checks, encrypted backup and safe restore |
| Evaluation | Stored model comparisons/metrics and a separate workflow for independently labelled external data |

Questionnaire scores, the model class, clinician judgement and urgency are distinct. The model only uses age and six online-habit features; it does not use questionnaire scores or clinician conclusions as prediction inputs. A positive PHQ-9 harm-related response creates a separate direct-check-in indicator for assigned clinicians and a participant support message, independent of the ML class. It does not provide a staffed emergency response.

PHQ-9/GAD-7 questions retain their published two-week timeframe and answer codes. Clinical interpretation and age-appropriate administration need a qualified professional and an approved local protocol. WEMWBS wording is not distributed: clinicians can record a total from an appropriately licensed administration with a source reference and explicit confirmation. [Instrument and operational details](docs/deployment.md#clinical-and-instrument-setup-still-required) explain those limits.

## Clinician and participant journeys

1. The participant completes an assessment, optionally including wellbeing questions, and sees their result, contributing answers and questionnaire totals separately.
2. An assigned clinician reviews the record and its history, records an independent conclusion and chooses whether to share a participant message. Private notes stay private.
3. The clinician can schedule an appointment and manage agreed actions in Follow-up dashboard. Participants see their appointments and in-app messages.
4. The participant can start a follow-up assessment. Earlier visits are archived transactionally when the new assessment is submitted; they are not overwritten.
5. A printable report includes questionnaire scores and clinician sign-off while excluding private note text.

Withdrawal closes further participation and deletes an unsubmitted draft. Removal requests are recorded for operator review; they do not instantly erase records. Real retention, guardian verification and staffed-response arrangements require an operating policy outside this project.

## Invitations, mail and service contacts

Administration -> Invite account creates an expiring setup link. The recipient chooses a password of at least 12 characters. Forgot your password? opens recovery; responses do not disclose whether an account exists.

Default delivery is **preview**. Administration -> Account mail shows messages locally and does not send email. **Manual** delivery requires an operator to give the setup link securely to its intended recipient. Actual sending requires explicitly configured SMTP. [Deployment instructions](docs/deployment.md#account-mail-and-reminders) list settings and the reminder command.

No fabricated contact is seeded into the live support directory. Administrators publish services only after checking their official source, operating hours and eligibility. Confirmation records the administrator's declaration; it is not automatic verification of a provider or a guarantee that someone will respond.

## Reliability and data

The first local start creates `instance/between.sqlite3` and, when no environment secret is supplied, `instance/session.key`. This directory is ignored by Git. Never commit accounts, databases, tokens, keys, backup files or real participant records.

Passwords are hashed. APIs enforce role and assignment checks, CSRF protection and 30-minute sessions. Sensitive responses are not put in browser local storage. The live SQLite database is not encrypted by this app; restrict filesystem access and protect host storage. Backup files can be encrypted separately.

```powershell
.\.venv\Scripts\python.exe tools/manage.py backup
.\.venv\Scripts\python.exe tools/manage.py restore --file instance/backups/YOUR_BACKUP.sqlite3.fernet --destination instance/restored.sqlite3
```

Restore refuses to overwrite an existing file. Preserve the backup key separately and stop the server before configuring it to use a restored database. See [backup and restore details](docs/deployment.md#encrypted-backups).

If a model result is missing, run `python -m ml.check` with the same Python used for the server. Restore the complete `ml/artifacts/` folder from the same commit if files are missing. For an assessment saved during an outage, use **Calculate my result**. Existing non-null predictions are never replaced by that action.

## Hosting and configuration

[docs/deployment.md](docs/deployment.md) covers production startup, a fresh private database, administrator bootstrapping, SMTP, HTTPS, reminders, backups and monitoring. [.env.example](.env.example) documents environment variables; `.env` files are not loaded automatically.

Production mode disables public demo access and seeding, requires a stable private secret and HTTPS configuration, and rejects active public example accounts. The operator must provide the actual hosting platform, persistent private storage, domain/TLS and delivery credentials. These changes have not provisioned a public website or a staffed clinical service.

`GET /healthz` checks liveness. `GET /readyz` verifies database access and a real in-memory model prediction without recording an assessment or exposing data. `tools/check_deployment.py` can check an operator-owned deployment.

## Machine learning and evidence

Read [docs/machine-learning.md](docs/machine-learning.md), [the notebook](ml/analysis.ipynb) and [the measured evaluation](ml/artifacts/evaluation.md). The checked-in Logistic Regression model achieved 61.4% accuracy, 0.587 macro-F1 and 0.774 macro AUC on its generated development test data. Those results do not establish clinical reliability.

The portable JSON model evaluates the same learned preprocessing and coefficients as the original joblib pipeline. Tests compare all 6,000 processed examples and exercise the full app with ML-package imports blocked. No retraining is needed for ordinary use.

The external-data workflow is ready, but no real participant study has been fabricated. Run `python -m ml.validate_external --help` in the training environment. It requires consent/independence declarations, independently defined reference labels and complete versioned inputs. Its output contains aggregate errors and provenance, does not grant a clinical release, and can be displayed in Insights when configured by the operator.

## Tests

Use Python 3.10-3.12 for the pinned training/test dependencies:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python tools/browser_qa.py
python tools/workspace_browser_qa.py
```

Browser tests use isolated databases and save screenshots under ignored `test-results/`. They recognise the existing cached Chromium in this workspace. On another machine, install Chromium with `python -m playwright install chromium` or set `BETWEEN_BROWSER` to a compatible executable.

## Main files

| Path | Purpose |
| --- | --- |
| `app.py` | Flask, role/session controls, assessments and database migrations |
| `workspace.py` | History, conclusions, appointments, invitations, directory and notifications |
| `instruments.py` | Questionnaire definitions, validation and deterministic screening scores |
| `static/app.js`, `static/workspace.js` | Current interface and expanded workflows |
| `static/opus-theme.css`, `static/workspace.css` | Shared theme and new components |
| `ml/` | Training, portable model, explanation and external-evaluation tooling |
| `tools/manage.py` | Account bootstrap, encrypted backups, restore and reminders |
| `serve.py` | Production WSGI server entry point |

PDF files and private local data remain excluded from Git. Original design and collaboration records are retained under `docs/`. Font licences are included with the self-hosted fonts. No project-wide software licence has been selected.
