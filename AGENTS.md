# jac-rag — Agent Guide

Multi-tenant RAG SaaS: tenants upload documents (PDF/DOCX/TXT/MD), end users chat
over them. Backend FastAPI + async SQLModel + PostgreSQL + Qdrant; CMS frontend in
Next.js + TypeScript. An embeddable chat widget will live in a **separate repo** and
consume the same versioned API.

## ⚠️ Working agreement (conservative, verify-first)

- This project is built **step by step and conservatively**. Prefer showing over doing.
- Before large or structural changes, **ask first** and describe what will change.
- Do **not** walk fast to "finish". Every step must be verifiable.
- When in doubt, ask. Never guess intent.
- No comments in code unless explicitly requested.

## Stack

- Backend: Python 3.12, FastAPI, **async** SQLModel/SQLAlchemy + `asyncpg`, Alembic, Qdrant, Redis + taskiq.
- Embeddings: **fastembed** (local, ONNX), fixed server-side. Multilingual model.
- LLM generation: **per-tenant provider** — local Ollama and/or external API (BYO key).
- CMS frontend: Next.js (App Router) + **TypeScript** (mandatory). `next-intl` for i18n.
- Widget: separate repo, consumes `/api/v1` with a tenant **embed key**.

## Repository layout

```
backend/
  app/
    main.py
    database.py            # async engine + AsyncSession dep
    core/
      config.py            # pydantic-settings
      security.py          # password hash, JWT, embed keys, visitor tokens
      cors.py              # CorsDispatcher (CMS credentialed vs widget key-only)
      deps.py              # auth deps, require_role, get_embed_tenant, get_widget_visitor
      tkq.py               # taskiq broker/scheduler
    models/                # SQLModel table models (table=True)
    schemas/               # Pydantic/SQLModel schemas (Base/Create/Update/Read)
    api/v1/                # routers, one per resource (+ widget.py, conversations.py)
    services/
      crypto.py            # encrypt/decrypt tenant secrets
      rate_limit.py        # Redis fixed-window limiter for widget keys
      llm/                 # base.py + factory.py; providers/ (ollama, openai)
                           # and resolution/ (capability, tenant, user, external)
      rag/
        ir.py              # Common Document IR (blocks, tables, rows, cells)
        diagnostics.py     # extraction/oversized diagnostics
        normalize.py       # order, block ids, section path propagation
        serialization.py   # IR -> self-descriptive text
        chunker.py         # structure-aware chunker over the Document IR
        embeddings.py      # fastembed wrapper
        retrieve.py        # hybrid retrieval + relevance gate
        rerank.py          # cross-encoder reranker (fastembed)
        chat/              # prompt, reply, prepare (shared pipeline),
                           # execute (JSON + SSE), conversations (history/persistence), events
    tasks/                 # taskiq tasks (own AsyncSession): ingest, retention (purge)
  alembic/                 # async env.py
  tests/
frontend/                  # CMS only (Next.js + TS)
docker-compose.yml         # db, qdrant, redis, backend, worker, scheduler, frontend (+ ollama)
```

## Schemas vs Models (mirror of medicines_manager, adapted to async)

- `app/schemas/<entity>.py`: `XxxBase(SQLModel)` with fields and validators
  (`field_validator`, `model_validator`), plus `XxxCreate`, `XxxUpdate`, `XxxRead`/`XxxResponse`.
- `app/models/<entity>.py`: `class Xxx(XxxBase, table=True)` adding `__tablename__`,
  `id`, `created_at`/`updated_at` (server-side `func.now()`, timezone-aware) and
  `Relationship`. No validation logic here — inherited from the schema Base.
- Export every model in `models/__init__.py` (Alembic autogenerate depends on it).
- API layer: `app/api/v1/<resource>.py` with `APIRouter` and `response_model`, no
  repository layer. Session via `Depends(get_session)`.
- `app/core/` = infrastructure, `app/services/` = integrations, `app/tasks/` = taskiq jobs.
- API routes are **versioned** (`/api/v1`) because the widget repo depends on them.

## Async rules (non-negotiable)

- `Session` → `AsyncSession`; `session.exec(...)` is awaited.
- **No lazy relationship loading.** Use explicit `selectinload`/`joinedload`, otherwise
  serialization raises `MissingGreenlet`. This is the #1 SQLModel+async bug.
- Alembic `env.py` uses `async_engine_from_config` (`run_async_migrations`).
- taskiq tasks open their **own** `AsyncSession` (never reuse request session).
- Tests: `pytest-asyncio` + `aiosqlite` (or testcontainers), not the sync `Session`
  pattern from medicines_manager.

