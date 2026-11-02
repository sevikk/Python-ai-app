# Python-ai-app

## Backend

The FastAPI backend provides a health check and a chat endpoint connected to
Gemini through LangChain.

### Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
uvicorn main:app --reload
```

Add your Gemini API key to `backend/.env`:

```env
GEMINI_API_KEY=your_api_key
```

The default model is `gemini-3.5-flash-lite`. To choose another model, set
`GEMINI_MODEL` in `.env`. Never put the API key in Angular code or commit it.

The API is available at `http://localhost:8000`. Interactive API documentation
is available at `http://localhost:8000/docs`.

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

Open `http://localhost:4200`. The Angular chat sends messages to the backend at
`http://localhost:8000/chat`; start the backend first. Angular uses
`frontend/src/environments/environment.ts` for local development and replaces
it with `environment.prod.ts` during a production build. The production API URL
is configured there for the Render service.

### Try the API

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Привет"}'
```

`/chat` sends the message to Gemini and returns its response. If the key is
missing, the endpoint responds with `503`; if Gemini rejects the request, it
responds with `502` and logs the provider error in the backend.