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
scripts/     exporters, bill parser, data builders, Run Everything + monthly installer
dashboard/   dash_template.html, build_dashboard.py, config.example.json
config/      example credential files
```

## Setup

1. **Credentials.** Copy each file in `config/` into `scripts/tesla_api/` without the `.example` part and fill it in. That folder is gitignored.
   - Tesla: register an app at developer.tesla.com. The Fleet API requires a public key hosted at `https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem` (a GitHub Pages repo works).
   - APsystems: request OpenAPI access in the EMA web portal (Settings > OpenAPI Service). The System ID is in the EMA app under Settings > Account Details.
   - Rheem EcoNet: uses the community `pyeconet` library with your app login. The water heater script only reads data.
2. **Bills.** Put utility bill PDFs in `scripts/bills/` (gitignored). If they are password protected, add `PDF_PASSWORD=...` to `scripts/tesla_api/pacific_power.txt`. `parse_bills.py` checks that every bill's line items add up to its total.
3. **Config.** Copy `dashboard/config.example.json` to `dashboard/config.json` and fill in your own numbers.
4. **Run.** Double-click `scripts/Run Everything.command`. It fetches only what's new from each source, parses the bills, builds every `dashboard_*.json`, and writes `scripts/energy-dashboard.html`. The EMA step is budget-aware for the free 1,000 calls/month tier (a refresh uses about 15).
5. **Monthly (optional).** `scripts/Install Monthly Refresh.command` adds a macOS launch agent that runs the refresh on the 1st of each month.

Everything is read-only: no script changes any device setting.

## Privacy

Nothing personal is in this repo: no credentials, tokens, keys, bills, addresses, account numbers or energy data. All of that lives in gitignored files (`tesla_api/`, `energy_data/`, `config.json`, `dashboard_*.json`).

## Notes

- The bill parser targets Pacific Power's Oregon bill layout (net metering and time of use). Other utilities need their own parser.
- Home car charging comes from Wall Connector sessions via the Fleet API energy site (`telemetry_history?kind=charge`). Earlier months can be seeded from a Tesla app export in `dashboard_tesla_base.json`.

## License

MIT
