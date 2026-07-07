# CampusAI — AI-Powered College/University Chatbot

A production-ready, ChatGPT-style virtual assistant for college and university
websites. It answers questions about admissions, fees, scholarships, exams,
hostel, placements, and more — grounded in your institution's own documents
via Retrieval-Augmented Generation (RAG) — and lets you switch between
**Anthropic Claude** and **OpenAI ChatGPT** at any time, with full tracing
through **LangSmith**.

---

## 1. Features

- **Dual AI providers** — Claude and ChatGPT, switchable mid-conversation, context preserved.
- **LangChain orchestration** — prompt templates, memory, retrieval chains, output parsers.
- **LangSmith tracing** — every chain run is traceable, with a built-in admin traces viewer.
- **RAG knowledge base** — upload PDF/DOCX/TXT documents; answers are grounded and cite sources.
- **ChatGPT-style UI** — sidebar history, new chat, dark/light mode, markdown + syntax highlighting.
- **Voice I/O** — speech-to-text input and text-to-speech playback (Web Speech API).
- **Search, export, feedback** — searchable history, export to TXT/PDF, thumbs up/down, regenerate.
- **Role-aware answers** — tailored tone for students, faculty, parents, and guests.
- **Secure admin dashboard** — hashed-password login, document management, analytics, chat review, LangSmith traces, usage logs.
- **REST API** — full JSON API for chat, history, documents, and analytics.
- **SQLite persistence** — chat history, users, documents, feedback, and usage logs.

---

## 2. Architecture

```
college_chatbot/
├── app.py                   # Flask application factory & entry point
├── config.py                 # Central configuration (env-driven)
├── init_db.py                 # One-time DB + sample knowledge base setup
├── models/                    # SQLAlchemy models (User, Conversation, Message, Document, Feedback, UsageLog)
├── services/
│   ├── ai_service.py          # LangChain provider routing + RAG-aware generation
│   ├── rag_service.py         # Document ingestion, chunking, embeddings, ChromaDB retrieval
│   ├── prompts.py             # Centralized, reusable LangChain prompt templates
│   └── langsmith_config.py    # LangSmith client + trace fetching for the admin dashboard
├── auth/                      # Flask-Login setup, admin login, guest sessions
├── api/                       # REST blueprints: chat, documents, admin, main pages
├── templates/                 # index.html (chat UI), admin.html, login.html
├── static/                    # css/style.css, js/chat.js, js/admin.js
├── data/sample_docs/          # Sample college documents to seed the knowledge base
└── requirements.txt
```

**Why this is modular:** adding a third AI provider only requires one new
branch in `services/ai_service.py::get_chat_model()` — the routes, prompts,
memory, and RAG pipeline are all provider-agnostic.

---

## 3. Installation

### Prerequisites
- Python 3.10+
- An Anthropic API key and/or an OpenAI API key
- (Optional but recommended) A LangSmith API key for tracing

### Steps

```bash
# 1. Clone / unzip the project, then enter the folder
cd college_chatbot

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# then edit .env and add your API keys (see section 4 below)

# 5. Initialize the database and seed the sample knowledge base
python init_db.py

# 6. Run the app
python app.py
```

The chatbot will be available at **http://localhost:5000**.
The admin dashboard is at **http://localhost:5000/admin/dashboard**
(login with the default admin credentials printed by `init_db.py`, then
change the password immediately by creating a new admin user or updating
the database).

---

## 4. API Key Configuration

Edit `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=college-chatbot
```

- Keys are **never** sent to the frontend — all AI calls happen server-side
  in `services/ai_service.py`.
- If a key is missing, the corresponding provider will return a clear,
  user-friendly error instead of crashing (see `AIProviderError` handling in
  `api/chat_routes.py`).
- LangSmith is optional. If `LANGCHAIN_API_KEY` is blank, tracing is
  silently disabled and the admin "LangSmith Traces" tab shows a notice
  instead of failing.

---

## 5. LangChain Workflow

Every chat turn runs through this LangChain pipeline (`services/ai_service.py`):

