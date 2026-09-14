# Publishing updates to users (maintainer guide)

Tender Monitor runs on each user's own computer, so there is no central server.
Instead, the app can **check a small JSON file you publish** and show every user
a banner when a newer version is available. You update one file; all users are
notified.

## How it works

1. Each user's app reads the URL in `TENDER_MONITOR_UPDATE_URL` (set in their
   `.env`) on start-up and when they click **Check for updates** on the About page.
2. That URL returns a JSON manifest (see `docs/update-manifest.example.json`).
3. If `latest_version` is newer than the version they have (`config.APP_VERSION`),
   the app shows an "Update available" banner with your notes and a download link.

## One-time setup (per release channel)

1. Put a file named `update.json` somewhere with a **stable public URL**. Easiest
   options:
   - A **GitHub raw** URL, e.g.
     `https://raw.githubusercontent.com/<you>/tender-monitor/main/update.json`
   - Any web page/host you control that returns the JSON.
2. In the `.env` file you ship to users, set:
   ```
   TENDER_MONITOR_UPDATE_URL=https://raw.githubusercontent.com/<you>/tender-monitor/main/update.json
   TENDER_MONITOR_REPO_URL=https://github.com/<you>/tender-monitor
   ```

## Every time you release a new version

1. Bump the version in `config.py` (`APP_VERSION = "1.1.0"`), commit, and publish
   the new code (e.g. a GitHub Release / zip).
2. Edit your hosted `update.json`:
   ```json
   {
     "latest_version": "1.1.0",
     "download_url": "https://github.com/<you>/tender-monitor/releases/latest",
     "notes": "What changed in this version.",
     "message": "Please update when convenient."
   }
   ```
3. That is it. Users see the banner next time they open the app (or click
   **Check for updates**), read your notes, and follow the download link.

## Fields

| Field | Meaning |
|-------|---------|
| `latest_version` | The newest version number, e.g. `1.1.0`. |
| `download_url` | Where users get the update (Releases page, zip, etc.). |
| `notes` | Short "what's new" text shown to users. |
| `message` | Optional extra line (e.g. "Recommended update"). |

Contact: Ganguly B (Shavarna) - enlaceet@gmail.com - WhatsApp +91-9073288770
