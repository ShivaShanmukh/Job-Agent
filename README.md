# 🤖 Job Application Agent

> **Automatically applies to jobs on LinkedIn & Indeed — 24/7, while you sleep.**  
> Deployed on Railway · Powered by Python · No subscriptions needed

---

## ⚡ How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR GOOGLE SHEET                           │
│   Company  │  Position    │  Platform  │  Status               │
│   Google   │  SWE         │  LinkedIn  │  Not Applied  ← You   │
│   Apple    │  iOS Dev     │  Indeed    │  Not Applied  ← add   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼  Every weekday at 9:00 AM UTC
┌─────────────────────────────────────────────────────────────────┐
│                   RAILWAY CLOUD WORKER  🚂                      │
│                                                                 │
│   1. 📋 Reads jobs with status "Not Applied"                   │
│   2. 📝 Generates a personalised cover letter (Jinja2)         │
│   3. 🌐 Opens browser (Playwright) → LinkedIn / Indeed         │
│   4. 🖱️  Clicks through Easy Apply automatically               │
│   5. ✅ Updates sheet status → "Applied"                       │
│   6. 📧 Sends you a Gmail notification                         │
│   7. 💾 Logs everything to SQLite database                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
            YOUR GMAIL              GOOGLE SHEET
         📧 "Applied to           Status updated
          Google — SWE"           to ✅ Applied
```

---

## 🗂️ Project Structure

```
Job-Agent/
│
├── 🚀 start.py               → Railway entry point (writes secrets to disk)
├── ⚙️  main.py                → CLI + scheduler launcher
├── 📅 scheduler.py           → Cron jobs (apply daily, check every 2 days)
│
├── 🔧 Core Modules
│   ├── config.py             → Loads all settings from env vars
│   ├── sheets.py             → Read/write Google Sheets
│   ├── browser_apply.py      → Playwright automation (LinkedIn & Indeed)
│   ├── cover_letter.py       → Personalised cover letter generator
│   ├── gmail_notify.py       → Gmail API email notifications
│   ├── status_tracker.py     → Checks if application status changed
│   └── database.py           → SQLite history log
│
├── 📄 Config
│   ├── .env.example          → Copy this to .env and fill in values
│   ├── cover_letter_template.txt → Edit your cover letter here!
│   └── sheet_template.csv    → Import this into Google Sheets
│
└── 🐳 Deployment
    ├── Dockerfile            → Railway build (Python + Playwright)
    └── railway.toml          → Railway deploy config
```

---

## 🛠️ Setup Guide

### Step 1 — Clone & Install

```bash
git clone https://github.com/ShivaShanmukh/Job-Agent.git
cd Job-Agent
pip install -r requirements.txt
playwright install chromium
```

### Step 2 — Configure Your `.env`

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Mac/Linux
```

Then edit `.env` with your personal values:

| Variable | What to put |
|---|---|
| `GOOGLE_SHEET_ID` | The long ID from your Google Sheet URL |
| `USER_EMAIL` | Your Gmail address |
| `LINKEDIN_EMAIL` | Your LinkedIn login |
| `LINKEDIN_PASSWORD` | Your LinkedIn password |
| `INDEED_EMAIL` | Your Indeed login |
| `INDEED_PASSWORD` | Your Indeed password |
| `RESUME_LOCAL_PATH` | Full path to your resume PDF |
| `DRY_RUN` | `true` for testing, `false` to actually apply |

### Step 3 — Set Up Google (one time)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Sheets API** and **Gmail API**
3. Create **OAuth 2.0 Desktop credentials** → download as `credentials.json`
4. Place `credentials.json` in the project folder
5. Run once: `python main.py --test-email` — this opens a browser to authorize

See **[SETUP.md](SETUP.md)** for detailed step-by-step instructions.

### Step 4 — Add Jobs to Your Sheet

Import `sheet_template.csv` into Google Sheets, then add rows like:

| Company | Position | Platform | Status | Priority |
|---|---|---|---|---|
| Google | SWE | LinkedIn | Not Applied | High |
| Apple | iOS Dev | Indeed | Not Applied | Medium |

---

## 🖥️ Run Locally

```bash
# Test without applying anything (safe)
python main.py --dry-run --run-now

# Apply to pending jobs right now
python main.py --run-now

# Start the continuous 24/7 scheduler
python main.py

# Other useful commands
python main.py --list-jobs      # See pending jobs
python main.py --check-now      # Check application statuses
python main.py --test-email     # Verify Gmail works
```

---

## 🚂 Deploy to Railway (Cloud)

The agent runs 24/7 on [Railway](https://railway.app) — no need to keep your computer on.

### Required Railway Environment Variables

Go to Railway → your service → **Variables** tab and add:

| Variable | Value |
|---|---|
| `GOOGLE_SHEET_ID` | Your sheet ID |
| `USER_EMAIL` | Your Gmail |
| `LINKEDIN_EMAIL` / `LINKEDIN_PASSWORD` | Your credentials |
| `INDEED_EMAIL` / `INDEED_PASSWORD` | Your credentials |
| `DRY_RUN` | `true` to test, `false` to go live |
| `GOOGLE_CREDENTIALS_JSON` | Paste full contents of `credentials.json` |
| `GOOGLE_TOKEN_JSON` | Paste full contents of `token.json` |
| `RESUME_URL` | Google Drive share link to your resume PDF |

Railway will auto-deploy on every push to `main`. ✅

---

## 📅 Schedule

| Job | When |
|---|---|
| Apply to new jobs | Weekdays at **9:00 AM UTC** |
| Check application statuses | Every **2 days** at 10:00 UTC |

Change `APPLY_HOUR`, `APPLY_MINUTE`, `STATUS_CHECK_INTERVAL_DAYS` in your env vars to customise.

---

## 📧 What You Get in Your Inbox

Every time the agent applies to a job, you get an email like:

```
Subject: Job Application: Google — Software Engineer

📋 Job Application Update
─────────────────────────────
Company      │ Google
Position     │ Software Engineer  
Status       │ ✅ Applied
Platform     │ LinkedIn
Date         │ 2026-02-23

Sent by your Job Application Agent 🤖
```

---

## 🔒 Security

- Credentials are **never committed to git** (`.gitignore` protects them)
- On Railway, secrets are stored as encrypted environment variables
- `start.py` writes credentials to disk at runtime from env vars

---

Built with Python · Playwright · Google APIs · APScheduler · Railway
