<p align="center">
  <img src="static/img/logo.png" alt="Tender Monitor" width="320">
</p>

<h1 align="center">Tender Monitor</h1>

<p align="center"><em>Find &middot; Track &middot; Stay Ahead.</em><br>
Automatically monitor government e-procurement tenders on your own Windows computer.</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-blue.svg">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg">
  <img alt="Tests" src="https://img.shields.io/badge/Tests-69%20passing-brightgreen.svg">
  <img alt="Status" src="https://img.shields.io/badge/Status-Active-success.svg">
</p>

<p align="center">
  Made by <strong>Ganguly B (Shavarna)</strong> &middot;
  <a href="mailto:enlaceet@gmail.com">enlaceet@gmail.com</a> &middot;
  WhatsApp <a href="https://wa.me/919073288770">+91-9073288770</a>
</p>

---

A local Windows application that monitors **any publicly accessible tender /
e-procurement website** you configure. You supply the URL and a schedule;
Tender Monitor visits the site, discovers tender listings, detects **new** and
**updated** tenders since the last scan, downloads publicly available documents,
keeps a full local history in SQLite, and produces professional Excel reports.

It runs entirely on your own computer. Nothing is deployed to a web server; the
dashboard is served locally at **http://127.0.0.1:8000**.

> Tender Monitor is a **general** monitor, not a scraper hard-coded for one
> portal. A generic engine tries to understand each site you add and clearly
> reports when a site is `SUPPORTED`, `PARTIALLY SUPPORTED`, `CAPTCHA REQUIRED`,
> `LOGIN REQUIRED`, `BLOCKED`, `SITE UNAVAILABLE`, or `STRUCTURE NOT DETECTED`.
> It never bypasses CAPTCHA, logins, or anti-bot controls.

---

## Key features

- Add unlimited tender portals through the UI (URL, schedule, keywords, filters).
- Daily / Weekly / Manual scheduling, editable at any time, surviving restarts.
- Generic engine (Playwright + BeautifulSoup) that discovers tables, cards,
  pagination, detail links and documents without site-specific code.
- **NEW** and **UPDATED** tender detection with a first-scan **baseline** so you
  are not flooded on day one.
- Field-level change history (e.g. "CLOSING DATE EXTENDED") stored per tender.
- Safe-scan guard: a sudden collapse in results is flagged as a possible portal
  structure change and previous data is preserved (never silently wiped).
- Public document download (PDF/DOC/XLS/ZIP...) with SHA-256, size limits and
  strict safety checks. Executables are never downloaded.
- 9-sheet Excel report with frozen headers, filters, hyperlinks and formatting.
- Keyword / negative-keyword / value / location filtering and a 0-100 relevance
  score (HIGH / MEDIUM / LOW).
- Optional email (SMTP) daily summaries.
- Command-line mode for unattended runs via Windows Task Scheduler.
- SSRF-conscious safety, parameterised SQL, filename sanitisation.

## Requirements

- Windows 10 or 11
- Python 3.12 or newer (`python --version`)
- ~300 MB free disk space (mostly the Playwright Chromium browser)
- Internet access to the portals you want to monitor

## Installation (Windows 10 / 11)

1. Install Python 3.12+ from https://www.python.org/downloads/ and tick
   **"Add Python to PATH"** during setup.
2. Download / copy this project folder somewhere convenient
   (for example `D:\Tender Monitor`).
3. Double-click **`install.bat`**. It will:
   create a virtual environment, install dependencies, install the Playwright
   Chromium browser, create the data folders and initialise the SQLite database.
4. When it finishes, double-click **`start.bat`** and open
   **http://127.0.0.1:8000** (it opens automatically).

