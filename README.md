# Test-Script — Temp Numbers smoke test

GitHub Actions smoke test:

1. Install Chromium (Playwright)
2. Login to `https://tempnumbers.net/login` (`test_panel`)
3. Open `https://tempnumbers.net/gen-stats`
4. Log success / failure in the Actions log

## Run

- **Actions** → **Temp Numbers Login Test** → **Run workflow**
- Or push to `main` (auto-runs)

## Files

- `test_login.py` — Playwright script
- `.github/workflows/test.yml` — workflow
- `requirements.txt` — playwright
