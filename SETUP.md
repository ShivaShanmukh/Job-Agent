# Setup Guide — Job Application Agent

## Prerequisites

- **Python 3.11+** installed ([python.org](https://python.org))
- A **Google account** (Gmail + Google Sheets)
- Your **resume** as a PDF stored locally

---

## Step 1 — Install Dependencies

```powershell
cd "d:\Job agent"
pip install -r requirements.txt
playwright install chromium
```

---

## Step 2 — Set Up Google Cloud (one-time, ~5 minutes)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **"New Project"** → name it `job-agent` → **Create**
3. In the search bar, search **"Google Sheets API"** → click **Enable**
4. Search **"Gmail API"** → click **Enable**
5. Go to **APIs & Services → Credentials**
6. Click **"+ Create Credentials"** → **"OAuth client ID"**
7. Application type: **Desktop app** → name it anything → **Create**
8. Click **Download JSON** → save the file as `credentials.json` inside `d:\Job agent\`

> **First run only:** A browser window will open asking you to sign in with Google and grant access. After that, a `token.json` is saved and logins are automatic.

---

## Step 3 — Create Your Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) → **Create blank spreadsheet**
2. Name the first tab/sheet: **Jobs** (exact spelling matters)
3. Import `sheet_template.csv` via **File → Import** to get the right column headers
4. Copy the **Sheet ID** from the URL:  
   `https://docs.google.com/spreadsheets/d/`**`THIS_IS_YOUR_SHEET_ID`**`/edit`

---

## Step 4 — Configure the Agent

```powershell
copy .env.example .env
notepad .env
```

Fill in all fields — at minimum:

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_SHEET_ID` | ✅ | From Step 3 |
| `USER_EMAIL` | ✅ | Your Gmail address |
| `RESUME_LOCAL_PATH` | ✅ | Full path to your resume PDF |
| `LINKEDIN_EMAIL` | For LinkedIn jobs | Your LinkedIn login email |
| `LINKEDIN_PASSWORD` | For LinkedIn jobs | Your LinkedIn password |
| `INDEED_EMAIL` | For Indeed jobs | Your Indeed login email |
| `INDEED_PASSWORD` | For Indeed jobs | Your Indeed password |

---

## Step 5 — Customise Your Cover Letter

Open `cover_letter_template.txt` and write your personal cover letter.  
Use `{{ position }}`, `{{ company }}`, `{{ skills }}`, `{{ applicant_name }}` as placeholders.

---

## Step 6 — Test Everything

```powershell
# 1. Run unit tests (no credentials needed)
python -m pytest tests/ -v

# 2. Test Gmail connection
python main.py --test-email

# 3. List pending jobs from your sheet
python main.py --list-jobs

# 4. Dry run (see what would happen, no actual applications)
python main.py --dry-run --run-now

# 5. Apply to 1-2 real jobs manually first to test
python main.py --run-now
```

---

## Step 7 — Run Continuously

```powershell
python main.py
```

The agent will:
- ✅ **Apply every weekday at 9:00 AM UTC** (configurable)
- ✅ **Check statuses every 2 days at 10:00 AM UTC** (configurable)
- ✅ **Send you email notifications** for every action
- ✅ **Log everything** to `agent.log` and `job_history.db`

---

## Google Sheet Column Reference

| Column | Name | Description |
|---|---|---|
| A | Job_ID | Unique identifier (you assign) |
| B | Company | Company name |
| C | Position | Job title |
| D | Status | `Not Applied` → `Applied` → `Under Review` etc. |
| E | Applied_Date | Set automatically when applied |
| F | Last_Checked | Updated every status check |
| G | Application_ID | Platform reference ID |
| H | Notes | Auto-filled notes |
| I | Job_URL | LinkedIn or Indeed URL |
| J | Priority | High / Medium / Low |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Missing env variable` error | Check `.env` has all required values |
| Google login browser doesn't open | Run in a non-headless terminal (not VS Code terminal) |
| LinkedIn CAPTCHA blocks login | Set `headless=False` in `browser_apply.py` (already done) and solve it manually |
| Email not sending | Run `--test-email` and check Gmail API is enabled in Cloud Console |
| Job not found in sheet | Make sure the sheet tab is named exactly `Jobs` |

---

## Maintaining Your Sheet Over Time

As you apply to more jobs, your Google Sheet will accumulate rows with terminal statuses
(`Rejected`, `Offer Received`, `Withdrawn`). The agent reads all rows every run, so
performance stays predictable if you periodically archive completed rows:

1. Create a second sheet tab named **Archive** in the same spreadsheet.
2. Move rows with terminal statuses there (cut → paste) once a month or so.
3. Keep the **Jobs** tab focused on active applications (Not Applied, Applied, Under Review, Interview Scheduled).

This keeps the Jobs tab lean and avoids reading stale data on every run.

---

## Security Notes

- ✅ Credentials stored in `.env` (local only, never shared)
- ✅ Google OAuth tokens stored in `token.json` (local only)
- ✅ Never commit `.env` or `credentials.json` to Git — the `.gitignore` handles this
