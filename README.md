# QuantAI — Stock & Crypto Prediction Platform

A real-time market intelligence app powered by **LangGraph**, **LangChain**, **FastAPI**, **React**, and a Bloomberg-terminal-inspired UI.

## Architecture

```
quantai/
├── main.py                 # FastAPI + LangGraph agent
├── tools.py                # All @tool logic
├── core/                   # auth, config, database, rate-limiting
├── routers/                # auth endpoints
├── frontend-react/         # 🆕 React + Vite frontend (modern architecture)
│   ├── src/
│   │   ├── components/     # UI components (TopBar, Sidebar, etc.)
│   │   ├── pages/          # Page-level components (Dashboard, Auth)
│   │   ├── hooks/          # Custom React hooks (useAPI, useWebSocket)
│   │   └── stores/         # Zustand state management
│   ├── package.json
│   └── vite.config.js
├── frontend/               # Legacy vanilla JS (deprecated)
├── Dockerfile              # Multi-stage: builds React + Python
├── requirements.txt
└── .github/                # CI/CD workflows
```

**Frontend Migration:** The project now uses a modern **React + Vite** frontend for better scalability, component reusability, and developer experience. See [frontend-react/README.md](frontend-react/README.md) and [MIGRATION_GUIDE.md](frontend-react/MIGRATION_GUIDE.md) for details.

The backend uses **PostgreSQL + asyncpg** (config via `DATABASE_URL`); predictions are stored and accuracy is tracked.

## Features

- 📈 **Real-time stock data** via `yfinance` (OHLCV, 60-day chart)
- 🪙 **Crypto data** via CoinGecko free API (no key needed); optional Redis cache mitigates rate limits
- 🤖 **LangGraph AI agent** with tools:
  - `get_stock_data` — stock price, volume, technicals
  - `get_crypto_data` — crypto market data + history
  - `get_market_overview` — indices + top 5 cryptos
  - `predict_asset` — RSI/MACD/SMA/Bollinger prediction engine
- 💬 **AI Chat** — conversational market analysis powered by LangGraph
- 📊 **Technical Analysis** — RSI, MACD, SMA 20/50, Bollinger Bands
- 🎯 **Predictions** — BUY/SELL/HOLD with confidence score & target price
- ⚡ **Modern UI** — React + Vite with TypeScript, Zustand state management
- 🔐 **Authentication** — JWT-based auth with refresh token rotation
- 🔄 **WebSocket** — Real-time live price updates

## Setup

### 1. Backend

> **Tip:** Set `REDIS_URL` to enable caching for CoinGecko/market endpoints. This greatly reduces rate-limit errors and speeds up responses.

```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy env and add your OpenAI API key
cp .env.example .env
# Edit .env and set: OPENAI_API_KEY=sk-...

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend (React)

```bash
cd frontend-react

# Install dependencies
npm install

# Start development server
npm run dev  # Opens http://localhost:5173
             # Auto-proxies API calls to backend at :8000
```

**For Production:**
```bash
npm run build  # Outputs optimized dist/
npm run preview  # Test production build
```

### 3. Docker (Recommended for Deployment)

The updated `Dockerfile` now includes both React frontend and Python backend:

```bash
# Build image (installs Node dependencies, builds React, then builds Python image)
docker build -t quantai:latest .

# Run with environment variables
docker run \
  -e OPENAI_API_KEY=sk-... \
  -e DATABASE_URL=postgresql://user:pass@host/db \
  -p 8000:8000 \
  quantai:latest
```

Access the app at `http://localhost:8000` (React frontend + FastAPI backend).

## Development Workflow

Two separate dev servers (local only):

**Terminal 1: Backend**
```bash
uvicorn main:app --reload --port 8000
```

**Terminal 2: Frontend**
```bash
cd frontend-react
npm run dev  # Port 5173
```

Vite proxies `/api/*` to `http://localhost:8000` automatically.

## Usage

### Analyze Tab
- Click any symbol in the sidebar watchlist
- Or search to add symbols in real-time