## Multi-tenancy rules

- `tenant` is the isolation boundary. Every tenant-scoped table has `tenant_id`.
- Users are global; membership is via `memberships(user_id, tenant_id, role)`.
- **Never trust `tenant_id` from the client.** Derive membership server-side on every
  tenant-scoped route and filter every query by it.
- Roles: `OWNER | ADMIN | MEMBER`. Exactly one `OWNER`, not removable.
- Qdrant: **one collection per tenant** `tenant_{id}`. Strong isolation, clean deletion.

## Data model

```
users         (id, email UNIQUE, password_hash, locale, is_active, timestamps)
tenants       (id, name, slug UNIQUE, default_locale, answer_mode, timestamps)
memberships   (id, user_id, tenant_id, role, created_at)  UNIQUE(user_id, tenant_id)
invitations   (id, tenant_id, email, role, token_hash, expires_at,
               accepted_at, created_by, created_at)
api_keys      (id, tenant_id, name, key_hash UNIQUE, prefix, is_active,
               created_by, created_at, last_used_at)     # embed keys
documents     (id, tenant_id, uploader_id, filename, storage_path, mime,
               size, language, status, error, timestamps)
conversations (id, tenant_id, user_id NULL, end_user_id NULL, title,
               timestamps)  CHECK one actor, indexes (tenant_id, end_user_id|user_id)
messages      (id, conversation_id, role, content, sources JSON, provider,
               model, grounded, error_code, created_at)
settings      (id, scope_type global|tenant|user, scope_id NULL, type, key,
               value JSON, timestamps)                  # generic (LLM etc.)
```

- Document status: `pending | processing | ready | failed`.
- `answer_mode`: `strict` (default) | `assistive`.
- Conversations have **exactly one actor**: `user_id` (CMS member) or `end_user_id`
  (anonymous widget visitor), enforced by a CHECK constraint.

## Auth

- User login: **email without verification** in MVP (`EMAIL_ENABLED=false`), JWT access +
  refresh. JWT carries only `user_id`.
- Onboarding is two-step: `register` creates only the user; then either
  `create tenant` (creator becomes `OWNER`) or `accept invitation`.
  `GET /api/v1/tenants/{id}/me` returns the caller's membership (role lookups in the
  CMS never fetch the member list).
- Invitations: admin generates a token, shared out-of-band; store only `token_hash`
  with expiry and `accepted_at` (one-shot).
- **Widget embed key**: the CMS (OWNER/ADMIN) creates a key, shown **once**; only its
  sha256 is stored (`prefix`/`last_used_at` for the UI, `is_active` to revoke). It is a
  *publishable* key (it lives in the customer's page, like a Google Maps/Stripe
  publishable key), so it grants only: open a chat and mint a visitor session. Requests
  carry it in `X-Embed-Key`.
- **Visitor token**: `POST /api/v1/widget/session` (key-authed) mints an opaque signed
  JWT (`type=visitor`, random `sub`, bound to the tenant, `VISITOR_TOKEN_EXPIRE_DAYS`).
  The widget stores it and sends `X-Visitor-Token`; conversations are tied to its
  `subject`, so a client can never assert another visitor's identity. Stateless (no DB
  row per visitor).
- Tenant secrets (LLM API keys) are **encrypted at rest** and **never returned** by the
  API (masked only). Only `OWNER`/`ADMIN` may manage them.

## Widget API & streaming

- Widget endpoints live under `/api/v1/widget/*` and authenticate with
  `X-Embed-Key` (+ `X-Visitor-Token` where a visitor is required):
  `POST /session`, `GET /config`, `POST /chat`, `POST /chat/stream`,
  `GET /conversations`, `GET /conversations/{id}` (own only, read-only).
- Auth headers: any origin, **no cookies** → `CorsDispatcher` (`app/core/cors.py`) gives
  the widget namespace `Access-Control-Allow-Origin: *` (no credentials) with allowed
  headers `Content-Type`, `X-Embed-Key`, `X-Visitor-Token`; the CMS keeps the
  credentialed, origin-restricted policy.
- **Rate limit**: Redis fixed window per embed key (`WIDGET_RATE_LIMIT_PER_MINUTE`,
  `app/services/rate_limit.py`); `0` disables. Enforced on the chat POSTs **and** the
  read routes (`/config`, `/conversations`, `/conversations/{id}`).
