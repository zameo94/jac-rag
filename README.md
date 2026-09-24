# jac-rag

The code in this repo was entirely written by a coding agent (mostly DeepSeek
V4.1 Flash). The idea, the architecture and the system design (especially the
backend) were under human control (me :)).

Multi-workspace RAG platform: each workspace uploads its own documents
(PDF, DOCX, TXT, Markdown) and chats over them. The backend exposes a versioned
API (`/api/v1`); the CMS is built with Next.js; the embeddable widget lives in a
**separate repo** (`embed-rag-chatbot`) that consumes the same API.

> **MVP.** The goal is a solid, verifiable foundation, not a complete platform.
> Some features are intentionally minimal or missing (see
> [MVP limitations](#mvp-limitations)). Every behavior is covered by tests.

---

## Table of contents

- [Project](#project)
- [First run](#first-run)
- [General usage](#general-usage)
- [The RAG](#the-rag)
  - [Ingestion (upload → index)](#ingestion-upload--index)
  - [Retrieval and answer (query → answer)](#retrieval-and-answer-query--answer)
- [Retrieval benchmarks](#retrieval-benchmarks)
- [Technology stack](#technology-stack)
- [Repository layout](#repository-layout)
- [Multi-workspace and security](#multi-workspace-and-security)
- [Configuration](#configuration)
- [Tests](#tests)
- [MVP limitations](#mvp-limitations)
- [License](#license)

---

## Project

jac-rag is a **multi-workspace RAG SaaS**. The **workspace** is the isolation
boundary: users are global, membership is granted per workspace, and roles are
`OWNER | ADMIN | MEMBER`. Each workspace has its own documents, chat, embed keys
and vector index.

What it does:

- **Ingestion** of documents (PDF with a text layer + optional OCR, DOCX, TXT,
  MD) with a **structure-aware** chunker that never destroys tables or lists.
- **Chat** over the documents with hybrid search (vector + lexical), a
  cross-encoder reranker and a **deterministic relevance gate** (no LLM router).
- **Per-workspace LLM provider**: local Ollama and/or an OpenAI-compatible
  external API (key encrypted at rest).
- **CMS** to manage workspaces, members, invitations, documents, LLM settings
  and embed keys.
- **Widget** (separate repo) that talks to the API with a publishable key and a
  visitor session.

What it does **not** do (in this MVP): no email verification, no global
superadmin role, no agent/tool-calling, a single embedding model for the whole
platform.

---

## First run

Requirements: **Docker** and Docker Compose.

```sh
cp .env.example .env
docker compose up -d --build
```

`docker compose` has **no defaults**: a missing variable in `.env` makes it fail
immediately (fail-fast). The backend applies Alembic migrations on startup.

Exposed services (ports from `.env`):

| Service | URL                                        |
| ------- | ------------------------------------------ |
| CMS     | http://localhost:3000                      |
| API     | http://localhost:8000 (Swagger at `/docs`) |
| Qdrant  | http://localhost:6333                      |
| Ollama  | http://localhost:11434                     |

The **`scheduler`** container (retention job) is behind the `retention` Compose
profile: it is only created when `RETENTION_JOB` is non-empty in `.env`.

### Host development (backend/frontend outside Docker)

Start only the infrastructure:

```sh
docker compose up -d db qdrant redis
```

Then:

| Action           | Dir         | Command                                                       |
| ---------------- | ----------- | ------------------------------------------------------------- |
| Backend          | `backend/`  | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`    |
| Worker           | `backend/`  | `taskiq worker app.core.tkq:broker --fs-discover`             |
| Scheduler        | `backend/`  | `taskiq scheduler app.core.tkq:scheduler`                     |
| New migration    | `backend/`  | `alembic revision --autogenerate -m "..."`                    |
| Apply migrations | `backend/`  | `alembic upgrade head`                                        |
| CMS              | `frontend/` | `npm run dev`                                                 |

The backend reads the same root `.env` through `env_file=("../.env", ".env")`.

---

## General usage

1. **Register** (`/register`) → only the user is created (no email verification
   in the MVP).
2. **Workspace**: a user with no membership sees a gate and can **create one**
   (becoming `OWNER`) or **accept an invitation**. The CMS home is `/dashboard`.
3. **Documents**: upload from the Documents page; the status moves from
   `pending` to `processing` to `ready` (or `failed` with a reason). Ingestion is
   asynchronous (taskiq worker).
4. **LLM settings**: pick a provider among the workspace's allowed ones; for the
   external API you configure base URL, model and API key (never returned). The
   selected provider also applies to the widget.
5. **Internal chat** (CMS): chat over the documents with token-by-token
   streaming.
6. **Embed keys**: create an embed key (shown once) and copy the snippet for the
   customer's site.

### Roles

- `OWNER`: exactly one, not removable. Can delete the workspace, edit it, manage
  members/invitations/keys and LLM settings.
- `ADMIN`: can edit the workspace, manage members/keys and LLM settings. **Cannot**
  delete the workspace.
- `MEMBER`: read-only on administrative features; can use chat and documents.

### Answer mode (`answer_mode`)

- `strict` (default): answers **only** from the documents; if the context is not
  enough, it **refuses** deterministically (no model call).
- `assistive`: if the context is missing, it still answers (general knowledge);
  if there is context, it prefers it and cites sources.

### Workspace state (`is_active`)

If a workspace is **disabled**, chat (CMS and widget) returns
`403 WORKSPACE_INACTIVE`; documents, settings, members and keys keep working.

---

## The RAG

The RAG is **deterministic and staged**: no decision is delegated to an LLM
router (small models get it wrong). Each stage below explains: what it is for,
whether it is **disableable**, and what its options change.

The same pipeline serves every entry point, for both the **CMS** and the
**widget**: a **standard JSON** response (`POST /chat`) and an **SSE stream**
(`POST /chat/stream`). Retrieval, gate and rerank are identical; only the
delivery differs (one full answer vs. token-by-token).

### Ingestion (upload → index)

1. **Upload and limits** — The file is read in a bounded way: a
   `Content-Length` above `MAX_UPLOAD_MB` is rejected before the body; the stream
   is read in chunks with an abort once the limit is exceeded
   (`413 FILE_TOO_LARGE`). Allowed formats: **PDF, DOCX, TXT, MD** (legacy `.doc`
   is rejected).

2. **Parsing → Common Document IR** — Each format has a registered parser
   (`get_parser(mime)`) that produces the same **IR** (blocks: headings,
   paragraphs, lists, tables, figures, fields, code, quotes). Adding a format =
   one new parser file, **with no chunker changes**.
   - *Disableable*: no (it is the core of ingestion).

3. **OCR (PDF only)** — Feature flag `OCR_ENABLED`. The **text layer always
   wins**; OCR only kicks in when needed:
   - page with text below `MIN_CHARS_PER_PAGE` → **full-page** OCR;
   - image-dominant page (`OCR_IMAGE_DOMINANCE_RATIO`) but with a text layer →
     OCR for **labels only** (alphabetic tokens), so values still come from the
     text layer.
   - `OCR_DPI`, `OCR_MIN_CONFIDENCE`; OCR language = workspace locale
     (`eng`/`ita`).
   - *Disableable*: **yes** (`OCR_ENABLED=false`). If no text is extracted, the
     document is marked `failed` with `no_text_layer` (never a silent empty
     index).

4. **Normalization** — Orders blocks, assigns stable `source_block_id`s and
   propagates the **section path** from headings to the following blocks. It
   never invents structure: it only propagates what the parser provided.
   - *Disableable*: no.

5. **Repeated-layout removal** — Repeated headers/footers are marked and **kept**
   by default. With `DROP_REPEATED_LAYOUT=true` they are dropped before
   chunking.
   - *Disableable*: yes (it is already opt-in).

6. **Structure-aware chunking** — Builds semantic units and packs them:
   - `CHUNK_SIZE` = soft target, `CHUNK_MAX_SIZE` = hard ceiling,
     `CHUNK_OVERLAP` = overlap (prose only).
   - **Table rows, list items and fields are atomic**: they are never split for
     size. An oversized atomic unit stays intact and is **flagged**
     (`oversized`).
   - `CHUNK_TABLE_CONTEXT`: prepends the table context (caption + columns) to the
     row, so an isolated row is understandable.
   - `CHUNK_SECTION_CONTEXT`: prepends `Document:`/`Section:` (the path).
   - `CHUNK_INCLUDE_METADATA`: stores provenance metadata (page, block_type,
     table_id, row_indices, section, source_block_ids) in the payload.
   - Headings that have content do **not** become their own chunk: their title
     travels inside the content chunk via the `Section:` line.

7. **Embedding** — Local `fastembed` (ONNX), a **fixed multilingual** model
   (`EMBEDDING_MODEL`, `EMBEDDING_DIM`, default
   `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384). It is the
   same for the whole platform, so similarity thresholds are comparable across
   workspaces and the gate is calibrated once.
   - *Disableable*: no. Changing it invalidates every vector (a full re-embed is
     required).

8. **Vector index (Qdrant)** — One **collection per workspace**
   (`workspace_{id}`): strong isolation and clean deletion. Stores the vector +
   payload (text + provenance metadata). The document is marked `ready` with
   `chunk_count` and the detected language.
   - *Disableable*: no.

### Retrieval and answer (query → answer)

1. **Query embedding** — Same function as ingestion (`embed_query`). The ONNX
   work runs in a worker thread: it never blocks the event loop.

2. **Dense search** — Top-k by cosine similarity in Qdrant (`RETRIEVAL_TOP_K`).
   - *Disableable*: no.

3. **Hybrid search (lexical BM25)** — `HYBRID_ENABLED`. Adds lexical candidates
   (`BM25Okapi`, with it/en stopwords) and fuses them with dense search via
   **Reciprocal Rank Fusion** (`RRF_K`). Useful when the same field appears in
   many documents and the distinguishing term is rare (e.g. "February 22"). The
   BM25 index is **cached per workspace** (LRU 16) and invalidated on every
   write.
   - *Disableable*: **yes** (`HYBRID_ENABLED=false` → dense only).

4. **Relevance gate** — `RELEVANCE_THRESHOLD`. It looks at the **best dense
   score** (which stays authoritative even after rerank): if it is below the
   threshold, the context is not considered relevant. This is where "answer or
   refuse" is decided, **without** an LLM.
   - *Disableable*: no (tunable via the threshold).

5. **Cross-encoder rerank** — `RERANK_ENABLED`. Candidates are over-fetched
   (`RERANK_CANDIDATES`) and reordered by a local cross-encoder (`RERANK_MODEL`);
   the best `CHAT_CONTEXT_K` go to the model. It does not change the dense score
   (the gate stays anchored to similarity).
   - `RERANK_MODE`: `on_demand` (load/unload the model, low RAM) or `warmup`
     (preloaded, fast but ~1.2 GB resident).
   - `RERANK_BATCH_SIZE`: cross-encoder batch (a low value keeps peak RAM down).
   - *Disableable*: **yes** (`RERANK_ENABLED=false` → the first `CHAT_CONTEXT_K`
     from search are used).

6. **Prompt construction** — Rigid: answer **only** from the CONTEXT, cite
   sources as `[n]`, temperature 0. The prompt is **in the configured language**
   (workspace/user) and instructs the model to **always answer in that
   language**, even when the question and context are in another language.
   - In `strict` with no context: **deterministic refusal** (message in the
     configured language), with no provider call.

7. **Generation** — Exactly one provider per request, chosen per workspace:
   `ollama` (local) or `external_api` (OpenAI-compatible). No multi-provider
   fallback. The answer is delivered either as a **standard JSON** response
   (`POST /chat`) or as an **SSE stream** (`POST /chat/stream`: `sources` →
   `token`* → `done`, or `error`). The same choice is available on the widget
   (`/api/v1/widget/chat` and `/api/v1/widget/chat/stream`).
   - *Disableable*: no (you choose the provider).

8. **Conversation history** — `CHAT_HISTORY_LIMIT`: how many previous messages
   enter the prompt (multi-turn). Conversations are then subject to retention
   (`CHAT_RETENTION_DAYS`, see [Configuration](#configuration)).

---

## Retrieval benchmarks

The retrieval pipeline has an offline benchmark harness
(`backend/benchmarks/run_baseline.py`): it runs the **real** pipeline (parsers,
chunker, embeddings, hybrid search, reranker) over a small in-memory index, so no
Postgres/Qdrant/Redis is needed. It reports Recall@k and MRR plus a failure
analysis (ingestion/chunking, retrieval, ranking).

Benchmark setup:

- **Embedding**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
  dim **384**, cosine.
- **Chunking**: `target=1000 max=1600 overlap=150 table_context=True
  section_context=True metadata=True`.
- **Retrieval**: `limit=10`; **rerank** with a cross-encoder, candidate window
  `30` (production defaults: `RERANK_MODEL`, `RERANK_CANDIDATES=30`).

### Representative dataset (7 documents, 55 queries)

A multilingual corpus with nested headings, lists, small/large tables, codes,
numbers, proper nouns, cross-document look-alikes and paraphrased queries. The
cross-encoder reranker is the single biggest win, mostly at rank 1:

| Metric    | Baseline | + rerank |
| --------- | -------- | -------- |
| Recall@1  | 0.6364   | 0.9636   |
| Recall@5  | 0.8909   | 1.0000   |
| Recall@10 | 0.9818   | 1.0000   |
| MRR       | 0.7617   | 0.9818   |

### Sample dataset (5 documents, 29 queries)

Baseline (dense + hybrid, no rerank): MRR **0.8567**, Recall@1 **0.7931**,
Recall@5 **0.9310**, Recall@10 **0.9655**.

### Reproduce

```sh
cd backend
# baseline
python -m benchmarks.run_baseline \
  --input benchmarks/retrieval/data/representative \
  --queries benchmarks/retrieval/data/representative/queries.jsonl \
  --output benchmarks/retrieval/results/representative_baseline.txt
# with the cross-encoder reranker
python -m benchmarks.run_baseline \
  --input benchmarks/retrieval/data/representative \
  --queries benchmarks/retrieval/data/representative/queries.jsonl \
  --rerank \
  --output benchmarks/retrieval/results/representative_rerank.txt
```

`--input` accepts a dataset directory (with `dataset.json`), a single document,
or a directory of documents; without `--queries` it prints a chunk inventory
instead of metrics. A chunk counts as relevant when it belongs to a ground-truth
document **and** contains one of the expected substrings.

---

## Technology stack

**Backend**

- **Python 3.12** + **FastAPI** (async API, `/api/v1`).
- **SQLModel / SQLAlchemy async** on **PostgreSQL 16** (`asyncpg`), migrations
  with **Alembic**.
- **Qdrant** for the vector index (one collection per workspace).
- **Redis** + **taskiq** for the task queue (on-demand ingestion) and the
  scheduler (retention).
- **fastembed** (ONNX, local) for **embeddings** and the **cross-encoder
  reranker**; **rank_bm25** for lexical search.
- **Tesseract** for optional PDF OCR.
- **cryptography (Fernet)** to encrypt workspace secrets at rest; JWT (access +
  refresh) and password hashing.

**CMS (frontend)**

- **Next.js** (App Router) + **React** + **TypeScript**.
- **next-intl** for i18n (IT/EN), **Tailwind CSS**.
- **Vitest** + Testing Library.

**Widget**

- Separate repo **[embed-rag-chatbot](https://github.com/zameo94/embed-rag-chatbot)**:
  **Preact** + **Vite** (IIFE bundle), **Shadow DOM** for CSS isolation, SSE via
  `fetch` + `ReadableStream`. Tested with **Vitest** + **Playwright**.

**Infrastructure**

- **Docker Compose**: `db`, `qdrant`, `redis`, `backend`, `worker`, `scheduler`
  (`retention` profile), `frontend`, `ollama`.
- **nginx** serves the static widget bundle (image in the widget repo).

---

## Repository layout

```
backend/
  app/
    main.py                # FastAPI app + /api/v1 routers
    database.py            # async engine + AsyncSession + session_scope
    core/                  # config, security, cors, deps, tkq, errors
    models/                # SQLModel tables
    schemas/               # Pydantic/SQLModel (Base/Create/Update/Read)
    api/v1/                # one router per resource (+ widget.py, conversations.py)
    services/
      crypto.py            # workspace secret encryption
      rate_limit.py        # Redis fixed-window limiter
      llm/                 # providers (ollama, openai) + resolution
      rag/                 # IR, parsers, normalize, chunker, embeddings,
                           # retrieve, rerank, vector_store, chat/
    tasks/                 # taskiq: ingest, retention
  alembic/                 # migrations (async env.py)
  tests/
frontend/                  # CMS (Next.js + TypeScript)
docker-compose.yml
```

Key ideas: **schemas vs models** (validation in schemas, models are tables
only), **no lazy loading** (always `selectinload`/`joinedload`), and tasks open
their **own** `AsyncSession`.

---

## Multi-workspace and security

- Every workspace-scoped table has `workspace_id`; the client `workspace_id` is
  **never trusted**: membership is derived server-side on every request.
- A workspace with `is_active=false` is disabled **for chat only**.
- **Embed key** (widget): a *publishable* key, stored only as a **hash** (shown
  once); it only allows opening a chat and minting a visitor session. Revocable,
  rate-limited per key.
- **Visitor session**: an opaque `type=visitor` JWT bound to the workspace;
  stateless.
- **Secrets** (provider API keys): encrypted at rest and **never returned**
  (masked only).
- **CORS**: the CMS is credentialed and restricted to `CORS_ORIGINS`; the widget
  namespace (`/api/v1/widget/*`) allows any origin **without** cookies.
- **Rate limits** on auth and widget (Redis, fail-open on an outage).

---

## Configuration

All configuration lives in the root **`.env`** (a single file, copied from
`.env.example`). No defaults in code: a missing variable makes the app fail at
startup. Docker Compose reads the same file and fails if a required variable is
missing.

Main sections of `.env.example`:

- **Runtime / DB / infra**: `ENVIRONMENT`, `DATABASE_URL`, `DB_*`, ports, `TZ`.
- **Auth/secrets**: `JWT_SECRET`, `ACCESS/REFRESH_*`,
  `SESSION_IDLE_TIMEOUT_MINUTES`, `VISITOR_TOKEN_EXPIRE_DAYS`, auth rate limits,
  `ENCRYPTION_KEY`.
- **HTTP/CORS/cookies**: `CORS_ORIGINS`, `COOKIE_*`.
- **Storage**: `STORAGE_DIR`, `MAX_UPLOAD_MB`.
- **Embeddings/retrieval**: `EMBEDDING_*`, `RELEVANCE_THRESHOLD`,
  `RETRIEVAL_TOP_K`, `HYBRID_ENABLED`, `RRF_K`, reranker.
- **Chat/widget**: `CHAT_HISTORY_LIMIT`, `WIDGET_RATE_LIMIT_PER_MINUTE`.
- **Retention** (purge old chats): `CHAT_RETENTION_DAYS`, `RETENTION_JOB`. The
  job runs once a day in the `scheduler` container; with `RETENTION_JOB` empty
  the container is **not created** (no deletion). `CHAT_RETENTION_DAYS=0`
  disables the purge in code.
- **Chunking / parsing / OCR**: `CHUNK_*`, `DROP_REPEATED_LAYOUT`, `OCR_*`,
  `MIN_CHARS_PER_PAGE`.
- **LLM**: `OLLAMA_*`, `LLM_DEFAULT_PROVIDER`, `EXTERNAL_API_ENABLED`.
- **Frontend**: `API_PROXY_TARGET`, `NEXT_PUBLIC_WIDGET_SCRIPT_URL`.

---

## Tests

```sh
cd backend && pytest          # backend (pytest-asyncio, in-memory aiosqlite)
cd frontend && npm test       # CMS (Vitest + Testing Library)
```

In the widget repo: `npm test` (unit/component) and `npm run test:e2e`
(Playwright, mocked API). Every function and behavior is covered: happy paths,
errors, status codes, validation, workspace isolation.

---

## MVP limitations

- No email verification: invitations are shared out of band.
- A single embedding model for the platform (changing it requires a reindex).
- No global superadmin: roles are per workspace.
- No agent/tool-calling: the pipeline is fixed and deterministic.
- No UI for retention beyond the on/off flag.
- The [widget](https://github.com/zameo94/embed-rag-chatbot) is a separate repo:
  the CMS manages its keys and snippet, not the bundle.

---

## License

Released under the [MIT License](LICENSE).