1. **Condense** — a small chain rewrites follow-up questions into standalone
   questions using the last 6 turns of chat history (resolves "what about
   the fees for that?" style references).
2. **Retrieve** — the standalone question is embedded and matched against
   the ChromaDB vector store (`services/rag_service.py`) to fetch the most
   relevant document chunks.
3. **Generate** — a `ChatPromptTemplate` (with or without retrieved context)
   is piped into the selected chat model (`ChatAnthropic` or `ChatOpenAI`)
   and parsed with `StrOutputParser`.
4. **Auxiliary chains** — title generation for new conversations and
   suggested follow-up questions each run as their own small LangChain
   chains, reusing the same provider-routing logic.

All prompts live in `services/prompts.py` so tone, structure, and behavior
stay consistent regardless of which provider answers.

---

## 6. LangSmith Setup

1. Sign up at https://smith.langchain.com and create a project.
2. Copy your API key into `.env` as `LANGCHAIN_API_KEY`.
3. Set `LANGCHAIN_PROJECT` to your project name (default: `college-chatbot`).
4. Restart the app. Every chain invocation is now traced automatically
   (LangChain reads `LANGCHAIN_TRACING_V2`/`LANGCHAIN_API_KEY` from the
   environment — no code changes needed).
5. View traces either directly on smith.langchain.com, or in-app under
   **Admin Dashboard → LangSmith Traces**, which pulls recent runs
   (status, latency, errors) via `services/langsmith_config.py`.

---

## 7. RAG Pipeline

1. An admin uploads a PDF/DOCX/TXT file via **Admin Dashboard → Knowledge Base**.
2. `services/rag_service.py::extract_text()` pulls raw text (pypdf for PDF,
   python-docx for DOCX, plain read for TXT).
3. `RecursiveCharacterTextSplitter` chunks the text (1000 chars, 150 overlap
   by default — tune via `CHUNK_SIZE`/`CHUNK_OVERLAP` in `.env`).
4. Chunks are embedded with a local `sentence-transformers` model (no extra
   API key required) and stored in a persistent **ChromaDB** collection.
5. At query time, `retrieve_context()` performs similarity search and
   returns the top-k chunks (default 4) plus source metadata, which are
   injected into the generation prompt and surfaced to the user as
   "Sources: ..." under each answer.
6. Admins can delete a document (and its vector chunks) at any time from
   the dashboard.

Four sample documents are included in `data/sample_docs/` covering
admissions, fees & scholarships, academic/exam policies, and campus
facilities — run `python init_db.py` to index them automatically.

---

## 8. Deployment

### Production server (Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Environment
- Set `DEBUG=False` and a strong random `SECRET_KEY` in `.env`.
- Use a persistent disk/volume for `instance/` (SQLite DB) and
  `chroma_db/` (vector store) if deploying on ephemeral infrastructure.
- Put Nginx (or another reverse proxy) in front of Gunicorn for TLS and
  static file caching.
- For larger deployments, swap SQLite for PostgreSQL by changing
  `DATABASE_URL` in `.env` — SQLAlchemy handles the rest.

---

## 9. Troubleshooting

| Issue | Fix |
|---|---|
| `AIProviderError: Anthropic/OpenAI API key is not configured` | Add the missing key to `.env` and restart. |
| Admin login fails with default credentials | Confirm `init_db.py` ran successfully and check `DEFAULT_ADMIN_USERNAME`/`PASSWORD` in `.env` match what you're typing. |
| Document upload fails with "Unsupported file format" | Only `.pdf`, `.docx`, and `.txt` are accepted. |
| LangSmith tab shows "not configured" | Set `LANGCHAIN_API_KEY` in `.env`. |
| Slow first response after startup | The embedding model downloads on first use; subsequent requests are fast. |
| Voice input button is hidden | Your browser doesn't support the Web Speech API (use Chrome/Edge). |

---

## 10. Future Enhancements

- Streaming token-by-token responses in the UI (backend already supports
  `streaming=True` on both chat models).
- Multi-tenant support for multiple colleges on one deployment.
- Fine-grained role-based document visibility (e.g., faculty-only policies).
- Native mobile app wrapper.
- Additional AI providers (Gemini, local open-source models) — just add a
  branch to `get_chat_model()`.

---

## 11. Tech Stack Summary

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Bcrypt |
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5 |
| Database | SQLite |
| AI Orchestration | LangChain |
| Observability | LangSmith |
| Vector Store | ChromaDB |
| Embeddings | sentence-transformers (local, free) |
| AI Providers | Anthropic Claude API, OpenAI ChatGPT API |

---

Built as a demonstration of Generative AI, LLM orchestration, RAG, and
full-stack engineering best practices for a real-world campus assistant.
