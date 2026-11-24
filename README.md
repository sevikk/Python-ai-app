# Python-ai-app

## Backend

The FastAPI backend provides a health check and a chat endpoint connected to
Gemini through LangChain. Its initial structure separates HTTP routes, data
schemas, application settings, and the model-calling service:

```text
backend/
└── app/
    ├── api/routes/    # HTTP endpoints
    ├── core/          # Configuration and request limits
    ├── schemas/       # Request and response models
    ├── services/      # Gemini/LangChain interaction
    └── main.py        # FastAPI app assembly and middleware
```

### Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
uvicorn app.main:app --reload
```

Add your Gemini API key to `backend/.env`:

```env
GEMINI_API_KEY=your_api_key
```

For PostgreSQL, set `DATABASE_URL` in `backend/.env`, for example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/python_ai_app
```

Start the local database and backend with Docker:

```bash
docker compose up --build
```

Set `GEMINI_API_KEY`, `DATABASE_URL`, `SESSION_SECRET`, and
`AUTH_COOKIE_SECURE=false` in `backend/.env`. The Docker Compose backend
loads that file automatically.
Generate `SESSION_SECRET` once with
`python3 -c "import secrets; print(secrets.token_urlsafe(32))"` and keep it
private; the backend refuses to start if it is missing or shorter than 32
characters. Authentication endpoints are rate-limited to 5 attempts per
15 minutes for each IP/email pair, and 30 attempts per IP during the same
window. These in-memory limits are per application process.

Register and sign in through `POST /auth/register` and `POST /auth/login`.
Successful responses set an HttpOnly session cookie. Use `GET /auth/me` to
check the current user and `POST /auth/logout` to clear the cookie.

For the deployed Cloudflare Pages frontend, configure Render with:

```env
AUTH_COOKIE_SECURE=true
CORS_ORIGINS=http://localhost:4200,https://python-ai-app.pages.dev
```

The frontend sends `credentials: "include"` for chat, conversation, and auth
requests. Production cookies use `SameSite=None` and `Secure`; a local HTTP
development setup uses `SameSite=Lax` and no Secure flag.
When an authenticated user registers or logs in with the browser's anonymous
session ID, existing chats for that session are claimed by the user. Owned
conversation list, detail, and delete endpoints only expose the user's own
chats. Anonymous chats remain visible only to their original session ID.

Alembic manages database schema changes. The backend runs `alembic upgrade head`
at startup. If PostgreSQL is available but a migration fails, startup fails
instead of serving requests with an outdated schema. If PostgreSQL itself is
unavailable, chat can still run without history persistence. For local
development, apply migrations manually before starting the backend:

```bash
cd backend
alembic upgrade head
```

`GET /health/db` reports PostgreSQL availability. PostgreSQL failures do not
break chat responses; history persistence is skipped and logged instead.
Empty conversations are removed during backend startup.

The default model is `gemini-3.5-flash-lite`. To choose another model, set
`GEMINI_MODEL` in `.env`. Never put the API key in Angular code or commit it.

The API is available at `http://localhost:8000`. Interactive API documentation
is available at `http://localhost:8000/docs`.

Chat requests are limited to 10 per client IP per 60 seconds by default. Set
`CHAT_RATE_LIMIT` and `CHAT_RATE_WINDOW_SECONDS` to change these values. The
limit is kept in process memory, so each backend instance tracks its own usage.
Requests may contain up to 20 messages, with at most 4,000 characters per
message. Run the backend tests with:

```bash
cd backend
python -m unittest discover -v
```

## Deploy

The app can be deployed with Cloudflare Pages (Angular) and Render (FastAPI).

### 1. Deploy the backend to Render

1. In Render, choose **New → Blueprint** and connect this GitHub repository.
2. Render detects the root `render.yaml`; create the `python-ai-chat-api`
   service and enter your Gemini API key when prompted.
3. After deployment, copy the service URL, for example
   `https://python-ai-chat-api.onrender.com`.
4. In the Render service's **Environment** settings, add
   `CORS_ORIGINS=http://localhost:4200` for now. Add the Cloudflare Pages
   `https://<project>.pages.dev` origin here after deploying the frontend.

Check `https://<render-service>.onrender.com/health` to confirm the backend is
running. A free Render service may sleep when idle, so the first request after
an idle period can take about a minute.

### 2. Configure and deploy the frontend to Cloudflare Pages

1. Update `frontend/src/app/chat-api.service.ts`: set `apiUrl` to the Render
   URL followed by `/chat`, for example
   `https://python-ai-chat-api.onrender.com/chat`.
2. Commit and push that change to the `main` branch.
3. In Cloudflare, choose **Workers & Pages → Create application → Pages →
   Connect to Git**, then select this repository.
4. Set the production branch to `main`, the root directory to `frontend`, the
   build command to `npm run build`, and the build output directory to
   `dist/frontend/browser`.
5. Save and deploy. Cloudflare will build and publish the frontend at a
   `https://<project>.pages.dev` URL.

### 3. Allow the deployed frontend to call the backend

In the Render service's **Environment** settings, set `CORS_ORIGINS` to the
Cloudflare Pages origin, for example `https://my-chat.pages.dev`. To allow both
the production site and local development, use a comma-separated value:
`http://localhost:4200,https://my-chat.pages.dev`. Save changes and let Render
redeploy.

The Gemini API key is configured only in Render's environment settings. Do not
add it to Cloudflare Pages or the frontend source.

## Frontend

In another terminal:

```bash
cd frontend
npm start
```

Open `http://localhost:4200`. The Angular chat streams responses from the
backend at `http://localhost:8000/chat/stream`; start the backend first. Angular uses
`frontend/src/environments/environment.ts` for local development and replaces
it with `environment.prod.ts` during a production build. The production API URL
is configured there for the Render service.

### Try the API

```bash
curl http://localhost:8000/health
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

`/chat` accepts a `messages` array containing recent `user` and `assistant`
messages and returns a complete JSON response. The frontend uses
`POST /chat/stream`, which accepts the same payload and streams Server-Sent
Events as Gemini generates text. The frontend keeps the latest 20 messages in
memory and sends them with each request; completed conversations are saved in
the database-backed chat history. The Stop button cancels the active stream;
any partial reply remains visible in the current page but is not saved. The
chat can start a new conversation, automatically scroll to new messages, and
retry a failed request. Assistant replies render sanitized Markdown with
highlighted fenced code blocks; untrusted HTML and images are not rendered.
Use **Extract tasks from text** to request a schema-validated list of tasks,
including priority and an explicit due date when present.
If the key is missing, either endpoint responds with `503`; provider failures
are logged by the backend and reported to the client.