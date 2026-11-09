# Nuur AI

A personal portfolio and English/Somali knowledge assistant. FastAPI serves the
frontend and `/chat` from the same origin. Answers use excerpts from the configured
Qdrant collection and Gemini; unsupported questions receive a fixed refusal.

## Local setup

Use Python 3.12 and Docker Desktop:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `app/.env` using `.env.example` and set a working `GOOGLE_API_KEY` from
[Google AI Studio](https://aistudio.google.com/app/apikey). Existing `app/.env`
files should be updated without replacing them with the empty example.

```powershell
docker compose up -d
.\venv\Scripts\python.exe -m app.index
.\venv\Scripts\python.exe -m app.check_services --google
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Place the private knowledge PDF at `app/data/sample.pdf` before the first indexing
run. The indexer preserves a populated collection, so rerunning it does not add
duplicate chunks. Use a new collection name when preparing revised source data.

Open http://127.0.0.1:8000. Configuration is shared by the server, indexer, and
service checks. Server environment variables take precedence over local `.env`
files. See `.env.example` for model, database, timeout, and deployment settings.

## Checks

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe -m app.check_services
.\venv\Scripts\python.exe -m app.check_services --google
```

The Google check sends synthetic connectivity text only; it does not send PDF
excerpts. It verifies authentication, access to both configured models, and
compatibility between query embeddings and the stored vectors.

- `GET /health`: web process liveness.
- `GET /ready`: indexed Qdrant storage readiness; no Google API calls.
- `POST /chat`: `{"message":"Who is Nuur?","session_id":"optional-id"}`.

A 503 authentication message means Google rejected the configured key. Replace
the key in `app/.env` and restart the server. A 502 means another upstream operation
failed; check server logs and `python -m app.check_services --google`.

## Deployment

`Dockerfile` builds the app without local credentials, the private PDF, or the
virtual environment. `compose.production.yml` provides the web service, persistent
Qdrant storage, an indexer, and an optional Caddy HTTPS proxy.

Follow [the DigitalOcean deployment guide](deploy/digitalocean.md). No Droplet is
created automatically. The local `docker-compose.yml` continues to provide only
the development database.

The GitHub workflow runs the tests and builds the Docker image on pushes and
pull requests. `.env`, private source documents, original photo, database files,
and local tooling are ignored by Git.