That is the whole setup. All data lives under the local `data\` folder.

## Quick start

1. `start.bat` -> open http://127.0.0.1:8000
2. Click **Add Portal**, fill in the form (see below), click **Test Portal** to
   check the site, then **Save Portal**.
3. On the dashboard click **Run All Now** (or, on the Portals page, **Scan** a
   single portal). The **first scan is a baseline** - existing tenders are
   recorded but not reported as NEW.
4. Run again later. From then on, genuinely new tenders show as **NEW** and
   changed ones as **UPDATED**.
5. Click **Download Excel** any time for a full report.

## Using the dashboard

- **Dashboard** - totals, portals needing attention, new/updated counts,
  documents downloaded, last successful scan, next scheduled scan, recent errors
  and notifications, plus the action buttons.
- **Portals** - list of configured portals with health, next run and actions
  (Edit, **Clone**, Scan, Enable/Disable, Delete). **Clone** copies every setting
  into a new portal and opens its edit page so you only change the name and URL -
  handy for monitoring several NIC state portals with the same keywords/filters.
- **Tenders** - searchable/filterable list; click a tender for full detail,
  documents and change history. Filter by portal, keyword, organisation,
  location, status, relevance, value and **published-date range**. Two quick
  views answer "what came in today": **New today** (tenders first seen today, in
  your timezone) and **Published today** (the portal's e-Published date is
  today). The Tenders list shows only **active** tenders so it stays focused. To
  clear the pile after reviewing/downloading: **Archive reviewed** (archives
  unchanged tenders, keeps New and Updated), **Archive all**, or **Archive** a
  single row. A changed tender automatically returns to the active list on the
  next scan, so updates are never missed. Every archive action reports how many
  it moved.
- **Archive** - old/processed tenders moved out of the main list. Same filters;
  **Restore** any row or **Restore all**. Excel export and the dashboard new/
  updated counts cover the active list only.
- **Scan History** - every scan with pages, found/new/updated/documents/errors
  and status; click a row for details.
- **Settings** - timezone and optional email (SMTP) configuration.

### Add Portal - fields

| Field | Meaning |
|-------|---------|
| Portal Name | Any label you choose |
| Website URL | The tender listing page (http/https) |
| Monitoring | Enabled / Disabled |
| Schedule | Daily / Weekly / Manual |
| Run Time | HH:MM (for Daily/Weekly) |
| Day of Week | Used for Weekly only |
| Keywords | Comma-separated (e.g. `water, pipeline, WTP, STP, JJM`) |
| Negative Keywords | Comma-separated exclusions (e.g. `vehicle, canteen`) |
| Keyword Mode | Match ANY or ALL keywords |
| Location Filter | Optional text match |
| Min / Max Tender Value | Optional numeric range |
| Download Documents | Yes / No |
| Maximum Pages | Pagination limit per scan |
| Delay Between Requests | Politeness delay (seconds) |
| Browser Mode | Headless or Visible (for debugging) |
| First Scan Handling | Default baseline, or treat first scan as NEW |
| Follow Detail Pages | Optionally enrich records from detail pages |

### Test Portal

`Test Portal` launches a real browser against the URL and reports whether the
site is reachable, whether HTTPS works, whether a listing / pagination / detail
pages / tender IDs / dates / values / documents were detected, and whether a
CAPTCHA or login is in the way. It ends with an **Automation Readiness** verdict
(`GOOD`, `PARTIALLY SUPPORTED`, `CAPTCHA REQUIRED`, `LOGIN REQUIRED`, `BLOCKED`,
`SITE UNAVAILABLE`, or `STRUCTURE NOT DETECTED`). It never bypasses protections.

## Command line

The virtual environment Python is at `.venv\Scripts\python.exe`.

```
.venv\Scripts\python.exe main.py --server            Start the dashboard
.venv\Scripts\python.exe main.py --scan              Scan all enabled portals
.venv\Scripts\python.exe main.py --scan-portal 1     Scan one portal by id
.venv\Scripts\python.exe main.py --export            Generate the Excel report
.venv\Scripts\python.exe main.py --test-portal 1     Test a configured portal
.venv\Scripts\python.exe main.py --status            Print a status summary
```

Exit codes: `0` success, `1` completed with some portal failures, `2` fatal /
bad usage.

## Scheduling

Two independent mechanisms:

1. **In-application scheduler** (APScheduler) runs while the dashboard is open,
   using each portal's Daily/Weekly time. Schedules are stored in SQLite and
   restored on restart.
2. **Windows Task Scheduler** (recommended for unattended use) runs scans even
   when the dashboard is closed. Double-click **`setup_scheduler.bat`**, enter a
   time, and it creates a `TenderMonitorDaily` task that runs `run_scan.bat`
   (`python main.py --scan`). Remove it with
   `schtasks /Delete /TN TenderMonitorDaily /F`.

## How detection works

- **Identity**: each tender is keyed by Portal + Tender ID, else Portal +
  Reference, else a fingerprint hashed from title + organisation + published date
  + detail URL + location. Title alone is never used.
- **Baseline**: the first successful scan of a new portal records everything as
  existing (unless you tick *Treat first scan as NEW*).
- **NEW**: a tender whose key was not seen before.
- **UPDATED**: an existing tender where a monitored field changed (title, value,
  EMD, fee, published/closing/opening dates, eligibility, work period,
  organisation, location, category, document links). Each change is stored in the
  tender's history with a type such as `CLOSING DATE EXTENDED`.
- **Safe-scan**: if results collapse (e.g. 500 -> 3) the scan is marked
  `partial`, a warning is raised, and previously stored tenders are preserved.

## Documents

When *Download Documents* is on, publicly linked files (PDF, DOC/DOCX, XLS/XLSX,
PPT/PPTX, ZIP, etc.) for NEW and UPDATED matching tenders are saved under
`data\downloads\<Portal>\<Tender ID>\`. Each file records name, URL, local path,
size, SHA-256 and status. Unchanged files are not re-downloaded. Executables are
never downloaded, filenames are sanitised, and a size limit is enforced.

## Security

The app accepts arbitrary URLs, so it validates every outbound request:
http/https only, no `file://`, and localhost / private / reserved IP ranges are
blocked by default (SSRF protection - set `TENDER_MONITOR_ALLOW_PRIVATE_HOSTS=1`
only for the bundled mock server or a trusted intranet). SQL is parameterised,
HTML output is escaped by Jinja2, downloads are size-limited and never executed,
and SMTP passwords are stored locally and never written to logs.

