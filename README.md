# CMTI Help Desk Chatbot

A customized domain chatbot for **CMTI (Construction Management Training Institute)**, built with the OpenAI API
for the BCS515B Artificial Intelligence project (Phase 1). The assistant, **Aakruti**, answers questions about CMTI's
courses, corporate training, college MoUs, e-learning and contacts. It answers only from CMTI's own knowledge,
refuses out-of-scope requests and says "I don't have that information" instead of guessing.

Architecture: **Option B (full stack)** with a FastAPI backend, an HTML/CSS/JavaScript chat widget and SQLite logging.
No LangChain, LlamaIndex or bot builders: the API calls, memory and prompt assembly are written by hand.

```
Browser (widget.js)  ──fetch──▶  FastAPI backend (app/)  ──▶  OpenAI Chat Completions API
                                   │  reads knowledge/*.md
                                   └─ logs to SQLite (data/chatbot.db)
```
Only the backend holds the API key; the browser never sees it.

## Four customization layers
All four live in `knowledge/system_prompt.md`; the knowledge itself is in `knowledge/knowledge.md`.

| Layer | Where | Summary |
|---|---|---|
| 1. Persona | system_prompt.md | "Aakruti", CMTI's friendly help-desk assistant; short, polite answers |
| 2. Custom knowledge | knowledge.md, inserted at `{knowledge}` | Courses, corporate programmes, MoUs, e-learning, team, awards, contacts |
| 3. Scope control | system_prompt.md | Only CMTI topics; declines coding, homework, politics and similar, then says what it can help with |
| 4. Safety and honesty | system_prompt.md | Says when it doesn't know; never invents fees or dates; no job promises; no personal data; resists prompt injection |

Updating knowledge needs no code changes: edit `knowledge/knowledge.md` and the next message uses it.

## Project structure
```
app/
  main.py      FastAPI app and API endpoints, serves the widget
  llm.py       the only OpenAI call, with error handling for timeouts, rate limits and outages
  prompt.py    assembles system prompt + knowledge + conversation memory
  db.py        SQLite tables: sessions, messages, feedback, test_results (with personal-data masking)
  config.py    settings from environment variables / .env
knowledge/
  knowledge.md       CMTI domain knowledge (from the CMTI website)
  system_prompt.md   persona, scope and safety rules
web/
  widget.js, widget.css   embeddable chat bubble (welcome message, typing indicator, feedback, new chat, privacy notice)
  index.html              stand-alone chat page
tests/
  test_api.py      offline tests with a fake model (no API key needed)
  test_set.csv     24 systematic test queries: in-scope, unknown, out-of-scope, safety, memory
  run_tests.py     runs test_set.csv against the real model and stores results in test_results
render.yaml        free hosting on Render
```

## API
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/chat` | Send `session_id` + `message`; returns `reply`, `latency_ms`, `tokens_used`, `message_id` |
| GET | `/api/history/{session_id}` | Past messages in a session |
| POST | `/api/feedback` | Thumbs up/down (`message_id`, `rating` = 1 or -1) |
| POST | `/api/reset/{session_id}` | Start a new conversation |
| GET | `/api/health` | Status check |

Interactive documentation is at `/docs` while the server runs.

## Run locally
Needs Python 3.10 or later.
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```
Put your OpenAI key in `.env` (`OPENAI_API_KEY=...`). `.env` is in `.gitignore` and must never be committed. Then:
```bash
uvicorn app.main:app --reload
```
Open http://localhost:8000 for the chat page and http://localhost:8000/docs for the API.

## Tests
```bash
pip install -r requirements-dev.txt
python -m pytest -q          # offline: endpoints, memory, errors, logging, privacy masking
python -m tests.run_tests    # live: 24 queries against OpenAI, results saved in the test_results table
```

## Deploy (free) and add to the CMTI website
1. On https://render.com, create a **Blueprint** from this repository (it reads `render.yaml`).
2. In the service's **Environment** settings, add `OPENAI_API_KEY` as a secret.
3. Note the service address, e.g. `https://cmti-chatbot.onrender.com`.
4. Add to the website's pages: `<script src="https://cmti-chatbot.onrender.com/widget.js" defer></script>`

Render's free plan sleeps after inactivity; the first message after a pause can take around 30 to 60 seconds.

## Privacy, cost and limitations
- No personal data is requested. The widget shows a notice that messages are sent to OpenAI, and email addresses,
  phone numbers and USNs are masked before messages are logged.
- Low-cost model (`gpt-4o-mini` by default, changeable in `.env`); token usage is stored per reply.
- `OPENAI_BASE_URL` in `.env` can point the same code at another OpenAI-compatible provider (see `.env.example`),
  only if the faculty has approved a non-OpenAI provider.
- The whole knowledge base is sent with every message (no RAG). This is simple and fine for a few pages, but cost
  grows with the knowledge size.
- The bot can still make mistakes or phrase facts loosely; the knowledge file is the source of truth.
- Fees, batch dates and seat availability are deliberately not in the knowledge base, so the bot refers users to the office.
- Memory covers the last 8 exchanges of a session.
