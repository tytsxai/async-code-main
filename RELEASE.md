# Release Checklist

- Run CI locally: `python -m compileall -q server`, `python -m unittest discover -s server/tests -p "test_*.py"`, `npm --prefix async-code-web run lint`, `npm --prefix async-code-web run build`
- Verify secrets are not committed (especially `server/.env`, `server/local_db.json`, tokens in logs)
- Smoke test: start with `docker compose up --build` and create a task end-to-end (clone → patch → PR)
- Tag and create a GitHub release