## Try it with the bundled mock portal

No real site needed to see the full flow:

```
set TENDER_MONITOR_ALLOW_PRIVATE_HOSTS=1
.venv\Scripts\python.exe tools\serve_mock.py
```

Then add a portal with URL `http://127.0.0.1:8899/tenders`, scan it (baseline),
open `http://127.0.0.1:8899/switch` to change/add tenders, and scan again to see
UPDATED and NEW detection plus a downloaded document.

## Project structure

```
Tender Monitor/
  app.py                  FastAPI dashboard + JSON API
  main.py                 Command-line entry point
  config.py               Technical settings / paths (no secrets)
  requirements.txt
  install.bat start.bat stop.bat run_scan.bat setup_scheduler.bat
  database/               database.py, models.py, migrations.py (SQLite)
  scraper/                base, generic, browser, parser, discovery,
                          downloader, portal_detector, registry
  scheduler/              scheduler.py (APScheduler)
  reports/                excel_exporter.py (9-sheet report)
  services/               tender_service, change_detector, scan_service,
                          notification_service
  templates/              Jinja2 HTML (dashboard, portals, tenders, ...)
  static/                 css/ and js/
  tools/serve_mock.py     Bundled mock tender portal for testing
  tests/                  pytest suite + mock HTML pages
  data/                   tender_monitor.db, downloads/, reports/, logs/
```

The adapter architecture (`scraper/base.py`, `scraper/registry.py`) lets you add
a dedicated portal adapter later without touching the database, scheduler,
reporting or dashboard code. The generic adapter is the default.

## Configuration (.env - optional)

Portal settings live in the UI/database. `.env` is only for technical overrides
(host/port, data directory, limits, timezone default, private-host allowance).
See `.env.example`.

## Running the tests

```
.venv\Scripts\python.exe -m pytest
```

The suite (offline; never touches live sites) covers database creation, tender
insertion, duplicate detection, fingerprinting, change detection, date/currency
parsing, keyword filtering, Excel generation, the scheduler, filename
sanitisation / SSRF, and a full baseline -> NEW -> UPDATED scan lifecycle.

## Troubleshooting

- **`Python was not found`** - install Python 3.12+ and tick "Add Python to
  PATH", then re-run `install.bat`.
- **Playwright / browser errors** - run
  `.venv\Scripts\python.exe -m playwright install chromium`.
- **Port 8000 already in use** - set `TENDER_MONITOR_PORT=8010` in `.env`, or run
  `main.py --server --port 8010`.
- **A portal reports CAPTCHA REQUIRED / LOGIN REQUIRED** - that site cannot be
  automated without defeating a protection, which this tool will not do.
- **Results suddenly dropped / scan marked `partial`** - the site layout may have
  changed. Your previous data is preserved; open the portal and re-Test it.
