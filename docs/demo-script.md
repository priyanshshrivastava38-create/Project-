# Demo script (≈10 minutes, for a technical lead)

Use the seeded accounts (password from `DEMO_PASSWORD`, local default `MetalFlow-demo-2026`).

1. **Dashboard (management@)**: live KPIs from SQL: orders by status, active/overdue jobs,
   low-stock alerts (EN8 bar and stainless sheet are below reorder level), deliveries in transit.
   Try creating an order: management is read-only (button hidden; API returns 403).
2. **Order (sales@)**: Orders → New: Evergreen Solar Mounts, 500 × BRK-100. Note the server-computed
   totals with 20% tax. Confirm → status timeline shows DRAFT → CONFIRMED.
3. **Production (production@)**: open the order → *Create production job*. Try **Start**: it is
   rejected because materials aren't allocated.
4. **Inventory (inventory@)**: job page → *Allocate materials*: reservations appear and the
   inventory overview shows reserved vs available. Show the transaction ledger (RESERVE rows) and
   Inventory → Reconciliation logic (`/inventory/reconciliation`).
5. **Production**: Start → Advance through Material prep / Cutting / Forming → *Record output*
   (e.g. 490 good, 10 scrap; material CONSUME movements appear) → Advance to Quality inspection.
6. **Quality (quality@)**: record a **FAIL** for 100 units with 4 defects → 96 go on hold, finished
   goods unchanged. *Reinspect* with corrective action → PASS → 96 approved into stock.
   Inspect the remaining units (PASS), then (production@) record replacements if needed and **Complete**.
   The order stays IN_PRODUCTION: completion doesn't mean fulfilment.
7. **Dispatch (dispatch@)**: Deliveries → *Ready to ship* shows the approved quantity. Create a
   partial delivery (300), Mark ready, Dispatch (carrier + tracking), Confirm delivery (receiver).
   Order becomes PARTIALLY_FULFILLED. Click Dispatch twice: the second attempt is rejected and the
   ledger shows one DISPATCH movement.
8. **Assistant (any role)**: "Summarize order SO-1001", "Which production jobs are overdue?",
   "What does the approved steel specification say about material grade?" (cited section),
   then as **sales@** "Which materials are below their reorder level?" → refused by role.
   As **quality@** ask about the pricing policy → no access (restricted document).
9. **Documents (admin@)**: upload a Markdown procedure → DRAFT (not used by the assistant) → Approve
   → now cited. Show version history and approval log.
10. **Audit log (admin@)**: every step above, with user and timestamp.
11. **Engineering**: `/api/docs`, `pytest` (123 tests incl. concurrency and AI eval), CI workflow,
   `render.yaml`.