- **SSE contract** (`POST .../chat/stream`, CMS and widget): `sources` (once, with
  `conversation_id` + `grounded` + `sources`), then `token`* (`{"text": ...}`), then
  `done` (`{"provider", "model", "grounded"}`); provider failures after the first byte
  emit `error` (`{"code", "message"}`), the partial reply is persisted with
  `error_code`; a client disconnect mid-stream persists the partial as
  `CLIENT_DISCONNECTED` in the background. Pre-stream errors stay normal JSON.
  Deterministic refusal (strict, no context) emits `sources` empty → one `token` →
  `done` without calling the provider. Consume with `fetch` + `ReadableStream` (not
  `EventSource`, which cannot POST or send headers).
- **Streaming route resources**: auth + retrieval run in a `session_scope()` unit of
  work closed *before* the stream starts; the provider is closed in the generator's
  `finally`, never by the route.

## i18n (IT + EN now)

- CMS UI: `next-intl`, `messages/it.json` / `messages/en.json`.
- Backend does **not** translate strings: stable error `code` + English `message`
  fallback; frontend maps `code → translation`.
- Locale: `users.locale` + `tenants.default_locale`; the widget passes its own locale.
- Assistant answers in the user/widget locale, even if retrieved context is in another
  language.

## Document ingestion & formats

- Supported: **PDF + DOCX + Markdown + TXT**, behind a **parser registry**
  (`get_parser(mime)`); every parser returns the **Common Document IR**
  (`app/services/rag/ir.py`). Adding a format = one parser file, no chunker changes.
- Pipeline: `parser -> Document IR -> normalize -> structure-aware chunk -> embed -> Qdrant`.
- **The chunker never destroys reconstructed structure**: table rows and list items are
  atomic and are never split because of a size limit; oversized atomic units are kept
  intact and flagged. Paragraphs may be split deterministically.
- Tables are structured (`TableBlock` -> header + rows + cells) and serialized
  self-descriptively (`Colonna: valore`).
- Chunk text uses the structured header `Documento:` / `Sezione:` / `Colonne:`
  (tables) / `Contenuto:`. Headings whose section has content are not emitted as
  standalone chunks; their title is propagated to the content chunk via
  `section_path`. Orphan headings (no content) stay as standalone chunks.
- `CHUNK_SIZE` is a soft target, `CHUNK_MAX_SIZE` the ceiling. Repeated header/footer
  blocks are marked and kept by default (`DROP_REPEATED_LAYOUT` to drop them).
- PDF text layer is the primary source. **OCR is a feature flag** (`OCR_ENABLED`,
  Tesseract, `eng`/`ita`) used only when needed and never as an LLM:
  - text layer below `MIN_CHARS_PER_PAGE` -> full-page OCR;
  - page is image-dominant (`OCR_IMAGE_DOMINANCE_RATIO`) but has a text layer ->
    OCR **labels only** (alphabetic tokens), so the text layer always wins on values.
  - ordinary text PDFs are never OCR'd. OCR language follows the tenant locale.
  - if extraction still yields no text, mark document `failed` with reason
    `no_text_layer` (never create an empty index silently).
- Chunk metadata (page, block_type, table_id, row_indices, section, source_block_ids)
  is stored in the Qdrant payload for provenance.

## Embeddings (fixed, server-side)

- Single model for the whole platform via `EMBEDDING_MODEL` / `EMBEDDING_DIM`, resolved at
  startup for backend and worker. **Must be multilingual.**
- Rationale: privacy, zero cost, and — key — similarity thresholds are comparable across
  tenants, so the relevance gate is calibrated once.
- Changing the model later invalidates all vectors: requires re-embedding every tenant.
  Mitigation: persist `embedding_model`/`embedding_dim` on tenant and document, and
  migrate via `tenant_{id}__v2` + background reindex + atomic switch.
- Verify the exact fastembed multilingual model availability/dimension before creating
  collections; do not assume.

## RAG strategy (no LLM router)

The LLM is **not** asked to classify intent — small local models get it wrong. The
decision is made deterministically on retrieval scores:

```
message -> fastembed -> search Qdrant top-k
  -> best score >= RELEVANCE_THRESHOLD ?
       YES -> grounded answer (strict prompt, cite sources)
       NO  -> answer_mode: strict -> refusal
                           assistive -> answer without context
```

- `strict` is the default: grounded in documents, refuses gracefully when context is
  absent. `assistive` is opt-in per tenant.
- Prompt is rigid (answer only from context, cite sources, temperature 0, top-k 4-8).
  For weak local models this matters more than routing.
- Optional deterministic greeting/short-message handling may run before retrieval; never
  an LLM-based classifier.
