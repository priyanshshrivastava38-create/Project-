# API guide

* Interactive docs: `/api/docs` (Swagger UI), `/api/redoc`; spec at `/api/openapi.json`
  (a copy is in `docs/openapi.json`).
* Base path: `/api/v1`. JSON in/out except document upload (multipart) and download (binary).
* Decimal values are serialised as strings (`"500.000"`) to avoid float rounding.

## Authentication

```bash
curl -X POST $API/api/v1/auth/login -H 'content-type: application/json' \
     -d '{"email":"sales@metalflow.example","password":"…"}' -c cookies.txt
# → {"access_token":"…","token_type":"bearer","expires_in":900}
curl $API/api/v1/orders -H "Authorization: Bearer $TOKEN"
curl -X POST $API/api/v1/auth/refresh -b cookies.txt -c cookies.txt   # rotate
curl -X POST $API/api/v1/auth/logout  -b cookies.txt
```

Access tokens: HS256 JWT, 15 min. Refresh tokens: opaque, httpOnly cookie on `/api/v1/auth`, 7 days,
rotated on every use; replaying an old one revokes the session family.

## Errors

```json
{"error": {"code": "business_rule_violation", "message": "Cannot reserve 6: only 5 available…", "details": {"available": "5.000"}}}
```

| HTTP | code | meaning |
|---|---|---|
| 401 | `not_authenticated` | missing/invalid/expired token |
| 403 | `permission_denied` | role lacks the permission |
| 404 | `not_found` | missing, **or** not visible to your role (restricted documents) |
| 409 | `conflict` | duplicate (email, SKU, file version, idempotency key reuse) |
| 422 | `validation_error` | schema validation; `details` = list of `{loc, msg}` |
| 422 | `business_rule_violation` / `invalid_state_transition` | well-formed but not allowed now |

## Pagination & filtering

List endpoints return `{items, total, page, page_size}`; query `page` (≥1) and `page_size` (≤200).
Common filters: `q` (text), `status` (comma-separated), `date_from`/`date_to`, `sort` (`-field` for desc).

## Idempotency

`POST /inventory/receipts` and `/inventory/adjustments` accept an `Idempotency-Key` header. A repeat
with the same key returns the original transaction with **200** instead of creating a new movement.
State-machine endpoints (`/deliveries/{id}/dispatch`, `/orders/{id}/confirm`, …) are naturally
idempotent-safe: a repeat is rejected with `invalid_state_transition` and moves no stock.

## Endpoint map

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me` |
| Users | `GET/POST /users`, `GET/PATCH /users/{id}` |
| Customers | `GET/POST /customers`, `GET/PATCH /customers/{id}` |
| Suppliers | `GET/POST /suppliers`, `GET/PATCH /suppliers/{id}` |
| Catalog | `GET/POST /materials`, `PATCH /materials/{id}`, `GET /materials/categories`, `GET/POST /products`, `GET /products/{id}`, `GET /stages`, `GET /warehouses` |
| Orders | `GET/POST /orders`, `GET/PATCH /orders/{id}`, `POST /orders/{id}/confirm`, `/cancel`, `/reject` |
| Inventory | `GET /inventory`, `/inventory/low-stock`, `/inventory/transactions`, `/inventory/reservations`, `/inventory/reconciliation`; `POST /inventory/receipts`, `/inventory/adjustments`, `/inventory/reservations`, `/inventory/reservations/{id}/release` |
| Production | `GET /production/jobs`, `/production/board`, `/production/jobs/{id}`; `POST /production/jobs`, `PATCH /production/jobs/{id}`, `POST /production/jobs/{id}/allocate-materials`, `/start`, `/advance`, `/record-output`, `/complete`, `/cancel` |
| Quality | `GET /quality/inspections`, `/quality/inspections/{id}`; `POST /quality/inspections`, `/quality/inspections/{id}/reinspect` |
| Deliveries | `GET /deliveries`, `/deliveries/dispatchable`, `/deliveries/{id}`; `POST /deliveries`, `/deliveries/{id}/ready`, `/dispatch`, `/in-transit`, `/confirm-delivery`, `/fail`, `/cancel` |
| Documents | `GET/POST /documents`, `GET /documents/{id}`, `POST /documents/{id}/approve`, `/archive`, `GET /documents/{id}/approvals`, `/download` |
| Assistant | `POST /assistant/chat`, `GET /assistant/history`, `/assistant/health` |
| Dashboard/Reports | `GET /dashboard/summary`, `/dashboard/production`, `/dashboard/inventory-alerts`, `/reports/orders-by-customer`, `/reports/production-performance`, `/reports/quality`, `/reports/fulfillment`, `/audit-logs` |
| Health | `GET /health` (liveness), `GET /health/ready` (DB check) |
