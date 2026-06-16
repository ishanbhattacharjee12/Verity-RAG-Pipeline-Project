# Verity — RAG Pipeline with Hybrid Search

## Project Overview

End-to-end Retrieval-Augmented Generation over internal documents. Retrieval runs dense (ChromaDB, `text-embedding-3-small`) and sparse (BM25) searches in parallel, fuses them with weighted Reciprocal Rank Fusion, and reranks candidates with an LLM-as-judge cross-encoder pass. Generation is constrained to the retrieved context with inline bracketed citations; every citation is then independently verified by a judge model, and each answer ships with a composite confidence score (retrieval quality × citation coverage × completeness). Unanswerable questions are refused rather than hallucinated, and a bundled 30-case golden Q&A suite measures all of it.

## Key Features

- **Hybrid Retrieval**: Combines sparse (BM25) and dense (ChromaDB) vector search.
- **Reciprocal Rank Fusion (RRF)**: Fuses sparse and dense results without brittle score normalization.
- **LLM Reranking**: Uses an LLM-as-judge cross-encoder to refine top candidates.
- **Citation Verification**: Validates every generated claim independently to prevent hallucinated citations.
- **Composite Confidence Scoring**: Grades answers based on retrieval quality, citation accuracy, and completeness.
- **Comprehensive Evaluation**: Bundled 30-case golden Q&A suite tests lookup, multi-hop, unanswerable, and ambiguous queries.

## Architecture

```text
High-Level Architecture
User
  │
  ▼
React/Vite Frontend
  │
  ▼
FastAPI Backend
  │
  ├── Hybrid Retrieval
  │      ├── BM25
  │      └── ChromaDB
  │
  ├── Reciprocal Rank Fusion
  │
  ├── LLM Reranking
  │
  ├── Citation Verification
  │
  └── Answer Generation
          │
          ▼
       OpenAI API
```

## Evaluation Framework

Measured on the bundled sample corpus (recursive chunking, hybrid retrieval, α = 0.7), 2026-06-12:

| Metric | Value |
|--------|-------|
| Pass rate (30 cases) | 83.3% (25/30) |
| Avg correctness (LLM-as-judge, 1–5) | 4.3 |
| "I don't know" accuracy (6 unanswerable) | 100% (6/6) |
| Avg latency per eval case | 15.5 s¹ |

All 10 lookups and all 8 multi-hop cases pass; the 5 failures are ambiguous-category questions where the system answers one valid interpretation instead of enumerating all of them — the failure mode that category exists to surface.

¹ Eval latency includes citation verification and correctness judging on a rate-limited (30K TPM) OpenAI org; interactive `/v1/ask` queries measure 6–10 s.

The golden set: 10 direct lookups, 8 multi-hop questions spanning 2+ documents, 6 unanswerable questions (refusal is the pass condition), 6 ambiguous questions. Per-question results include correctness, retrieval relevance, and citation accuracy; run history is persisted and charted in the Eval tab.

## Local Development

Prereqs: Python 3.11+, Node 18+.

**1. Initial Setup**

First, set up both the backend and frontend dependencies:

```bash
# Install all dependencies (frontend and backend) and create Python venv
npm run install:all
```

**2. Environment Configuration**

Configure the backend environment variables:
```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set OPENAI_API_KEY
```

**3. Run Application**

Start both the FastAPI backend and Vite frontend together with a single command from the root of the repository:

```bash
npm run dev
```

Both services will start simultaneously. The frontend will be available at http://localhost:5173, and the backend API at http://localhost:8000.

## Deployment

### Deploying Backend to Render

1. Create a new **Web Service**.
2. Set the **Root Directory** to `backend`.
3. Set the **Build Command** to: `pip install -r requirements.txt`
4. Set the **Start Command** to: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}`
5. Add the required environment variable: `OPENAI_API_KEY`.

### Deploying Frontend to Vercel

1. Create a new **Project** and select this repository.
2. Set the **Root Directory** to `frontend`.
3. Ensure the **Framework Preset** is Vite.
4. Set the **Build Command** to: `npm run build`
5. Set the **Output Directory** to: `dist`
6. Add the **Environment Variable**: `VITE_API_BASE` and set it to the URL of your deployed Render backend (e.g., `https://your-backend.onrender.com`).

## Future Improvements

