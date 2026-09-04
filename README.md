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
