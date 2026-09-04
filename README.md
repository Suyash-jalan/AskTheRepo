# Codebase Q&A / Onboarding Agent

An AI agent that helps developers understand a codebase by answering natural-language questions like *"how does auth work here?"* — grounded in the actual code, docs, and git history of the repo, not generic knowledge.

Built on a hybrid **RAG (Retrieval-Augmented Generation)** architecture combined with live retrieval tools, so answers are accurate, cited, and specific to your codebase.

---

## Why this exists

New developers lose weeks getting familiar with a codebase, and senior engineers get pulled into repeated "how does X work" questions. This agent retrieves the relevant code, docs, and commit history for a question, then uses an LLM to synthesize a clear, cited answer — cutting down onboarding time and reducing interruptions.

---

## How it works

```
User question
      │
      ▼
Agent orchestrator (decides which tool(s) to use)
      │
      ├──► Vector search      → semantic search over embedded code, docs, commit messages
      ├──► Grep / ripgrep     → exact symbol / string lookup
      ├──► AST query          → structural code search (definitions, usages, interfaces)
      └──► Git blame / log    → authorship and change history
      │
      ▼
LLM synthesis (merges retrieved results)
      │
      ▼
Answer with file:line / commit citations
```

**Key design decision:** not everything is pre-indexed. Code, docs, and commit *messages* are embedded ahead of time and stored in a vector database. Precise, on-demand facts (`git blame`, `git log`, grep, AST lookups) are called live as tools — they're too granular to usefully pre-compute.

---

## Tech stack

| Component | Tool |
|---|---|
| Agent orchestration | LangGraph |
| Code parsing | tree-sitter |
| Embeddings | OpenAI / Voyage AI (code-aware) |
| Vector database | Chroma (local) / Qdrant, Pinecone (production) |
| LLM | Claude / GPT-4-class |
| Backend | FastAPI |
| Interface | Slack bot / web chat |

---

## Architecture: what's indexed vs. what's live

| Data | Storage | Access pattern |
|---|---|---|
| Code (chunked by function/class) | Vector store | Pre-indexed, semantic search |
| Docs (chunked by section) | Vector store | Pre-indexed, semantic search |
| Commit messages | Vector store | Pre-indexed, semantic search |
| `git blame` (line-level history) | — | Live tool call |
| `git log <file>` (file history) | — | Live tool call |
| Exact symbol search | — | Live tool call (ripgrep) |
| Structural queries | — | Live tool call (AST) |

The vector store persists to disk and holds the embedding, the original chunk text, and metadata (file path, line numbers, author, type) together — it's the permanent source of truth for retrieval, updated incrementally on every push via a GitHub webhook.

---

## Getting started

### Prerequisites
- Python 3.10+
- An embedding provider API key (OpenAI / Voyage AI)
- An LLM provider API key (Claude / OpenAI)

### Installation

```bash
git clone <this-repo-url>
cd codebase-qa-agent
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```
EMBEDDING_API_KEY=your_key_here
LLM_API_KEY=your_key_here
TARGET_REPO_URL=https://github.com/your-org/your-repo
```

### Ingest a repository

```bash
python ingest.py --repo <repo_url>
```

This clones the repo, chunks code/docs, pulls commit history, generates embeddings, and stores everything in the local vector database.

### Run the agent

```bash
uvicorn app:app --reload
```

Ask a question via the API, web UI, or connected Slack bot.

---

## Project structure

```
.
├── ingest/           # cloning, chunking, embedding pipeline
│   ├── code.py        # tree-sitter based code chunking
│   ├── docs.py         # doc section chunking
│   └── git_history.py  # commit log extraction
├── tools/             # live retrieval tools
│   ├── grep.py
│   ├── ast_query.py
│   └── git_tools.py    # blame, log
├── agent/             # orchestration + synthesis
│   ├── router.py       # tool-selection logic
│   └── synthesize.py   # LLM answer generation with citations
├── app.py             # FastAPI entrypoint
└── requirements.txt
```

---

## Roadmap

- [x] Code, docs, and commit message ingestion
- [x] Hybrid retrieval (vector search + grep + AST + git tools)
- [x] Agent orchestration with multi-tool routing
- [x] Cited answer synthesis
- [ ] GitHub webhook for incremental reindexing
- [ ] Slack bot interface
- [ ] Auto-generated module onboarding guides
- [ ] Usage tracking to surface confusing/under-documented areas

---

## Evaluation

Retrieval and answer quality are tracked against a hand-written set of real questions with known-correct answers, covering conceptual, exact-symbol, structural, and history-based queries. See `/eval` for the test set and scoring scripts.

---

## Contributing

Issues and PRs welcome. Please include a clear description of the change and, where relevant, an update to the eval set.

---

## License

MIT
