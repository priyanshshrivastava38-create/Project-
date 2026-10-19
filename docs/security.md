# Security

| Control | Implementation |
|---|---|
| Passwords | Argon2id (`argon2-cffi` defaults); constant-time dummy verify for unknown emails; same error for unknown user and wrong password |
| Access tokens | PyJWT HS256, 15 min, `exp/iat/nbf/sub/type` required, algorithm pinned on decode |
| Refresh tokens | 48-byte random, stored as SHA-256, httpOnly + `SameSite=Strict` + `Secure` (prod) cookie scoped to `/api/v1/auth`, rotated each use, reuse revokes the family, logout revokes |
| Browser storage | access token in memory only; nothing sensitive in localStorage |
| Authorization | `require(P.…)` dependency on every protected route; role read from the DB on every request (role changes and deactivation apply immediately); management role read-only |
| Object-level access | restricted documents return 404 to other roles (no ID probing); assistant history is per user; assistant data tools check the same permissions as the REST API |
| Input validation | Pydantic schemas (lengths, patterns, positive quantities, enums), DB check constraints, parameterised ORM queries only; sort fields whitelisted |
| Errors | structured, no stack traces or SQL in responses; unhandled errors logged server-side |
| Files | extension whitelist + magic-byte check, size limit, UTF-8 check for text, stored in DB (never executed or served from web root), downloads with `Content-Disposition: attachment` and `nosniff` |
| Secrets | environment only; app refuses to start in production with the default or a short JWT secret; seed refuses production without `DEMO_PASSWORD`; `.env` git-ignored |
| CORS | allow-list from `CORS_ORIGINS`; production is same-origin |
| Headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy` (same-origin scripts/connections, Google Fonts only), HSTS in production; `X-Request-ID` on every response |
| Login throttling | failed logins counted per account+IP (5 / 15 min) and per IP (50 / 15 min) → `429 rate_limited` with `Retry-After`; in-process, so per worker (see gaps) |
| API docs | `/api/docs`, `/api/redoc`, `/api/openapi.json` disabled in production unless `ENABLE_API_DOCS=true` |
| Containers | non-root users in all images |
| Audit | every business mutation and login recorded with user and timestamp |
| AI | no LLM-generated SQL; documents treated as untrusted (system prompt + instruction-like sentences withheld + citation validation); context contains only data the user may already see; API key never sent to the browser or logged |

## Known gaps (address before a real production rollout)
* Login throttling is in-process: with several workers/instances each keeps its own counters. Use a proxy or Redis-backed limiter when scaling out.
* No MFA/SSO. JWT secret rotation requires re-login of all users.
* No malware scanning of uploads.
* Audit log is append-only by convention (no DB-level immutability/WORM storage).
