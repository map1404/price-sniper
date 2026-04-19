# 🎯 Price Drop Sniper Agent

An autonomous price intelligence agent built with **LangGraph** that crawls 5 retailers,
analyzes 90-day price history, detects buying signals, and reasons about whether to
**BUY NOW**, **WAIT**, or **AVOID** a product — all from a single URL.

---

## Project Structure

```
price_sniper/
├── agent.py              ← LangGraph graph definition (main orchestrator)
├── tools/
│   ├── crawler.py        ← Async multi-retailer webcrawler (Crawl4AI)
│   ├── price_history.py  ← 90-day price history fetcher (CamelCamelCamel)
│   ├── analyzer.py       ← Signal detection (flash sales, ATL, stock, seasonality)
│   └── reasoner.py       ← LLM reasoning agent with few-shot CoT prompting
├── ui/
│   └── app.py            ← Streamlit demo interface
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Playwright (required by Crawl4AI for JS-rendered pages)
```bash
playwright install chromium
```

### 3. Set API keys
Create a `.env` file:
```
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
```

Or enter them directly in the Streamlit sidebar during the demo.

---

## Run the React demo

```bash
cd frontend
npm install
npm run build
cd ..
python server.py
```

Then open `http://127.0.0.1:8000` and paste any product URL (Amazon, Best Buy, Walmart, Target, Newegg).

## Deploy on Render

This repo now includes:

- `Dockerfile`
- `render.yaml`

Recommended path:

1. Push this repo to GitHub
2. In Render, choose **New +** → **Blueprint**
3. Select this repository
4. Render will detect `render.yaml` and create the `price-sniper` web service
5. Add any required environment variables in the Render dashboard:

```bash
OPENAI_API_KEY=...
# and/or
ANTHROPIC_API_KEY=...
```

Notes:

- The service exposes `GET /health` for Render health checks
- The server binds to `0.0.0.0` and uses Render's `PORT` environment variable
- The React frontend is built into the Docker image and served by the Python server

## Run the React app in development

Terminal 1:
```bash
python server.py
```

Terminal 2:
```bash
cd frontend
npm install
npm run dev
```

Then open `http://127.0.0.1:5173`.

---

## Run via CLI

```bash
python agent.py
# Enter a product URL when prompted
```

---

## How it works (LangGraph pipeline)

```
[identify_product] → [crawl_prices] → [fetch_history] → [analyze] → [reason_and_decide]
```

| Node | What it does |
|------|-------------|
| `identify_product` | Extracts product name from URL structure |
| `crawl_prices` | Async-crawls 5 retailers for live prices + stock status |
| `fetch_history` | Fetches 90-day price history from CamelCamelCamel or generates realistic synthetic data |
| `analyze` | Detects signals: flash sales, proximity to ATL, low stock, seasonal events |
| `reason_and_decide` | LLM with chain-of-thought + few-shot examples produces BUY/WAIT/AVOID verdict |

---

## Rubric mapping

| Step | Implementation |
|------|---------------|
| **1. Business case** | Consumers overpay; existing tools (Honey, CamelCamelCamel) track but don't *reason*. This agent decides. |
| **2. Model selection** | GPT-4o / Claude Sonnet for reasoning; Crawl4AI for webcrawling; CamelCamelCamel for history |
| **3. Model adaptation** | Chain-of-thought prompting + 3 few-shot examples with labelled BUY/WAIT/AVOID decisions |
| **4. Implementation** | LangGraph agent with retrieval node, Python API server, React frontend dashboard |

---

## Demo script (for presentation)

1. Open the Streamlit app
2. Paste a real Amazon product URL live
3. Watch the agent animate through each pipeline step
4. Show the price comparison bar chart
5. Show the 90-day history with ATL line
6. Reveal the verdict card + reasoning chain
7. Say: *"Honey tells you what happened. This agent tells you what to do."*
