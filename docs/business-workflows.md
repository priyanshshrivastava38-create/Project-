# Business workflows and rules

## End-to-end flow

```
SALES          create order (DRAFT) ──► confirm (CONFIRMED)
PRODUCTION     create job from order line ──► order IN_PRODUCTION
INVENTORY      allocate materials (reservations; all-or-nothing on requirement)
PRODUCTION     start ──► advance through route stages ──► record output (consumes material)
               ──► reach QUALITY_INSPECTION stage
QUALITY        inspect: PASS → approved units into finished goods │ FAIL → units on hold → reinspect
PRODUCTION     complete (needs approved = planned, nothing pending/on hold; unused material released)
DISPATCH       create delivery (≤ approved, unallocated qty) ──► ready (reserve finished goods)
               ──► dispatch (carrier + tracking; stock leaves) ──► in transit ──► confirm (receiver)
SYSTEM         order PARTIALLY_FULFILLED / FULFILLED from confirmed delivered quantities
```

## Orders
* Lifecycle `DRAFT → CONFIRMED → IN_PRODUCTION → PARTIALLY_FULFILLED → FULFILLED`; `DRAFT → REJECTED`
  (admin), `DRAFT|CONFIRMED → CANCELLED` (sales), `IN_PRODUCTION → CANCELLED` (admin only, only while
  every job is still PLANNED; their reservations are released).
* Order numbers come from a DB sequence. Totals are computed server-side (Decimal, half-up to cents).
* After confirmation only `notes` can change. Each product appears once per order.
* Fulfilment is derived only from **confirmed deliveries**. Completing a job never fulfils an order.

## Material requirement model (single level)
* `product_materials.quantity_per_unit` × units = material needed.
* **Units to produce** = planned − (produced − QC-rejected). Allocation must cover the material for
  the units still to produce before a job can start.
* Auto-allocation also reserves a scrap allowance (`SCRAP_ALLOWANCE_PCT`, default 5%) when stock
  permits; a job may never hold more than plan × (1 + allowance) plus replacements for scrapped and
  QC-rejected units.
* Recording output consumes material for good + scrap units from the job's reservations (FIFO);
  if allocations are insufficient the request is rejected and nothing is recorded.
* Units of measure are fixed per material (KG, M, EA…); no conversions are performed.

## Production
* Stages are configurable (`stage_definitions`) and each product has its own ordered route that
  always ends with `QUALITY_INSPECTION`. The route is snapshotted on the job.
* Jobs: `PLANNED → IN_PROGRESS → COMPLETED`, or `CANCELLED` before any output is recorded.
* Stages advance one at a time (no skipping); entering QUALITY_INSPECTION requires recorded output.
* Good output is capped at the planned quantity (QC-rejected units free capacity for replacements).
* Overdue = open job with `target_date` before today.

## Quality
* Inspections need the job at the QUALITY_INSPECTION stage and ≤ pending-inspection units.
* **PASS**: inspected − defects become approved finished goods (ledger `PRODUCE`); defects are QC rejects.
* **FAIL**: defects are QC rejects; the rest go **on hold**. Nothing is approved, nothing enters stock.
* Reinspection (requires corrective action) covers the held units of a failed inspection and
  creates a new linked record; the original is never modified (only flagged `reinspected`).

## Deliveries
* `PENDING → READY_FOR_DISPATCH → DISPATCHED → IN_TRANSIT → DELIVERED`; `CANCELLED` before dispatch
  (reservations released); `FAILED` after dispatch (optionally returning goods to stock).
* A delivery line may not exceed the line's QC-approved quantity minus quantity already on
  non-cancelled/failed deliveries (order row locked while checking). Ready-for-dispatch reserves
  finished goods and fails if they're not physically available.
* Dispatch writes one `DISPATCH` movement per line; repeating it is rejected.
* Delivered requires the receiver's name; proof-of-delivery reference optional.

## Documents
* Upload creates a DRAFT version (PDF/TXT/MD/DOCX, ≤10 MB, extension must match content).
  Approval makes that version authoritative and archives the previously approved one.
* Only approved, current versions, visible to the user's role, are used by the assistant.
* Scanned PDFs without a text layer are stored and flagged; OCR is not included.