- Agentic tool-calling (`search_documents`) is a future opt-in for capable providers,
  not the default.

## LLM providers

- Abstraction: `LLMProvider` with `OllamaProvider` and `OpenAIProvider`
  (OpenAI-compatible: OpenAI, OpenRouter, OpenCode, vLLM...).
- Exactly one provider per request, chosen explicitly by the user among the
  tenant's allowed providers; no fallback, no multi-provider orchestration.
- Global capability: `EXTERNAL_API_ENABLED` gates whether `external_api` is
  available at all. Per tenant: `allowed_providers`, `default_provider`, model
  override; per user: `selected_provider`.
- `external_api` needs tenant config stored in the generic `settings` table
  (`external_base_url`, `external_model`, `external_api_key` encrypted).
- Endpoints: `GET/PUT /api/v1/tenants/{id}/llm/settings` (OWNER/ADMIN),
  `GET /api/v1/tenants/{id}/llm/config` and `PUT .../llm/provider` (members).
- External keys encrypted at rest (`services/crypto.py`, Fernet) and never
  returned; local Ollama reached over the docker network.

## Secrets

- `JWT_SECRET`, `ENCRYPTION_KEY` (serves tenant secrets), DB/Redis/Qdrant URLs via env.
- Never log or return secrets. `.env` never committed.

## Frontend scope (CMS only, TypeScript)

- Auth (`/register`, `/login`), onboarding (create tenant / accept invite).
- Tenant management, members, invitations, embed keys (`features/embed-keys`).
- Document upload + status, LLM settings, chat playground (`features/chat`, streaming via
  `lib/chat-stream.ts`), conversations viewer for ADMIN/OWNER (`features/conversations`).
- Module division mirrors medicines_manager: `features/<domain>/{components,hooks,services}`,
  `pages`/route groups, typed `lib/api.ts`. Next.js App Router instead of React Router.
- The embeddable widget is a **separate repo**; the CMS only manages its keys/config.

## Testing (mandatory)

- **Every function and every behavior must be tested.** This is non-negotiable in this repo.
  Happy paths, error paths, status codes, validation, edge cases, tenant isolation.
- Python: `pytest` + `pytest-asyncio`; in-memory `aiosqlite` for DB tests. Async fixtures in `conftest.py`.
- No production code is added without its tests in the same step.
- Frontend (CMS): `Vitest` + React Testing Library once the app exists (TypeScript).
- CI runs `pytest`; it must stay green.

## API errors (English only)

- The API is **English-only**. Backend strings are never localized or translated.
- Error payload is `{"code": "<STABLE_CODE>", "message": "<english>", "details": {...}}`;
  the frontend maps `code →` user language.
- Use correct HTTP status codes: `400` malformed, `401` unauthenticated, `403` forbidden,
  `404` not found, `409` conflict, `410` gone (expired), `422` validation, `500` server.
  Never `200` for an error.

## Commands

