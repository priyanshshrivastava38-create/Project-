# Architecture

MetalFlow ERP is a modular monolith: one FastAPI service, one PostgreSQL database, one React SPA.
No microservices, queues or vector stores. Nothing in the supported workflows needs them.

```
Browser (React SPA, access token in memory)
   │  same origin: /api/v1/*  (Bearer JWT)  +  /api/v1/auth/refresh (httpOnly cookie)
   ▼
FastAPI  ── api/v1 routers ──► permission dependency (require(P.X)) ──► services ──► SQLAlchemy ──► PostgreSQL
                                                                     └──► ai/ (intent → data tools | BM25 → provider)
```

## Backend layout (`backend/app`)

| Package | Responsibility |
|---|---|
| `core/` | settings (env), DB engine/session, JWT + Argon2, structured errors, FastAPI dependencies |
| `permissions/policy.py` | roles, permission constants, role→permission matrix (single source of truth) |
| `models/` | SQLAlchemy 2.x ORM models (one file per domain) |
| `schemas/` | Pydantic request/response models: validation and OpenAPI documentation |
| `services/` | business logic and transactions. Route handlers only parse input, check permission and call a service |
| `api/v1/` | REST routers, all mounted under `/api/v1` |
| `ai/` | assistant: `intents` (rules), `data_tools` (permission-checked read-only queries), `retrieval` (BM25), `providers` (LLM abstraction), `assistant` (orchestration + citation validation) |

Data access is done directly with the ORM inside services; a separate repository layer was
deliberately not added because it would only wrap single-line queries.

## Key design decisions

* **Inventory ledger, not a mutable counter.** `inventory_balances` is a cache of the append-only
  `inventory_transactions` ledger; every change writes a transaction with before/after values.
  `/inventory/reconciliation` proves `balance == SUM(ledger)`.
* **Row-level locking.** Stock-changing operations lock the balance row (`SELECT … FOR UPDATE OF`),
  and order/job/delivery rows are locked before balances (fixed lock order prevents deadlocks).
  DB `CHECK` constraints (`on_hand >= 0`, `reserved <= on_hand`, …) are the last line of defence.
* **Explicit state machines** for orders, jobs, inspections and deliveries, enforced in services
  (`ALLOWED_TRANSITIONS`, `TRANSITIONS`), each change audited.
* **Server-side money.** Line totals, subtotal, tax and total are computed with `Decimal` on the
  server; client-submitted totals are ignored.
* **Single-level material requirements.** Each product lists `quantity_per_unit` of each material
  plus an ordered route of configurable stages (see business-workflows.md). No multi-level BOM.
* **Documents stored in PostgreSQL** (`document_files.data`). This keeps the container stateless,
  so redeploys on ephemeral hosts can't lose files and files are never under the web root.
* **Single-origin deployment.** In production the API serves the built SPA (`FRONTEND_DIST_DIR`),
  so the refresh cookie can be `SameSite=Strict` and CORS stays closed. Docker Compose
  additionally runs an nginx frontend that proxies `/api`.

## AI assistant pipeline

1. Route dependency requires `assistant:use`.
2. `intents.classify`: regexes route to `order_status`, `job_status`, `low_stock`, `overdue_jobs`,
   `awaiting_inspection`, `ready_for_dispatch` or `documents`.
3. Business intents run a fixed, read-only service query, only if the user's role has the
   corresponding permission (e.g. `inventory:read`). No LLM-generated SQL exists anywhere.
4. Document intents run BM25 (`rank-bm25`) over chunks of **approved, current** versions of
   documents the user's role may see. Eligibility is by query-term overlap; ordering by BM25.
5. If `AI_PROVIDER` is configured, numbered passages are sent to the LLM with a strict system prompt
   (cite `[n]`, treat sources as untrusted, answer `INSUFFICIENT_EVIDENCE` otherwise).
6. Citation markers that don't match a provided passage are removed; an answer with no valid
   citation, an LLM error or a timeout falls back to a deterministic extractive answer (the most
   relevant sentences, instruction-like sentences withheld).
7. Every interaction is logged in `assistant_queries` (question, intent, cited doc ids, provider,
   fallback flag, latency). Secrets are never logged.
