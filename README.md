# Home Energy Dashboard

A single-page dashboard that combines every source of home energy data I could get into one place:

- **Utility bills** (Pacific Power): every line item, rate and meter read
- **Tesla Fleet API**: Powerwall 3, solar and grid flows at 5-minute resolution, plus vehicle snapshot and Supercharger history
- **APsystems EMA OpenAPI**: per-panel output from the microinverters
- **Rheem EcoNet**: heat pump water heater energy use (read-only)

It also includes an editable appliance load calculator and an NEC 220.82 panel capacity estimate checked against the real measured peak.

The dashboard is one static HTML file (Chart.js) with the data inlined at build time. No server, no database.

## Layout

```
scripts/     data exporters (macOS built-in python3 + curl; double-click the .command files)
dashboard/   dash_template.html, build_dashboard.py, config.example.json
config/      example credential files
```

## Setup

1. **Credentials.** Copy each file in `config/` into `scripts/tesla_api/` without the `.example` part and fill it in. That folder is gitignored.
   - Tesla: register an app at developer.tesla.com. The Fleet API requires a public key hosted at `https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem` (a GitHub Pages repo works).
   - APsystems: request OpenAPI access in the EMA web portal (Settings > OpenAPI Service). The System ID is in the EMA app under Settings > Account Details.
   - Rheem EcoNet: uses the community `pyeconet` library with your app login. The water heater script only reads data.
2. **Export.** Run the `.command` files (or `python3 scripts/<name>.py`). Raw data lands in `scripts/energy_data/` (gitignored). The EMA script is budget-aware for the free 1,000 calls/month tier.
3. **Build.** Put the `dashboard_*.json` files in a data folder, copy `config.example.json` to `config.json` with your own numbers, and run:
   ```
   python3 dashboard/build_dashboard.py <data_dir> energy-dashboard.html
   ```

## Privacy

Nothing personal is in this repo: no credentials, tokens, keys, bills, addresses, account numbers or energy data. All of that lives in gitignored files (`tesla_api/`, `energy_data/`, `config.json`, `dashboard_*.json`).

## Not included yet

- The utility bill PDF parser that produces `dashboard_bills.json` and `dashboard_line_items.json` (format is specific to Pacific Power).

## License

MIT