| Action | Dir | Command |
|---|---|---|
| Backend dev | `backend/` | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` |
| Tests | `backend/` | `pytest` |
| New migration | `backend/` | `alembic revision --autogenerate -m "..."` |
| Apply migrations | `backend/` | `alembic upgrade head` |
| Worker | `backend/` | `taskiq worker app.core.tkq:broker --fs-discover` |
| Scheduler | `backend/` | `taskiq scheduler app.core.tkq:scheduler` |
| Frontend dev | `frontend/` | `npm run dev` |
| Frontend tests | `frontend/` | `npm test` |
| Frontend typecheck | `frontend/` | `npm run typecheck` |
| Frontend build | `frontend/` | `npm run build` |
| Full stack | root | `docker compose up` |

## Local infrastructure

- First run: `cp .env.example .env` — Compose has **no fallback defaults**, so it fails
  without a complete `.env`.
- Full stack: `docker compose up -d --build` starts `db`, `qdrant`, `redis`, `backend`,
  `worker`, `scheduler`, `frontend`. Backend applies migrations via `start.sh` before serving.
- Infra only (for running uvicorn/taskiq/next on the host): `docker compose up -d db qdrant redis`
  — PostgreSQL 16 (`localhost:5432`, `user`/`password`, db `jac_rag`),
  Qdrant (`localhost:6333`), Redis (`localhost:6379`).
- `worker` runs `taskiq worker app.core.tkq:broker --fs-discover`; `scheduler` runs
  `taskiq scheduler app.core.tkq:scheduler`. Ingestion is on-demand (`ingest_document.kiq`);
  the scheduler only drives the periodic retention purge (`purge_conversations`, daily cron,
  `CHAT_RETENTION_DAYS`).
- Volumes: `storage_data` (uploads), `fastembed_cache` (embedding model), plus db/qdrant/redis.
- CORS: `CorsDispatcher` — the CMS allows `CORS_ORIGINS` with credentials; the widget
  namespace (`/api/v1/widget/*`) allows any origin without credentials.

## Configuration & secrets

- **No defaults in code**: every configuration value is required from the environment.
  A missing variable makes the app fail at startup. `APP_NAME`/`VERSION` are code
  constants (metadata, not configuration); `QDRANT_API_KEY` is the only optional field.
- A single `.env.example` at the repo root is the source of truth; copy it with
  `cp .env.example .env` (gitignored). `.env.example` is never read by the app.
- Docker Compose reads the root `.env` via `${VAR:?}` and **fails** when a variable is
  missing. Container-internal values (`db:5432`, `qdrant:6333`, `/data/...`) are set in
  the compose file because they describe the Docker network, not the app config.
- Running the backend on the host from `backend/` reads the same root `.env` through
  `env_file=("../.env", ".env")`.
- The frontend proxies the API same-origin: the browser calls `/api/*` and Next.js
  rewrites it to `API_PROXY_TARGET` (server-side, from the root `.env`). Only that
  variable is propagated in `next.config.ts`, so host dev from `frontend/` needs no
  separate file. In Docker the target is `http://backend:8000`.
- **Fail-fast JWT**: when `ENVIRONMENT` is not a development value, the backend refuses
  to start if `JWT_SECRET` is the default or shorter than 32 characters.
- `JWT_SECRET` rotation invalidates all issued tokens.

## Frontend (CMS, Next.js + TypeScript)

- App Router under `src/app/[locale]/`; locales IT/EN via `next-intl`
  (`messages/it.json`, `messages/en.json`).
- `src/lib/api.ts` is the typed client (throws `ApiError` with a stable `code`);
  `src/lib/types.ts` mirrors the backend schemas.
- `features/<domain>/` holds components/hooks/providers (mirrors medicines_manager).
- Auth state in `AuthProvider`; active workspace in `TenantProvider`.
- Sessions use **httpOnly cookies** (`jacrag_access`, `jacrag_refresh`) set by the
  backend. The browser never reads tokens; the CMS calls the API through the `/api`
  same-origin proxy so cookies are sent automatically.
- `middleware.ts` is the server-side guard: requests without a session cookie are
  redirected to `/{locale}/login` before rendering (public paths: login, register,
  onboarding). `RequireAuth` is a client-side secondary check.
- Error codes are mapped to translations in `errors.*`; the API stays English-only.

## Gotchas

- `passlib[bcrypt]` breaks with `bcrypt>=4.1` (`__about__`). Pin `bcrypt<4.1` or use `pwdlib`.
- Async lazy-loading (see above) — always eager-load relationships.
- `alembic/env.py` uses `async_engine_from_config`; autogenerated migrations need
  `import sqlmodel` (already in `script.py.mako`).
- Qdrant vector size is fixed per collection by the embedding model — do not mix.
- Cross-lingual retrieval works with multilingual embeddings; do not use `*-en` models.
- `redis-py>=8` sets a default `socket_timeout=5` that breaks taskiq's blocking
  `brpop` (`TimeoutError`, not caught). The broker passes `socket_timeout=None`.
- Embedding model in use: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (dim **384**). Qdrant tests use `AsyncQdrantClient(":memory:")`; `QDRANT_URL=:memory:`
  makes the app use in-memory too.
- Node 26 exposes a broken experimental `localStorage` under jsdom; `vitest.setup.ts`
  installs an in-memory polyfill.
- PDF support uses the text layer, with optional Tesseract OCR (`OCR_ENABLED`) for
  scanned pages or labels baked into page images; scanned PDFs without OCR enabled
  fail with `no_text_layer`.
- Reranker is an in-process cross-encoder (`fastembed`, `RERANK_MODEL`), no Ollama.
  `RERANK_MODE` picks the memory strategy: `on_demand` loads it for the rerank and
  releases it before the LLM call (low RAM, +1-2s/chat, needed next to a local LLM on
  a   small Docker VM), `warmup` preloads at startup and keeps ~1.2 GB resident.
  `RERANK_BATCH_SIZE` caps the cross-encoder batch; fastembed's default (64) spikes
  several GB on long candidates, a low value (4) keeps the peak ~1.8 GB at similar speed.