- **Scheduled task did not run** - confirm the `TenderMonitorDaily` task in
  Windows Task Scheduler and that the machine was on; check `data\logs\`.
- **Logs** - `data\logs\app.log`, `scanner.log`, `errors.log`; failed-parse
  diagnostics under `data\logs\portal_diagnostics\`.

## Acceptance checklist

Start app -> add a portal (use the mock portal above) -> set a time -> add
keywords -> Test Portal -> Save -> Scan (baseline) -> Scan again (no duplicates)
-> change mock data -> Scan (UPDATED) -> add a mock tender -> Scan (NEW) ->
Download Excel (9 sheets) -> check documents and logs -> restart the app and
confirm configuration and database persist.

## Limitations

The generic engine supports a wide variety of public portals but cannot scrape
every site. It will not bypass CAPTCHA, logins, OTP, or anti-bot controls, and it
does not determine legal or technical eligibility - the relevance score is a
ranking aid only.

## Version 1 scope / future-ready

SQLite only (no external DB). The design leaves room for future additions
(dedicated portal adapters, PDF text extraction/OCR, AI summaries, Telegram/
WhatsApp alerts) without reworking the core.

## NIC eProcurement portals (GePNIC)

Many Indian government tender sites run the **NIC eProcurement System** under a
`/nicgep/app` URL - for example `eprocure.goa.gov.in`, `wbtenders.gov.in`,
`tenders.wb.gov.in`, and most state / CPPP portals. These are handled
automatically:

- Just add the portal with the site's base URL (e.g.
  `https://eprocure.goa.gov.in/nicgep/app`). The app **auto-detects** NIC portals
  and uses a dedicated adapter - you do not need to find a deep link.
- Their landing page has no tender table; the adapter scans via **Tenders by
  Organisation**, visiting each organisation's tender list (no CAPTCHA involved).
  The free-text "Active Tenders" search is CAPTCHA-protected and is never used.
- Control how many organisations are walked per scan with the portal's
  **Organisations to scan** field on the Add/Edit Portal form (default 60);
  increase it to capture more (each organisation adds a little time). The global
  default can also be set with the `TENDER_MONITOR_NIC_MAX_ORGS` env var.
- Tick **Store only matching tenders** on the form to keep just the tenders that
  match your keywords (and skip your negative keywords), so the database holds
  only what is relevant to your search.
- If a specific NIC site is temporarily returning `503`/blocking automated
  requests from your network, that is the site's WAF, not the app - retry later.

Non-NIC sites (plain HTML tender tables/cards) continue to use the generic
engine, which now also reads tables whose header cells are styled `<td>` rather
than `<th>`.

## Running on macOS / Linux

Tender Monitor is pure cross-platform Python - no code changes are needed. Use
the shell scripts instead of the Windows `.bat` files:

```bash
./install.sh        # one-time setup (venv, dependencies, Chromium, database)
./start.sh          # start the dashboard, then open http://127.0.0.1:8000
./run_scan.sh       # run one scan of all enabled portals
./stop.sh           # stop the dashboard
./setup_cron.sh     # schedule a daily scan with cron
```

If the scripts are not executable yet, run `chmod +x *.sh` once.

Manual commands (equivalent, if you prefer not to use the scripts):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python main.py --server
```

**Scheduling:** macOS / Linux have no Windows Task Scheduler. `setup_cron.sh`
installs a `cron` job (or create a `launchd` agent on macOS). The in-app
scheduler works while the dashboard is open, exactly as on Windows. Everything
else - portals, scanning, Excel reports, the Archive, the About page and update
checks - behaves identically.

## Credits, license & contact

**Tender Monitor** is created and maintained by **Ganguly B (Shavarna)** and is
free, open-source software released under the **MIT License** (see `LICENSE` and
`AUTHORS`). You may use, copy, modify and share it.

- Email: **enlaceet@gmail.com**
- WhatsApp: **+91-9073288770**

Feedback, bug reports and contributions are welcome - please get in touch.

## Getting updates

Open the **About** page (top menu) to see your version and a **Check for updates**
button. When the maintainer publishes a newer version, an "Update available"
banner appears in the app with release notes and a download link.

Maintainers: to notify all users of a new release from one place, see
`docs/PUBLISHING_UPDATES.md` and `docs/update-manifest.example.json`.
