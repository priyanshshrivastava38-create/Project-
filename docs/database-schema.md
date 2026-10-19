# Database schema

PostgreSQL 16, managed by Alembic (`backend/alembic/versions`). 26 business tables plus
`alembic_version`. All timestamps are `timestamptz`; quantities are `NUMERIC(14,3)`, money is
`NUMERIC(14,2)`.

## Tables

| Area | Table | Notes |
|---|---|---|
| Identity | `users` | one role per user (`role` column, see `permissions/policy.py`); `is_active` for deactivation |
| | `refresh_tokens` | SHA-256 hash of opaque token, `family_id` for reuse detection, `revoked_at` |
| Partners | `customers` | unique `code` (CUST-0001) and email; `status` ACTIVE/INACTIVE (soft delete) |
| | `suppliers`, `supplier_materials` | M:N materials supplied |
| Catalog | `materials` | SKU, category, grade, `uom`, `reorder_level`, preferred supplier |
| | `products` | manufactured items with list price |
| | `product_materials` | material requirement per finished unit (single level) |
| | `stage_definitions`, `product_route_steps` | configurable stages and each product's ordered route |
| | `warehouses` | storage locations |
| Inventory | `inventory_balances` | one row per (material or product, warehouse); `CHECK` on_hand ≥ 0, reserved ≥ 0, reserved ≤ on_hand; partial unique indexes |
| | `inventory_transactions` | append-only ledger: type, on_hand/reserved deltas and after-values, reference, reason, user, unique `idempotency_key` |
| | `reservations` | stock held for a production job (materials) or a delivery (finished goods); `consumed_quantity`, status ACTIVE/RELEASED/CONSUMED |
| Sales | `customer_orders` | `order_number` (SO-1001…), status, currency, tax rate, server-computed totals |
| | `order_items` | product, SKU/description snapshot, qty, unit price, line total, `delivered_quantity` |
| | `order_status_history` | every transition with user and reason |
| Production | `production_jobs` | job number, order/line link, planned/produced/scrap/approved/qc_rejected/hold quantities (DB check keeps QC buckets ≤ produced), dates, priority, current stage |
| | `job_stages` | snapshot of the route per job; doubles as stage history (start/complete/by) |
| | `production_outputs` | output batches (`batch_ref`) |
| Quality | `quality_inspections` | immutable records; `parent_id` links reinspections; checklist JSON |
| Dispatch | `deliveries`, `delivery_items` | status, carrier/tracking, receiver, POD ref, failure reason; per-line quantities |
| Documents | `documents` | title, type, status, `allowed_roles` (empty = all) |
| | `document_versions` | version number, status, filename, MIME, size, SHA-256 hash, approval info |
| | `document_files` | file bytes (1:1 with version) |
| | `document_approvals` | approval/archive history |
| | `document_chunks` | extracted text with page number / section, used for retrieval |
| | `assistant_queries` | assistant log |
| Audit | `audit_logs` | append-only: user, action, entity, summary, JSON details |

Number sequences: `order_number_seq` (1001), `job_number_seq` (5001), `inspection_number_seq` (7001),
`delivery_number_seq` (9001), `customer_code_seq`, `supplier_code_seq`, `batch_number_seq`.

## Deletion & archival policy

* Nothing transactional is hard-deleted. Customers/suppliers/materials are deactivated; documents
  are archived; orders/jobs/deliveries are cancelled; inspections and ledger rows are immutable.
* Foreign keys use `RESTRICT` for business history (you cannot delete a product that was ordered)
  and `CASCADE` only for owned children (order items, job stages, document chunks/files).

## Migrations

```bash
cd backend
alembic upgrade head                    # apply
alembic downgrade -1                    # roll back one revision
alembic revision --autogenerate -m "…"  # new migration (review the generated file!)
```

Migrations run with `transaction_per_migration=True`: a failing migration rolls back completely
and `alembic_version` keeps the last good revision. Recovery procedure:

1. Read the error, fix the migration (or the data it tripped on).
2. `alembic current` to confirm the revision, then `alembic upgrade head` again.
3. Before running migrations in production, take a backup (`pg_dump -Fc`); for destructive changes
   write expand/contract migrations (add column → backfill → switch code → drop later).

CI runs `upgrade head → downgrade base → upgrade head` on every push.
