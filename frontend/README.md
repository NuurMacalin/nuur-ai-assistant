# Nuur AI — Personal Portfolio & AI Chat Frontend

A responsive **HTML + CSS + JavaScript** frontend for Nuur Macalin Isaaq Caddow. The sticky navigation sits above a two-column portrait and chat layout. The portrait shows Nuur holding the AI World key; the chat stays beside it on laptops and tablets, and appears first on mobile. About, skills, and experience follow below.

The chat supports suggested questions, Enter to send, Shift+Enter for a new line, and a new-conversation button. It connects to the existing **FastAPI + Qdrant RAG** backend through `/chat`.

## Folder structure

```text
nuur-ai-frontend/
├── index.html
├── styles.css
├── config.js         # CHANGE THIS to connect your API
├── app.js            # chat + API handling
└── assets/
    ├── nuur-photo.jpg       # Original photo
    └── nuur-ai-world.png    # AI World portrait used by the page
```

## Preview without any backend

Open `index.html` in a browser or, preferably, serve via a small local webserver:

```powershell
cd nuur-ai-frontend
python -m http.server 5500
```

Then visit `http://localhost:5500`. The included demo mode lets you test the interface but **does not call a real model**.

## Connect your FastAPI backend

1. Open **`config.js`**.
2. Set **`useApi: true`** (the current default).
3. Set `endpoint` to your actual route, for example `http://127.0.0.1:8000/chat`.
4. Restart your FastAPI server and refresh the frontend.
5. Check browser DevTools → Network if a request fails.

**Expected request example** (the default `buildRequest`):

```json
{"message":"Who is Nuur?","session_id":"some-unique-session-id"}
```

**Expected response example**:

```json
{"answer":"Nuur is a software developer ...", "session_id":"some-unique-session-id"}
```

If your backend expects a different body (e.g. `query` rather than `message`) change `buildRequest` in `config.js`:

```js
buildRequest: (message, sessionId) => ({ query: message, conversation_id: sessionId })
```

If it responds as `{ "response": "..." }`, the current `readAnswer` already supports it. Other supported fields include `answer`, `reply`, `message`, `result.answer`. Update `readAnswer` for any other shape.

## Example minimal FastAPI route (replace with your existing RAG logic)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

@app.post("/chat")
def chat(request: ChatRequest):
    # Replace with a call to your Qdrant + LLM RAG pipeline.
    return {"answer": "Connect your real RAG pipeline here.", "session_id": request.session_id}
```

**Note:** the example is an interface demonstration, not a working Qdrant or LLM pipeline. The actual response must come from your backend.

## Production/security notes

- Do **not** store API keys, LLM secrets, or private Qdrant tokens in `config.js` or browser JavaScript.
- Keep provider credentials on your FastAPI server (environment variables).
- Restrict FastAPI `allow_origins` to your actual frontend domain, avoid permissive production CORS, add rate limiting and request validation.
- If your backend authenticates visitors, implement an appropriate server-side authorization mechanism.
- If deployed over HTTPS, your API also needs HTTPS to avoid mixed-content blocking.
- The chat keeps a session ID in memory for this tab; it does not persist chat history across reloads. Your API may use it for conversation memory.
- UI does not claim that AI is online while in local demo mode.

## Customization

- The page uses `assets/nuur-ai-world.png`; the original photo is preserved as `assets/nuur-photo.jpg`.
- Edit copy and skills in `index.html`.
- Adjust theme tokens at the start of `styles.css`.
- The AI World portrait is a generated visual asset; answers come from the configured backend.