### Market Overview
- Live indices: S&P 500, NASDAQ, Dow Jones, VIX
- Top 5 cryptocurrencies by market cap

### AI Chat Tab
- Ask natural language questions:
  - *"Is NVDA a good buy right now?"*
  - *"What are Bitcoin's technical signals?"*
  - *"Compare Apple and Microsoft"*
  - *"Give me a full market overview"*

### Predictions
- Automated predictions using technical indicators + LLM reasoning
- View prediction history and accuracy metrics

## LangGraph Flow

```
User Message (Chat)
    ↓
[Agent Node] — LLM decides which tool to call
    ↓
[Tool Node] — Executes: get_stock_data / predict_asset / market_overview
    ↓
[Agent Node] — Synthesizes results into analysis
    ↓
JSON Response → Frontend (React)
```

## React Architecture

**Key Benefits:**
- 🧩 **Component-Based:** Reusable, testable components
- 📦 **State Management:** Zustand for simple, predictable state
- 🎣 **Custom Hooks:** `useAPI()`, `useWebSocketPriceStream()`
- 🚀 **Performance:** Code splitting, HMR, ~150KB bundle (gzipped)
- 🔒 **Type-Safe:** Full TypeScript support

**Directory Structure:**
```
frontend-react/src/
├── App.tsx              # Root component
├── main.tsx             # Entry point
├── components/          # Reusable UI (TopBar, Sidebar, Tabs)
├── pages/               # Route-level (Dashboard, AuthPage)
├── hooks/               # useAPI, useWebSocket
├── stores/              # Zustand: auth, UI, watchlist
└── styles/              # CSS with design tokens
```

## Migration from Vanilla JS

The legacy `frontend/index.html` has been replaced with a modern React stack. See:
- [MIGRATION_GUIDE.md](frontend-react/MIGRATION_GUIDE.md) — Detailed architecture comparison
- [frontend-react/README.md](frontend-react/README.md) — React frontend docs
- [DEPLOYMENT.md](frontend-react/DEPLOYMENT.md) — Production deployment guide

## Deployment

### Quick Deploy (Production Build Locally)

```bash
# 1. Build React frontend
cd frontend-react && npm run build && cd ..

# 2. Start backend (serves React at root)
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then visit: `http://localhost:8000`

### Docker Deployment

```bash
docker build -t quantai:latest .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e DATABASE_URL=postgresql://... \
  quantai:latest
```

### Cloud Platforms

See [frontend-react/DEPLOYMENT.md](frontend-react/DEPLOYMENT.md) for:
- Heroku
- AWS (ECS, Elastic Beanstalk)
- Railway, Render
- Vercel (frontend only)

## Environment Variables

**Backend (.env):**
```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:pass@host/db
JWT_SECRET=your-secret-key
REDIS_URL=redis://localhost:6379  # Optional
APP_ENV=production
DEBUG=false
```

**Frontend (.env.local):**
```env
VITE_API_URL=http://localhost:8000
```

## Performance

- **Frontend Bundle:** ~150KB gzipped (React 18 + libraries)
- **Backend Response:** <500ms (with caching)
- **WebSocket Latency:** <100ms (real-time prices)
- **Lighthouse:** >90 on all metrics (production)

## Extending

- Add more LangGraph tools (news sentiment, earnings, options)
- Swap LLM model (ChatOpenAI → Claude, Llama, etc.)
- Add portfolio tracking & backtesting
- Extend React components for charting (Chart.js already integrated)
- Add user notifications & alerts
- Implement dark/light theme toggle

## Contributing

1. Backend: Modify `tools.py`, `agent.py`, or `routers/`
2. Frontend: Create components in `frontend-react/src/`
3. Test locally (dev servers)
4. Commit and push
5. GitHub Actions CI/CD runs tests and builds Docker image

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml`:
- Installs dependencies
- Lints Python files
- Builds Docker image
- Pushes to GitHub Container Registry
