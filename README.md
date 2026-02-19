# Job Application Agent 🤖

A free, self-hosted Python agent that automates job applications — no n8n, no subscriptions.

## Features
- 📋 Reads job listings from **Google Sheets**
- 🤖 Applies via **LinkedIn Easy Apply** and **Indeed** (Playwright browser automation)
- ✉️ Personalised **cover letters** per application (Jinja2 template)
- 📧 **Gmail notifications** on every application and status change
- 🔍 **Status tracking** every 2 days
- 💾 Full **SQLite history log** locally
- ⏰ **APScheduler** — cron-like triggers, no cloud required

## Quick Start

```powershell
pip install -r requirements.txt
playwright install chromium
copy .env.example .env   # fill in your values
python main.py --dry-run --run-now   # test without applying
python main.py           # start the scheduler
```

See **[SETUP.md](SETUP.md)** for full configuration instructions.

## Project Structure

```
Job agent/
├── main.py                   # Entry point + CLI
├── scheduler.py              # APScheduler workflows
├── config.py                 # Settings from .env
├── sheets.py                 # Google Sheets read/write
├── gmail_notify.py           # Gmail API notifications
├── browser_apply.py          # Playwright automation
├── status_tracker.py         # Status check logic
├── cover_letter.py           # Jinja2 cover letter generator
├── database.py               # SQLite history log
├── cover_letter_template.txt # Edit this!
├── sheet_template.csv        # Import into Google Sheets
├── .env.example              # Copy to .env and configure
├── requirements.txt
├── SETUP.md                  # Step-by-step setup guide
└── tests/
    ├── test_cover_letter.py
    ├── test_database.py
    └── test_sheets.py
```

## CLI Commands

| Command | Description |
|---|---|
| `python main.py` | Start the continuous scheduler |
| `python main.py --dry-run --run-now` | Preview without applying |
| `python main.py --run-now` | Apply to pending jobs now |
| `python main.py --check-now` | Check all applied job statuses |
| `python main.py --test-email` | Verify Gmail setup |
| `python main.py --list-jobs` | Print pending jobs |
