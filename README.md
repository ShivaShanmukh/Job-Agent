# Job Application Agent 🤖

A **free, self-hosted** Python agent that automates job applications end-to-end — no n8n, no subscriptions, no cloud required.

> Reads from Google Sheets → Applies via browser automation → Logs to SQLite → Notifies via Gmail

---

## Table of Contents

- [How It Works](#how-it-works)
- [Agent Flows](#agent-flows)
  - [Daily Apply Workflow](#daily-apply-workflow)
  - [Status Check Workflow](#status-check-workflow)
- [Architecture](#architecture)
  - [Component Map](#component-map)
  - [Data Flow](#data-flow)
- [Job Status Lifecycle](#job-status-lifecycle)
- [Scheduler Timeline](#scheduler-timeline)
- [Google Sheet Schema](#google-sheet-schema)
- [Configuration Reference](#configuration-reference)
- [CLI Commands](#cli-commands)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Security Notes](#security-notes)

---

## How It Works

At its core the agent runs two recurring workflows on a cron-like schedule — equivalent to two n8n workflow tabs running in parallel:

| Workflow | Trigger | What it does |
|---|---|---|
| **Apply** | Weekdays at `APPLY_HOUR:APPLY_MINUTE` UTC | Reads pending jobs → generates cover letters → applies via browser |
| **Status Check** | Every `STATUS_CHECK_INTERVAL_DAYS` days | Re-visits applied jobs → scrapes status → emails you if anything changed |

Everything is driven by a single Google Sheet you maintain. You add job URLs, the agent does the rest.

---

## Agent Flows

### Daily Apply Workflow

This mirrors a typical n8n workflow with a Cron trigger → HTTP/browser nodes → Google Sheets node → Gmail node.

```mermaid
flowchart TD
    TRIGGER(["⏰ Cron Trigger\nWeekdays @ APPLY_HOUR:APPLY_MINUTE UTC"])
    READ["📋 Read Google Sheet\nFilter: Status = 'Not Applied'"]
    EMPTY{"Any jobs\nfound?"}
    DONE(["✅ Done — nothing to do"])
    BATCH["🔢 Slice batch\n≤ MAX_APPLICATIONS_PER_RUN jobs"]

    LOOP_START(["🔁 For each job"])

    COVER["✍️ Generate Cover Letter\nJinja2 template\n+ company & position vars"]

    ROUTE{"Job URL\nplatform?"}

    LINKEDIN["🔵 LinkedIn Easy Apply\n① Login to LinkedIn\n② Navigate to job URL\n③ Click Easy Apply\n④ Upload resume\n⑤ Fill cover letter\n⑥ Step through form\n⑦ Click Submit"]

    INDEED["🔴 Indeed Apply\n① Login to Indeed\n② Navigate to job URL\n③ Click Apply Now\n④ Upload resume\n⑤ Fill cover letter\n⑥ Step through form\n⑦ Click Submit"]

    UNSUPPORTED["⚠️ Unsupported Platform\nReturn Failed result\n(apply manually)"]

    SUCCESS{"Application\nsubmitted?"}

    UPDATE_SHEET["📊 Update Google Sheet\nStatus → Applied\nApplied_Date, Application_ID, Notes"]
    LOG_DB["💾 Log to SQLite\napplications table"]
    EMAIL["📧 Send Gmail Notification\n🟢 Green = Applied\n🔴 Red = Failed"]

    NEXT_JOB{{"More jobs\nin batch?"}}
    END(["✅ Batch complete\nLog summary"])

    TRIGGER --> READ
    READ --> EMPTY
    EMPTY -- "No" --> DONE
    EMPTY -- "Yes" --> BATCH
    BATCH --> LOOP_START
    LOOP_START --> COVER
    COVER --> ROUTE
    ROUTE -- "linkedin.com" --> LINKEDIN
    ROUTE -- "indeed.com" --> INDEED
    ROUTE -- "other" --> UNSUPPORTED
    LINKEDIN --> SUCCESS
    INDEED --> SUCCESS
    UNSUPPORTED --> SUCCESS
    SUCCESS -- "Yes" --> UPDATE_SHEET
    SUCCESS -- "No" --> UPDATE_SHEET
    UPDATE_SHEET --> LOG_DB
    LOG_DB --> EMAIL
    EMAIL --> NEXT_JOB
    NEXT_JOB -- "Yes" --> LOOP_START
    NEXT_JOB -- "No" --> END
```

---

### Status Check Workflow

Runs every N days to detect if recruiters have viewed, rejected, or progressed your applications.

```mermaid
flowchart TD
    TRIGGER2(["⏰ Interval Trigger\nEvery STATUS_CHECK_INTERVAL_DAYS days\n@ STATUS_CHECK_HOUR UTC"])
    READ2["📋 Read Google Sheet\nFilter: Status = 'Applied'"]
    EMPTY2{"Any applied\njobs?"}
    DONE2(["✅ Done — nothing to check"])

    LOOP2(["🔁 For each applied job"])

    PLATFORM{"Job URL\nplatform?"}

    LI_CHECK["🔵 LinkedIn Status Check\n① Login to LinkedIn\n② Navigate to Applied Jobs page\n③ Find card matching company name\n④ Scan card text for status keywords"]

    NO_CHECK["⚪ No automated check\n(keep current status)"]

    DETECT{"Status\nchanged?"}

    UPDATE_BOTH["📊 Update Google Sheet\nStatus column + Last_Checked date"]
    LOG_CHANGE["💾 Log status change\nstatus_changes table"]
    NOTIFY["📧 Email Status Update\n🟢 Interview Scheduled\n🟣 Offer Received\n🔴 Rejected\n🟡 Under Review"]

    UPDATE_DATE["📊 Update Last_Checked only\n(no status change)"]

    NEXT2{{"More jobs\nto check?"}}
    END2(["✅ Status check complete"])

    TRIGGER2 --> READ2
    READ2 --> EMPTY2
    EMPTY2 -- "No" --> DONE2
    EMPTY2 -- "Yes" --> LOOP2
    LOOP2 --> PLATFORM
    PLATFORM -- "linkedin.com" --> LI_CHECK
    PLATFORM -- "other" --> NO_CHECK
    LI_CHECK --> DETECT
    NO_CHECK --> DETECT
    DETECT -- "Yes" --> UPDATE_BOTH
    DETECT -- "No" --> UPDATE_DATE
    UPDATE_BOTH --> LOG_CHANGE
    LOG_CHANGE --> NOTIFY
    NOTIFY --> NEXT2
    UPDATE_DATE --> NEXT2
    NEXT2 -- "Yes" --> LOOP2
    NEXT2 -- "No" --> END2
```

---

## Architecture

### Component Map

Shows how the 9 source modules depend on each other and what external services each touches.

```mermaid
graph LR
    subgraph CLI["CLI Layer"]
        MAIN["main.py\nEntry point + argparse"]
    end

    subgraph CORE["Orchestration Layer"]
        SCHED["scheduler.py\napply_to_jobs()\ncheck_statuses()"]
    end

    subgraph SERVICES["Service Layer"]
        SHEETS["sheets.py\nGoogle Sheets R/W"]
        GMAIL["gmail_notify.py\nGmail send"]
        BROWSER["browser_apply.py\nPlaywright automation"]
        TRACKER["status_tracker.py\nLinkedIn scraper"]
        COVER["cover_letter.py\nJinja2 templating"]
        DB["database.py\nSQLite history"]
    end

    subgraph INFRA["Infrastructure Layer"]
        AUTH["google_auth.py\nOAuth2 credentials"]
        CONFIG["config.py\n.env loader + validation"]
    end

    subgraph EXTERNAL["External Services"]
        GS[("Google\nSheets API")]
        GAPI[("Gmail\nAPI")]
        LI[("LinkedIn.com\nbrowser")]
        IN[("Indeed.com\nbrowser")]
        SQLITE[("job_history.db\nSQLite")]
    end

    MAIN --> SCHED
    MAIN --> DB
    MAIN --> SHEETS
    MAIN --> GMAIL

    SCHED --> SHEETS
    SCHED --> BROWSER
    SCHED --> TRACKER
    SCHED --> COVER
    SCHED --> DB
    SCHED --> GMAIL

    SHEETS --> AUTH
    GMAIL --> AUTH
    SHEETS --> GS
    GMAIL --> GAPI
    BROWSER --> LI
    BROWSER --> IN
    TRACKER --> LI
    DB --> SQLITE

    AUTH --> CONFIG
    SHEETS --> CONFIG
    GMAIL --> CONFIG
    BROWSER --> CONFIG
    TRACKER --> CONFIG
    COVER --> CONFIG
    DB --> CONFIG
```

---

### Data Flow

End-to-end path of data from your Google Sheet to your Gmail inbox.

```mermaid
sequenceDiagram
    participant Sheet as 📋 Google Sheet
    participant Sched as ⏰ Scheduler
    participant Cover as ✍️ Cover Letter
    participant Browser as 🌐 Browser (Playwright)
    participant JobBoard as 💼 Job Board
    participant DB as 💾 SQLite DB
    participant Gmail as 📧 Gmail

    Note over Sched: Weekday 9:00 AM UTC trigger

    Sched->>Sheet: read_jobs(status="Not Applied")
    Sheet-->>Sched: [ {Company, Position, Job_URL, ...}, ... ]

    loop For each job (up to MAX_APPLICATIONS_PER_RUN)
        Sched->>Cover: generate(job)
        Cover-->>Sched: "Dear Hiring Manager, ..."

        Sched->>Browser: apply(job, cover_letter)
        Browser->>JobBoard: Login → Navigate → Fill form → Submit
        JobBoard-->>Browser: Success / CAPTCHA / Error
        Browser-->>Sched: { status, application_id, notes, applied_date }

        Sched->>Sheet: mark_applied(job, result)   [batchUpdate — 1 API call]
        Sched->>DB: log_application(job, result)
        Sched->>Gmail: send_application_email(job, result)
    end

    Note over Sched: Every 2 days @ 10:00 AM UTC

    Sched->>Sheet: read_jobs(status="Applied")
    Sheet-->>Sched: [ {Company, Status, Application_ID, ...}, ... ]

    loop For each applied job (up to MAX_STATUS_CHECKS_PER_RUN)
        Sched->>Browser: check_job_status(job)
        Browser->>JobBoard: Login → Applied Jobs page → Find card → Read status
        JobBoard-->>Browser: Page HTML
        Browser-->>Sched: { new_status, check_date, notes }

        Sched->>Sheet: mark_status_changed(job, new_status, check_date)

        alt Status changed
            Sched->>DB: log_status_change(job, old, new)
            Sched->>Gmail: send_status_update_email(job, old, new)
        end
    end
```

---

## Job Status Lifecycle

A job moves through these states, driven by agent actions or manual edits.

```mermaid
stateDiagram-v2
    direction LR

    [*] --> NotApplied : You add job to Sheet

    NotApplied --> Applied : Agent submits application\n(apply workflow)
    NotApplied --> Failed : Browser error /\nunsupported platform

    Failed --> NotApplied : You fix URL\nand reset status manually

    Applied --> UnderReview : Status check detects\n"viewed" / "under review"
    Applied --> Rejected : Status check detects\n"rejected"
    Applied --> InterviewScheduled : Status check detects\n"interview" / "assessment"
    Applied --> Withdrawn : You withdraw manually

    UnderReview --> InterviewScheduled : Status check update
    UnderReview --> Rejected : Status check update

    InterviewScheduled --> OfferReceived : Status check detects\n"offer"
    InterviewScheduled --> Rejected : Status check update

    OfferReceived --> [*] : Archive row
    Rejected --> [*] : Archive row
    Withdrawn --> [*] : Archive row

    note right of NotApplied
        Agent reads rows
        with this status
        every weekday
    end note

    note right of Applied
        Agent checks rows
        with this status
        every 2 days
    end note
```

---

## Scheduler Timeline

How the two workflows interleave across a typical work week.

```mermaid
gantt
    title Job Agent — Typical Week (UTC)
    dateFormat  YYYY-MM-DD HH:mm
    axisFormat  %a %H:%M

    section Apply Workflow
    Monday apply run        :milestone, m1, 2026-02-23 09:00, 0m
    Tuesday apply run       :milestone, m2, 2026-02-24 09:00, 0m
    Wednesday apply run     :milestone, m3, 2026-02-25 09:00, 0m
    Thursday apply run      :milestone, m4, 2026-02-26 09:00, 0m
    Friday apply run        :milestone, m5, 2026-02-27 09:00, 0m

    section Status Check Workflow
    Status check (day 1)    :milestone, s1, 2026-02-23 10:00, 0m
    Status check (day 3)    :milestone, s2, 2026-02-25 10:00, 0m
    Status check (day 5)    :milestone, s3, 2026-02-27 10:00, 0m

    section You Receive
    Email notifications     :active, e1, 2026-02-23 09:01, 2026-02-27 17:00
```

---

## Google Sheet Schema

The agent reads from and writes to a sheet tab named **`Jobs`** (exact spelling).

```
┌─────┬───────────┬──────────────────┬──────────────────┬─────────────┬──────────────┬──────────────────────┬──────────────────────────┬────────────────────────────────────┬──────────┐
│  A  │     B     │        C         │        D         │      E      │      F       │          G           │            H             │                 I                  │    J     │
├─────┼───────────┼──────────────────┼──────────────────┼─────────────┼──────────────┼──────────────────────┼──────────────────────────┼────────────────────────────────────┼──────────┤
│ ID  │  Company  │    Position      │     Status       │Applied_Date │ Last_Checked │   Application_ID     │          Notes           │              Job_URL               │ Priority │
├─────┼───────────┼──────────────────┼──────────────────┼─────────────┼──────────────┼──────────────────────┼──────────────────────────┼────────────────────────────────────┼──────────┤
│ 001 │ Acme Corp │ Software Eng.    │ Not Applied      │             │              │                      │                          │ https://linkedin.com/jobs/view/123 │ High     │
│ 002 │ Beta Ltd  │ Product Manager  │ Applied          │ 2026-02-20  │ 2026-02-22   │ AUTO_20260220091532  │ Submitted via Easy Apply │ https://indeed.com/j/abc456        │ Medium   │
│ 003 │ Gamma Inc │ Data Scientist   │ Under Review     │ 2026-02-18  │ 2026-02-22   │ AUTO_20260218091104  │ Status checked via LI    │ https://linkedin.com/jobs/view/789 │ High     │
└─────┴───────────┴──────────────────┴──────────────────┴─────────────┴──────────────┴──────────────────────┴──────────────────────────┴────────────────────────────────────┴──────────┘
```

### Column Reference

| Col | Name | Set By | Description |
|-----|------|--------|-------------|
| A | `Job_ID` | You | Unique ID you assign (e.g. `001`, `acme-swe`) |
| B | `Company` | You | Company name — used in cover letter and email subject |
| C | `Position` | You | Job title — used in cover letter |
| D | `Status` | Agent + You | `Not Applied` → `Applied` → `Under Review` → ... |
| E | `Applied_Date` | Agent | Set automatically when the application is submitted |
| F | `Last_Checked` | Agent | Updated on every status-check pass |
| G | `Application_ID` | Agent | Platform reference ID (e.g. `AUTO_20260220091532`) |
| H | `Notes` | Agent | Auto-filled with apply result or status check notes |
| I | `Job_URL` | You | Full LinkedIn or Indeed job URL |
| J | `Priority` | You | `High` / `Medium` / `Low` — informational only |

### Valid Status Values

```
Not Applied  →  Applied  →  Under Review  →  Interview Scheduled  →  Offer Received
                                          ↘                        ↘
                                           Rejected                 Rejected
                                           Withdrawn
```

---

## Configuration Reference

Copy `.env.example` to `.env` and fill in your values.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_SHEET_ID` | ✅ | — | Sheet ID from the Google Sheets URL |
| `USER_EMAIL` | ✅ | — | Your Gmail address (send + receive notifications) |
| `GOOGLE_CREDENTIALS_PATH` | | `credentials.json` | Path to your OAuth2 credentials file |
| `RESUME_LOCAL_PATH` | ✅ | — | Absolute path to your resume PDF |
| `RESUME_URL` | | `""` | Google Drive link to resume (informational) |
| `LINKEDIN_EMAIL` | For LinkedIn | `""` | LinkedIn login email |
| `LINKEDIN_PASSWORD` | For LinkedIn | `""` | LinkedIn password |
| `INDEED_EMAIL` | For Indeed | `""` | Indeed login email |
| `INDEED_PASSWORD` | For Indeed | `""` | Indeed password |
| `APPLY_HOUR` | | `9` | Hour to run apply workflow (UTC, 0–23) |
| `APPLY_MINUTE` | | `0` | Minute to run apply workflow (0–59) |
| `STATUS_CHECK_INTERVAL_DAYS` | | `2` | Days between status checks (≥ 1) |
| `STATUS_CHECK_HOUR` | | `10` | Hour to run status checks (UTC, 0–23) |
| `MAX_APPLICATIONS_PER_RUN` | | `5` | Max jobs applied per daily run |
| `MAX_STATUS_CHECKS_PER_RUN` | | `20` | Max jobs checked per status-check run |
| `DRY_RUN` | | `false` | `true` = log only, never actually apply |

---

## CLI Commands

```
python main.py                    Start the continuous scheduler (normal mode)
python main.py --dry-run          Same, but never submit — logs what it would do
python main.py --run-now          Apply to pending jobs right now (skip schedule)
python main.py --check-now        Check all applied job statuses right now
python main.py --test-email       Send a test email to verify Gmail is working
python main.py --list-jobs        Print all pending jobs from the sheet and exit
```

Flags can be combined:
```
python main.py --dry-run --run-now    # safe preview of what apply would do
python main.py --dry-run --check-now  # safe preview of what status check would do
```

---

## Project Structure

```
Job-Agent/
│
├── main.py                    CLI entry point — argument parsing + startup
├── scheduler.py               Two workflow functions + APScheduler setup
├── config.py                  All settings loaded from .env, with validation
│
├── sheets.py                  Google Sheets read/write (batchUpdate for atomic writes)
├── gmail_notify.py            Gmail API — application + status update emails
├── browser_apply.py           Playwright automation — LinkedIn & Indeed apply flows
├── status_tracker.py          LinkedIn Applied Jobs page scraper
├── cover_letter.py            Jinja2 cover letter renderer
├── database.py                SQLite history log (applications + status_changes)
├── google_auth.py             Shared OAuth2 credential loader (used by sheets + gmail)
│
├── cover_letter_template.txt  ← Edit this with your personal cover letter
├── sheet_template.csv         Import into Google Sheets to create the Jobs tab
├── .env.example               Copy to .env and fill in your credentials
│
├── requirements.txt
├── Procfile                   Heroku/Railway worker process definition
├── railway.toml               Railway.app deployment config
├── nixpacks.toml              Build config (Chromium system deps)
├── start.py                   Railway startup — writes secrets from env to disk
│
├── SETUP.md                   Step-by-step setup guide
│
└── tests/
    ├── conftest.py            Shared fixtures, env stubs, DB isolation
    ├── test_cover_letter.py   Cover letter generation tests
    ├── test_database.py       SQLite log tests
    └── test_sheets.py         Google Sheets integration tests (mocked)
```

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt
playwright install chromium

# 2. Configure
cp .env.example .env
# Edit .env with your Google Sheet ID, email, resume path, and job board credentials

# 3. First-run auth (opens browser for Google OAuth)
python main.py --list-jobs

# 4. Dry run — see what would happen without applying
python main.py --dry-run --run-now

# 5. Start the scheduler
python main.py
```

See **[SETUP.md](SETUP.md)** for the full step-by-step guide including Google Cloud setup.

---

## Local Database

The agent keeps a permanent local history in `job_history.db` (SQLite).

**`applications` table** — one row per application attempt:

```
id | job_id | company | position | platform | status | application_id | notes | applied_at | created_at
```

**`status_changes` table** — one row per detected status change:

```
id | job_id | company | position | old_status | new_status | changed_at | created_at
```

This gives you a full audit trail even if you modify the Google Sheet manually.

---

## Cover Letter Customisation

Edit `cover_letter_template.txt`. Available Jinja2 variables:

| Variable | Default | Source |
|----------|---------|--------|
| `{{ company }}` | `"the company"` | Sheet: Company column |
| `{{ position }}` | `"the position"` | Sheet: Position column |
| `{{ applicant_name }}` | `"Your Name"` | Set in template or `extra_context` |
| `{{ skills }}` | `"software development"` | Set in template or `extra_context` |

Example template:
```
Dear Hiring Manager at {{ company }},

I am excited to apply for the {{ position }} role. With my background in
{{ skills }}, I am confident I can contribute meaningfully to your team.

Best regards,
{{ applicant_name }}
```

---

## Supported Platforms

| Platform | Apply | Status Check | Notes |
|----------|-------|--------------|-------|
| **LinkedIn** | ✅ Easy Apply | ✅ Applied Jobs page | Non-headless: CAPTCHA can be solved manually |
| **Indeed** | ✅ Indeed Apply | ❌ Not yet implemented | Two-step login handled automatically |
| **Other** | ❌ Skip + log | ❌ N/A | Returns `Failed` result; apply manually |

---

## Security Notes

- `credentials.json`, `.env`, and `token.json` are in `.gitignore` — they are never committed
- All Google API calls use OAuth2 with the minimum required scopes (Sheets + Gmail send only)
- The SQLite database (`job_history.db`) stays on your machine
- Passwords are stored only in your local `.env` file; nothing is sent to third parties
- For deployment to Railway/Heroku, credentials are passed as environment variables (not files)

---

## Running Tests

```bash
pytest tests/ -v
```

All 12 tests run without real Google credentials or a browser — everything external is mocked.

---

## Deployment (Railway / Heroku)

Set these environment variables in your Railway/Heroku dashboard (instead of `.env`):

- All variables from the [Configuration Reference](#configuration-reference) above
- `GOOGLE_CREDENTIALS_JSON` — paste the full contents of `credentials.json`
- `GOOGLE_TOKEN_JSON` — paste the full contents of `token.json` (generated on first local run)

The `start.py` script writes these to disk before launching `main.py`.

---

*Built as a free alternative to n8n job automation workflows. No subscriptions, no cloud, no scraping APIs.*
