# Contributing to Tender Monitor

Thanks for your interest in improving Tender Monitor. It is free, open-source
software (MIT License) created and maintained by **Ganguly B (Shavarna)**.
Contributions, bug reports and ideas are all welcome.

## Ways to help

- Report a bug or a portal that does not scan correctly.
- Suggest a feature or an improvement.
- Improve the documentation or the user handbook.
- Add support for a new portal type (a new adapter).
- Fix an issue and open a pull request.

## Reporting a bug or requesting a feature

Please include:

- What you did and what you expected to happen.
- What actually happened (copy any error text).
- The portal URL (if relevant) and your Windows version.
- Relevant log lines from `data\logs\` (app.log / scanner.log / errors.log).

You can reach the maintainer directly:

- Email: **enlaceet@gmail.com**
- WhatsApp: **+91-9073288770**

Or open an Issue if the project is hosted on GitHub.

## Developer setup

Requires Python 3.12+ on Windows (works on other OSes for development).

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Run the app:

```bash
.venv\Scripts\python.exe main.py --server
```

Run the test suite (offline; never touches live sites):

```bash
.venv\Scripts\python.exe -m pytest
```

Try the bundled mock portal without any real website:

```bash
set TENDER_MONITOR_ALLOW_PRIVATE_HOSTS=1
.venv\Scripts\python.exe tools\serve_mock.py
```

## Project layout

See `AGENTS.md`-style notes in `README.md` (Project structure section). In short:
`database/` (SQLite), `scraper/` (adapters, parser, browser, downloader),
`services/` (scan/change/tender/notification/update), `scheduler/`, `reports/`
(Excel), `templates/` + `static/` (UI), `tests/` (pytest).

## Coding guidelines

- Keep the test suite green. Add tests for new behaviour.
- Do not commit secrets, API keys, cookies or `.env` files.
- No emoji in source code, comments or commit messages.
- Match the style of the surrounding code; keep changes focused.
- New portal support should be a new adapter under `scraper/` registered in
  `scraper/registry.py`, without changing the database, scheduler or UI code.

## Adding a portal adapter (advanced)

1. Create a class extending `scraper.base.BasePortalAdapter` with a `collect()`
   method returning the standard result dict.
2. Register it in `scraper/registry.py` (and add auto-detection if useful).
3. Add offline tests using mock HTML in `tests/`.

## License

By contributing you agree that your contributions are licensed under the
project's MIT License (see `LICENSE`).
