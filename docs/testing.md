# Testing

## Backend (pytest)

```bash
createdb metalflow_test             # once
cd backend && .venv/bin/pytest -o addopts="" -q
```

* Uses `TEST_DATABASE_URL` (default `postgresql+psycopg://localhost:5432/metalflow_test`) and refuses
  any database whose name doesn't end in `_test`. It drops and recreates the schema with the real
  Alembic migrations.
* Each test runs in a transaction that is rolled back; concurrency tests use real parallel
  connections and clean up after themselves.

| File | Covers |
|---|---|
| `test_units.py` | order totals/rounding, order state machine, permission matrix, overdue logic, intent routing, tokenizer, citation validation, MD/DOCX/PDF extraction |
| `test_auth.py` | login, invalid credentials, inactive user, token tampering, refresh rotation + reuse detection, logout, user admin |
| `test_rbac.py` | 401 on every protected area, role restrictions (sales can't adjust stock, management read-only, dispatch can't plan jobs…) |
| `test_customers_orders.py` | customer validation/duplicates, server totals, order validation, transitions, edit lock, cancel/reject paths, filters |
| `test_inventory.py` | receipts, idempotency, adjustments, negative-stock prevention, reservation limits, release, reconciliation, low stock |
| `test_production_quality.py` | job creation rules, start without materials, stage rules, consumption, output caps, failed → hold → reinspection, completion rules |
| `test_deliveries.py` | ship-before-QC rejection, over-shipment, partial → full fulfilment, duplicate dispatch, cancel/fail/return |
| `test_documents_ai.py` | upload validation, draft vs approved citations, versioning, restricted docs (IDOR), archived docs, prompt injection, provider failure/fabricated citations, private history |
| `test_ai_eval.py` | evaluation dataset `tests/eval/assistant_eval.json` (13 cases: grounding, citation section, permissions, unapproved docs, insufficient evidence, injection, DB intents) |
| `test_concurrency.py` | parallel withdrawals can't overdraw; parallel duplicate receipts create one movement |
| `test_dashboard_audit.py` | dashboard counts follow DB changes, trend/reports, audit trail, health |

## Frontend (Vitest + React Testing Library)

```bash
cd frontend && npm test
```

## Lint / build
`ruff check . && ruff format --check .` (backend), `npm run lint && npm run build` (frontend).
CI runs all of the above plus migration up/down and Docker builds.