- **Streaming Responses**: Implement Server-Sent Events (SSE) to stream answer chunks and citations to the frontend in real-time.
- **Authentication & RBAC**: Add secure authentication (e.g., via Firebase Auth) and restrict document access based on user roles.
- **Caching Layer**: Integrate Redis to cache frequent queries and intermediate retrieval steps to lower latency.
- **More Embedding Options**: Support local embedding models like `BGE` or `instructor` to reduce API dependencies for ingestion.

## API Reference

Full OpenAPI docs at `/docs`. Summary:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/ask` | POST | Full pipeline: retrieve → rerank → generate → verify → score |
| `/v1/ingest` | POST | Multipart upload; chunking strategy/size/overlap per request |
| `/v1/documents` | GET | Indexed documents with chunk counts and strategies |
| `/v1/documents/{id}` | DELETE | Remove a document from both indexes |
| `/v1/eval/run` | POST | Run the 30-case golden suite; returns a full report |
| `/v1/eval/progress` | GET | Poll during a run (drives the UI progress bar) |
| `/v1/eval/results` | GET | All past runs (trend data) |
| `/v1/stats` | GET | Index size, rolling confidence, mode distribution |

## Chunking Strategies

| Strategy | How it splits | Use when | Tradeoff |
|----------|---------------|----------|----------|
| `fixed` | Equal-size windows + overlap | Uniform prose, logs, transcripts | Cheap and predictable; happily cuts mid-thought |
| `recursive` | Headings → paragraphs → sentences, falling through separators | Structured docs (the default) | Respects document structure; chunk sizes vary |
| `semantic` | Boundary where adjacent-sentence embedding similarity dips below mean − σ | Dense unstructured prose where topic shifts matter | Best boundaries; costs one embedding call per sentence at ingest |

## Design Decisions

**Why hybrid beats dense-only for technical docs.** Embedding models smear rare exact tokens — `shipctl`, `X-Meridian-Key`, `mk_test_` — into a semantic neighborhood where they lose to fluent paraphrases. BM25 treats those tokens as near-unique keys and nails them. Conversely, BM25 scores zero on paraphrases ("undo a bad release" shares no tokens with `rollback`). Technical-docs queries are a mix of both shapes, so fusing the two retrievers dominates either alone. The Compare tab demonstrates this live.

**Why RRF instead of score averaging.** Cosine similarity (≈0.2–0.9, bounded) and BM25 (unbounded, corpus-dependent) live on incomparable scales; any linear combination needs per-corpus normalization that drifts as documents are added. RRF discards scores and fuses ranks — `Σ wᵢ/(k + rankᵢ)` — which is scale-free, stable under index growth, and exposes a single interpretable knob (the dense weight α).

**Why LLM-as-judge for reranking instead of a cross-encoder model.** A dedicated cross-encoder (e.g. a MiniLM variant) is cheaper per query, but it adds a model artifact to deploy, pins a tokenizer/runtime, and caps quality at its training distribution. The judge call evaluates query×passage jointly with gpt-4o-level reading comprehension, needs zero deployment surface beyond the API key already required, and reuses the same JSON-judging machinery as citation verification and eval grading. At top-10 candidate pools the latency cost is one batched call.

**Why citation verification is a separate pass.** Generation models cite plausibly, not faithfully. Verifying each claim-passage pair post-hoc with an independent judge converts citations from decoration into a measurable contract — and feeds citation coverage into the confidence score, so unsupported citations visibly drag the answer's score down.

**Why composite confidence, not model self-assessment.** A single "how confident are you?" number from the generator is poorly calibrated. The composite combines three independently measured signals: mean cosine similarity of the context actually used (retrieval), fraction of citations that survived verification (grounding), and a judge score for whether the whole question was addressed (completeness), weighted 0.3 / 0.4 / 0.3.

## Repository Layout

```text
backend/
  main.py               FastAPI app + lifespan (seeds sample corpus on first run)
  config.py             All settings via env vars (pydantic-settings)
  routers/              ask, ingest, documents+stats, eval
  services/             ingestion, embeddings, bm25_index, retrieval (RRF + rerank),
                        generation, citation_verifier, confidence, evaluator, pipeline
  models/               Pydantic v2 request/response models
  data/
    sample_corpus/      6 markdown docs (fictional company's internal docs)
    golden_qa.json      30-case eval set
    chroma/, bm25/      Persisted indexes (created at runtime)
frontend/
  src/api/              Typed client + types mirroring backend models
  src/tabs/             Ask, Documents, Eval, Compare
  src/components/       Confidence meter, citation cards, chunk panels, skeletons
```
