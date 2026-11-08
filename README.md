# Between

**A youth mental-health workspace for assessments, clinician review and follow-up.**

Between brings young people's self-reported experiences and digital habits into an assigned clinician's workspace. Young people complete an assessment; clinicians review answers, record confidential notes and arrange follow-up. Separate Insights and Administration areas provide aggregate information and access management.

The application uses **Python, Flask, SQLite, HTML, CSS and JavaScript**. It runs locally without a Node build, a separate database server, Claude access or an AI API key.

**Current status:** a working local demonstration with fictional accounts and records. A trained synthetic-data ML demonstration is connected. PHQ-9, GAD-7 and WEMWBS are not administered; no clinically validated model is connected. Support requests are recorded for demonstration and are **not monitored**. Use example information only; this version is not configured for live clinical care.

## Contents

- [What makes the website link work?](#what-makes-the-website-link-work)
- [Requirements](#requirements)
- [Run on Windows](#run-on-windows)
- [Run on macOS or Linux](#run-on-macos-or-linux)
- [Accounts and access](#accounts-and-access)
- [Using the application](#using-the-application)
- [Features and availability](#features-and-availability)
- [Machine learning](#machine-learning)
- [Configuration](#configuration)
- [Data, backups and reset](#data-backups-and-reset)
- [Project structure](#project-structure)
- [Testing](#testing)
- [API overview](#api-overview)
- [Troubleshooting](#troubleshooting)
- [Deployment status](#deployment-status)
- [Development notes and licences](#development-notes-and-licences)

## What makes the website link work?

**A running Python process serves the website.** The entry point is `app.py`. Running it starts Flask's local web server, which serves the pages, JavaScript, CSS and API at **http://127.0.0.1:5000** and reads/writes the SQLite database.

After installing the requirements, start that server from the project root:

```powershell
cd "C:\Users\PC\Youth Mental Health App"
python app.py
```

If you installed dependencies in the virtual environment described below, use `.\.venv\Scripts\python.exe app.py` instead of `python app.py`.

Wait for the terminal to show:

```text
 * Serving Flask app 'app'
 * Debug mode: off
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

**Then open the link in your browser and leave the server terminal running.** Opening the README or clicking the link does not start Python. Stopping the server with Ctrl+C, terminating its process or shutting down the computer makes the link stop responding until you run `app.py` again.

`127.0.0.1` means this computer, and `5000` is the port used by the server. This is a local address, not a publicly hosted website. On another computer or phone, that same link points to that other device rather than this server.

## Requirements

- Python **3.10-3.12** for the pinned ML dependencies; development has been verified with Python 3.11.
- `pip` and Python's `venv` module.
- A modern web browser.
- An internet connection for the initial dependency installation. Fonts and application assets are served locally afterward.

Runtime dependencies are declared in [requirements.txt](requirements.txt). Test dependencies are in [requirements-dev.txt](requirements-dev.txt).

## Run on Windows

Use PowerShell and open the folder containing `app.py`. For this workspace:

```powershell
cd "C:\Users\PC\Youth Mental Health App"
```

If you copied the project elsewhere, use that folder instead.

### First-time setup

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If Windows does not recognise `python`, try `py -3` for the first two commands. Once the environment exists, use `.\.venv\Scripts\python.exe` as shown above.

Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)**. Keep the terminal open while using the site. The first start creates the local database, example records and a session-signing key automatically.

These commands use the virtual environment directly, so you do not need to activate it or change PowerShell's execution policy.

### Start again later

From the same project folder:

```powershell
.\.venv\Scripts\python.exe app.py
```

Press **Ctrl+C** in the server terminal to stop the website.

### Windows launcher

[Start-Between.cmd](Start-Between.cmd) is an alternative launcher. It runs `python app.py` using whichever Python is on your `PATH`; dependencies must be installed in that Python environment. It does not automatically select `.venv`. If you used the recommended setup above, the explicit virtual-environment command is the reliable way to start the app.

**Open the Flask URL, not an HTML file.** Double-clicking `static/index.html` will not connect the API. The nested `Youth Mental Health App/` folder contains the preserved older site, not the current application.

## Run on macOS or Linux

From the directory containing `app.py`:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python app.py
```

Open **http://127.0.0.1:5000**. On subsequent runs, use `./.venv/bin/python app.py`. Stop the server with **Ctrl+C**.

## Accounts and access

The homepage has two main routes:

- **Open clinician workspace** or **Sign in** opens staff access.
- **Start my assessment** opens access for a young person.

All preloaded example accounts use the password **`BetweenDemo!26`**. The account buttons on the sign-in page fill in credentials automatically; choose **Sign in** afterward.

| Email | Interface role | Access |
| --- | --- | --- |
| `counsellor@between.demo` | Clinician | Assigned assessments, confidential reviews, follow-up and reports |
| `counsellor2@between.demo` | Clinician | A separate assignment for checking access restrictions |
| `participant@between.demo` | Young person | Own assessment, saved draft, summary and participation controls |
| `researcher@between.demo` | Insights | Aggregate totals, completeness and model status |
| `admin@between.demo` | Administrator | Staff accounts, assignments, workspace settings and access history |

The email addresses are local example identifiers. No email service is connected. Existing accounts and records are created when an empty database is initialised; restarting the server does not reset them.

### Temporary assessment access

On the assessment access page, enter **`BETWEEN-DEMO`** as the access code and choose **Enter the demo**.

Each code entry creates a new temporary session. It cannot recover the same assessment after sign-out or session expiry. To test saving, signing out and returning to the same draft, use **`participant@between.demo`** instead.

Each assessment account can submit **once**. After submission, the homepage action becomes **View my summary**. For a fresh example assessment, use a new temporary access-code session or reset the local database as described below.

## Using the application

### Young-person assessment

1. Choose **Start my assessment** and use an access code or example account.
2. Enter an age from **13–24**, read the participation information and confirm the required choices. The under-18 example pathway includes separate guardian authorisation and young-person assent.
3. Complete background and social-media questions. **Back** preserves answers; **Continue** saves valid progress to the server.
4. Use **Save and exit** to save a partial draft. Wait for the save acknowledgement before leaving.
5. Review answers, edit if needed and submit once.
6. View the saved summary, optional support form or privacy controls.

Wellbeing questionnaires are shown as unavailable during the assessment. After submission, the young person sees their saved result, a plain-language explanation of contributing answers, their reported habits, review status and support information. Numerical probabilities and model versions are shown to authorised staff. Questionnaire scores are not generated. If the model is unavailable, answers are still saved without an estimate.

### Clinician workflow

1. Sign in with a clinician example account.
2. Search or filter the **Review queue** and open an assigned record.
3. Use **Overview**, **Responses** and **Follow-up** to inspect the assessment and review history.
4. Set a review status, add a confidential note and choose **Save review**.
5. A follow-up requires an owner, due date and agreed next action. Closing or reopening a case requires a reason.
6. Use **Print report**, then **Print / save as PDF**, for an assessment summary.

Review states are **Needs review**, **In progress**, **Follow-up arranged** and **Closed**. Changing a review state does not change a model output. If another reviewer changes a record, the app rejects a stale save and asks you to reload instead of silently overwriting their work.

Clinicians can access assigned records only. The printable report omits contact details and confidential note text; it includes the agreed next action.

### Insights and administration

- **Insights:** view aggregate counts, completeness, labelled distribution bars, an equivalent data table and a CSV export of totals. Individual assessment records and contact details are not available to this role.
- **Administration:** create example staff accounts, change roles or active status, assign clinicians, edit versioned configuration notes and filter access history. Staff account creation shows a temporary password; it does not send an invitation email.
- Reassign a clinician's open cases before deactivating or changing their role. An administrator cannot change their own access through the account editor.

### Support and privacy choices

Support requests store a chosen contact method, example contact details, suitable times and explicit permission to share them with an assigned clinician. A successful request shows a reference and status. Requests are **not monitored**, and no email, text message or response deadline is provided.

**Stop participating** closes further assessment activity and deletes an unsubmitted draft. Submitted records remain. **Request removal of my information** records a separate request for operator review; it does not immediately erase data. Both actions provide a receipt.

## Features and availability

| Available now | Not connected or enabled |
| --- | --- |
| Age eligibility, example consent and under-18 assent pathway | Verification of real guardian authorisation |
| Background and digital-habit questions with server-saved drafts | Approved live questionnaire wording and operating process |
| Validated inputs and duplicate-submission protection | PHQ-9, GAD-7 and WEMWBS administration or scoring |
| Assigned clinician cases, review history and reports | A clinically validated prediction model |
| Aggregate Insights, CSV totals and stored synthetic model evaluation | Small-group breakdowns and cohort filtering |
| Staff accounts, assignments and access history | Email invitations, password recovery, SMS or email notifications |
| Support and participation-request receipts | A verified service directory and staffed response/escalation service |

New submissions use a model trained only on simulated data; the preloaded Low, Moderate and High outputs remain **fictional examples**. Neither represents a diagnosis or clinical urgency. Missing information or an unavailable model never becomes a fabricated Low result. Questionnaire results, model outputs and clinician review remain separate.

The behaviour questionnaire is versioned as `behaviour-demo-1`. Its source wording and categories still require approval. Live use also needs appropriate instrument permissions, a WEMWBS licence, consent/assent arrangements, retention rules and a staffed safeguarding process. Editing configuration notes does not activate instruments, verify a service or unlock live collection.


## Machine learning

The complete implementation and reproduction guide is in [docs/machine-learning.md](docs/machine-learning.md). It includes the proposal mapping, provisional target definition, generator assumptions, feature contract, preprocessing, model comparison and limitations.

The checked-in model is ready to use after installing requirements. To regenerate and train:

```powershell
python -m ml.generate_data --samples 6000 --seed 2026
python -m ml.train --seed 2026
```

Restart Flask afterward. This creates 6,000 cleaned fictional participants, compares Logistic Regression, Decision Tree and Random Forest, and saves the selected preprocessing/classifier pipeline. A 70/15/15 stratified split keeps testing separate from fitting. The selected Logistic Regression model achieved **61.4% accuracy, 0.587 macro-F1 and 0.774 macro AUC on synthetic test data**. These are simulation results, not real-world validation.

Young people receive their result with a plain-language explanation, separate from clinician review status. Authorised staff see **Research model estimate** and its full details in the clinician record and report. Insights > Model status shows stored comparisons, per-class metrics and the confusion matrix. Preloaded examples stay labelled separately. Predictions are saved with the assessment and do not change when a record is viewed or reviewed.

Explore [ml/analysis.ipynb](ml/analysis.ipynb), [the evaluation report](ml/artifacts/evaluation.md), and [exported figures](ml/artifacts/figures/). Optional figure regeneration uses `python tools/plot_ml_evaluation.py` with development requirements installed. No real submissions are used for training, and no questionnaire scores are invented.

## Configuration

Set environment variables before starting the server. **`.env` files are not loaded automatically.**

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `5000` | Local port used by `python app.py` |
| `BETWEEN_SECRET_KEY` | Generated key stored in `instance/session.key` | Flask session-signing key; keep it private and stable between restarts |
| `BETWEEN_HTTPS` | Unset | Set to `1` to require HTTPS-only session cookies |
| `BETWEEN_BROWSER` | Unset | Optional browser executable path for browser QA only |

To use another port on Windows:

```powershell
$env:PORT = "5001"
.\.venv\Scripts\python.exe app.py
```

Then open **http://127.0.0.1:5001**. In Bash, use `PORT=5001 ./.venv/bin/python app.py`.

Leave `BETWEEN_HTTPS` unset for ordinary local HTTP testing. If it is set to `1` over HTTP, session cookies will not be sent and sign-in or CSRF validation can fail. Setting this variable does not configure an HTTPS server.

The default host is **`127.0.0.1`**, so the server is accessible on this computer, not automatically on another device. There is no implemented `HOST`, `DATABASE_URL` or model-key environment setting. `create_app(test_config)` accepts explicit Flask configuration overrides for tests or a future deployment entry point.

## Data, backups and reset

The first start creates:

| Path | Contents |
| --- | --- |
| `instance/between.sqlite3` | Accounts, drafts, assessments, reviews, separate contact records, participation requests, configuration and audit events |
| `instance/session.key` | Generated session-signing key, when `BETWEEN_SECRET_KEY` is unset |

The `instance/` directory is ignored by Git. Do not commit databases, signing keys, contact information or real patient records.

Sessions last **30 minutes** and can be extended from the expiry warning. Only server-acknowledged saves survive leaving the page. Sensitive responses are not persisted in browser local storage, analytics or offline caches. The homepage illustration uses page memory only and sends no assessment data.

Passwords are hashed; access is enforced on the server by role and assignment. The app also uses CSRF tokens, HTTP-only/SameSite cookies, no-store response headers and a Content Security Policy. The local database itself is **not encrypted by this app**.

### Back up or restore

Stop the server before making a simple file backup. Copy the `instance/` directory to a protected location. If using `BETWEEN_SECRET_KEY`, manage that secret separately. To restore, stop the server, restore the saved database and restart. Changing the signing key invalidates existing signed sessions; users must sign in again.

### Reset example records

1. Stop the server with **Ctrl+C**.
2. Back up the database if you want to keep its contents.
3. Rename **only** `instance/between.sqlite3` to a backup filename, such as `between.previous.sqlite3`. Choose a different filename if that backup already exists.
4. Restart the app. A new database is created with the original example accounts and records.

The reset database does not contain previous submissions, notes, requests or account changes. Renaming the old file preserves those records in the backup. Browser QA uses its own database and does not reset the application database.

## Project structure

```text
.
├── app.py                       # Flask app, API, SQLite schema and example data
├── requirements.txt             # Flask and pinned ML dependencies
├── requirements-dev.txt         # Runtime plus test dependencies
├── Start-Between.cmd             # Windows launcher using Python on PATH
├── static/
│   ├── index.html               # App shell and current script/style loading
│   ├── app.js                   # Routes, forms, session and workspace interactions
│   ├── opus-home.js             # Homepage and interactive online/offline scene
│   ├── styles.css               # Base components, responsive and print styles
│   ├── opus-theme.css           # Current shared theme
│   ├── mark.svg                 # Favicon
│   ├── fonts/                   # Self-hosted fonts and font licences
│   └── images/                  # Retained assets from an earlier design
├── tests/test_app.py            # Backend and permission tests
├── tools/
│   ├── browser_qa.py            # Isolated browser journey checks and screenshots
│   └── fetch_fonts.py           # Optional font-download utility
├── docs/                        # Design and collaboration notes
├── reference/                   # Extracted original design mockups
├── design-spec.txt              # Searchable extracted design specification
├── Youth_Mental_Health_Web_App_UI_Design.docx
└── Youth Mental Health App/      # Preserved original MindWell site
```

`instance/`, `.venv/` and `test-results/` are generated locally. `.test-deps/` and `.tooling/` are optional ignored development directories from this workspace; neither is needed to run the website. The older `identity.css`, `field.css` and window/photographic assets are retained but not loaded by the current interface.

## Testing

From the project root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe tools/browser_qa.py
```

On macOS or Linux, substitute `./.venv/bin/python` for `.\.venv\Scripts\python.exe`.

- Backend tests use temporary databases and cover authentication, role boundaries, case assignments, draft recovery, validation, submission retries, confidential notes, review conflicts, support/participation choices and administration. ML tests cover data cleaning, outcome leakage, split provenance, measured metrics, artifact failures and stable saved predictions.
- Browser QA starts its own temporary server on **port 5055**. You do not need to start `app.py` for it. It checks the interactive scene, keyboard access, phone/tablet layouts, clinician entry, expandable information, assessment completion, reviews, reports and staff areas.
- Browser QA recreates `test-results/browser.sqlite3` each run. Its screenshots, `browser-checks.json` and a generated assessment-summary PDF are saved under `test-results/`.
- If required, set `BETWEEN_BROWSER` to a compatible existing Chrome/Chromium executable. Otherwise install Chromium with the command above; the helper also recognises a cached Chromium path used by this workspace.

## API overview

The frontend and API share the same Flask origin. JSON request bodies use `Content-Type: application/json`.

Start with `GET /api/session` to receive a CSRF token and the current session. Send its token as **`X-CSRF-Token`** on every non-GET request, including sign-in. Preserve cookies between requests. Successful sign-in and access-code entry rotate the token, so use the returned replacement afterward.

| Area | Endpoints |
| --- | --- |
| Session | `GET /api/session`, `POST /api/login`, `POST /api/logout`, `POST /api/session/extend` |
| Temporary access | `POST /api/study-access` |
| Own assessment | `GET /api/assessment`, `PUT /api/assessment/draft`, `POST /api/assessment/submit` |
| Support | `POST /api/support` |
| Participation choices | `GET` / `POST /api/privacy/requests` |
| Assigned cases | `GET /api/cases`, `GET /api/cases/<id>` |
| Clinician review/report | `POST /api/cases/<id>/review`, `GET /api/cases/<id>/report` |
| Insights | `GET /api/research`, `GET /api/research/export` |
| Model metadata | `GET /api/model` (clinician, Insights or administrator) |
| Administration | `GET /api/admin`; `POST /api/admin/account`, `/api/admin/invite`, `/api/admin/assignment`, `/api/admin/config` |

Some internal names are retained for compatibility: `participant` is the young-person role, `counsellor` is Clinician, and `researcher` is Insights. The older API path names do not change the current clinician-focused interface.

Assessment submission requires a `submission_id`; retry the same submission with the same ID. Review saves require the record's current `version`. A stale version returns **409 Conflict**. Common errors are **400** for invalid input, **401** for missing/expired access, **403** for permission or CSRF failures and **429** after too many recent sign-in attempts. See [app.py](app.py) for exact request fields and responses.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `python` is not recognised | Install Python or try `py -3` on Windows. Use the virtual environment's Python once created. |
| `No module named flask` | Install requirements with the same Python executable used to start the server. |
| PowerShell blocks activation scripts | Activation is unnecessary; use `.\.venv\Scripts\python.exe` directly. |
| The launcher cannot find dependencies | `Start-Between.cmd` uses Python on PATH, not automatically `.venv`. Use the documented virtual-environment start command. |
| The page will not open | Confirm the server terminal is still running, then use its printed URL and port. Opening the HTML file directly is unsupported. |
| Another app uses port 5000 | Set `PORT=5001` using the configuration example and open the matching URL. |
| The old design is visible | Open the root Flask app, not the older nested site. Refresh with **Ctrl+F5** on Windows or **Cmd+Shift+R** on macOS. |
| Sign-in or CSRF validation fails | Reload the page, check session expiry and leave `BETWEEN_HTTPS` unset for local HTTP. API clients must send cookies and the latest CSRF token. |
| Too many sign-in attempts | Wait five minutes; the server limits recent attempts. |
| An assessment cannot be edited or submitted again | Each account allows one submission. View its summary or start a fresh temporary example session. |
| A temporary draft is missing after sign-out | Access-code sessions cannot be recovered. Use the named participant account for return visits. |
| A clinician cannot open a record | Ask an administrator to check the assignment and active role; unassigned records are rejected by the server. |
| A review save reports a conflict | Keep any unsaved note you need, reload the latest record and review the change before saving again. |
| No model estimate appears | Install requirements, check that `ml/artifacts/` is intact and restart Flask. Existing records are not rescored automatically. See the ML guide below. Local services remain unconnected. |
| Browser QA cannot launch Chromium | Install it with the environment's `python -m playwright install chromium`, or set `BETWEEN_BROWSER`. Port 5055 must also be free. |

## Deployment status

`python app.py` starts Flask's local development server with debugging disabled. Production hosting and live clinical operation are **not configured**. This application needs a Python-capable server; uploading the HTML alone to static hosting will not run its API.

A live deployment requires a production server/HTTPS setup, private staff authentication instead of public example access, appropriate storage and backup protection, approved assessment content and consent, defined retention/removal handling, verified support contacts and staffed safeguarding arrangements. There is no switch in the current interface that completes these integrations.

SQLite is the implemented database. MySQL was named in the original proposal but has not been integrated, and no MySQL migration tooling is included.

## Development notes and licences

- Edit [static/opus-home.js](static/opus-home.js) for homepage content and the illustrative scene, [static/app.js](static/app.js) for application flows, and [static/opus-theme.css](static/opus-theme.css) for the current theme.
- Preserve question meanings and response codes when changing layout. Keep clinician judgement, questionnaire results and model outputs distinct. Do not replace missing results with invented scores or weaken server-side permissions.
- The current design was developed with Claude Opus 5.5 and integrated and checked by Codex. See [the collaboration record](docs/opus-collaboration.md). The design notes also document earlier iterations; the loaded files in `static/index.html` identify the current implementation.
- Source Sans 3 and Source Serif 4 are self-hosted. Their licences are included in [static/fonts/source-sans-LICENSE.md](static/fonts/source-sans-LICENSE.md) and [static/fonts/source-serif-LICENSE.md](static/fonts/source-serif-LICENSE.md). The optional `tools/fetch_fonts.py` utility requires network access but is not part of application startup.
- No project-wide software licence file is currently included.
