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

## Frontend

In another terminal:

```bash
cd frontend
npm start
```

Open `http://localhost:4200`. The Angular chat sends messages to the backend at
`http://localhost:8000/chat`; start the backend first.

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