# Working on this repo

- This repo is public. It holds code only. Never commit credentials, tokens, keys, bill PDFs, energy data, `dashboard_*.json`, `config.json`, addresses, account numbers, VINs, device or system IDs, or payment amounts. `.gitignore` covers the usual paths; check `git status` before every commit anyway.
- The owner's working copy lives outside the repo (scripts at the top of a local folder, with `tesla_api/` and `energy_data/` beside them). When a script changes there, copy the change here, run a privacy scan of the diff, then commit and push.
- Every script is read-only toward devices. Nothing here may change Tesla, Powerwall, water heater or solar settings.
- Keep scripts compatible with the macOS system Python 3.9 (no `match`, no `X | None` without `from __future__ import annotations`), and use `curl` via subprocess for HTTPS (the system Python's LibreSSL lacks TLS 1.3).
- After changing the bill parser, rerun it on the full bill set and confirm every bill still reconciles to the penny.
