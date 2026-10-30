# TAO-Fin: Verifier-Guided Financial Question Answering

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20Vite%20%7C%20Tailwind-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**TAO-Fin** is an end-to-end, verifier-guided financial question-answering system designed to eliminate financial hallucinations by extracting precise, verifiable answers directly from audited **U.S. SEC 10-K and 10-Q filings**.

Designed as a modern, light financial SaaS dashboard, TAO-Fin integrates deterministic mathematical resolution, hybrid semantic retrieval (BM25 + BGE dense embeddings in FAISS), an active verifier, and the TAO (Think-Act-Observe) controller to guarantee full citation traceability and audited accuracy.

---

## 📸 Overview & Dashboard Preview

| **Ask (Core Q&A Workflow)** | **Companies & Filings Sync** |
|:---:|:---:|
| Question composer, verified answers, formula & source row, filing quotes, and TAO trace | Searchable SEC sync table, filing explorer, and company metadata drawer |

| **Market Data & Live Stream** | **Benchmark Evaluation** |
|:---:|:---:|
| Real-time quotes, 1M/6M/1Y/5Y charts, Finnhub WebSocket stream & key statistics | Accuracy, abstention rates, latency distributions, and category performance |

---

## 🎯 Core System Guarantees

1. **Full Traceability**: Every reported financial figure is mapped directly to its official source filing, including the form (`10-K` or `10-Q`), fiscal period, filing date, SEC EDGAR accession number, and exact quoted row.
2. **No Guessing (Zero Hallucination)**: When filings lack sufficient evidence or contain conflicting numbers, TAO-Fin returns **"Insufficient evidence."** with the explicit reason rather than producing plausible hallucinations.
3. **High Efficiency**: Eliminates LLM latency and compute costs for arithmetic metrics (e.g., margins, YoY growth) using deterministic table resolvers, achieving up to **85%+ compute savings**.

---

## 🏛️ System Architecture Pipeline

```
Question (e.g. "What was Apple's gross margin in 2024?")
   │
   ▼
1. Query Analyser ──────────────── Cheap keyword & regex routing (difficulty & temporal extraction)
   │
   ├──► 2. Deterministic Resolvers ── Direct table row parsing & arithmetic (margins, growth, ratios)
   │       (LLM bypassed: 0s latency, 100% exact math)
   │
   └──► 3. Hybrid Retrieval ───────── BM25 sparse keyword search + BGE dense vector embeddings (FAISS)
           │
           ▼
        4. Local LLM ──────────────── Reasoning engine (e.g., Qwen 2.5 via Ollama)
           │
           ▼
        5. Verifier ───────────────── 4-way cross-examination: numerical, evidence, logical, financial
           │
           ▼
        6. TAO Controller ─────────── Evaluates confidence, triggers retrieval loops, or abstains
           │
           ▼
        7. Verified Answer ────────── Evidenced value, formulas, citations & compute trace
```

---

## ✨ Features

- **Ask Dashboard**:
  - Floating pill-shaped question composer with company logo/ticker indicator (`Ctrl + Enter` to submit).
  - Quick-start clickable example prompt chips.
  - Formatted answer card highlighting the primary financial value, unit, confidence score, and latency.
  - Monospace side-by-side formula and filing source row cards with one-click clipboard copying.
  - Compact verification banner indicating deterministic cross-checks or abstention reasons.
  - Collapsible **TAO trace** displaying reasoning iterations, retrieval expansions, verification checks, and compute savings.
  - Right-column filing evidence citations with highlighted numerical figures, query analysis badges, live market snapshot with sparkline, and persistent local query history.

- **Companies Management**:
  - Full SEC sync workflow: fetches company metadata, CIK, and parses 10-K/10-Q reports via SEC EDGAR.
  - Searchable, sortable table with filing counts and last synced timestamps.
  - Interactive sliding drawer with filtered filings breakdown (10-K / 10-Q) and direct links to SEC EDGAR.

- **Market Intelligence**:
  - Live price quotes, day high/low, volume, enterprise value, P/E ratio, and EPS (TTM).
  - Interactive price charts with timeframe toggling (`1M | 6M | 1Y | 5Y`).
  - Finnhub WebSocket live stream monitor with connection status and subscription controls.
  - Clear disclaimer: *Live market prices are for informational context only and never used for filing-grounded QA.*

- **Evaluation Benchmark Suite**:
  - Multi-run benchmark dashboard: **Smoke Test (8)**, **Validation Baseline (12)**, and **Dev Run (50)**.
  - 6 aligned KPI cards: Total questions, Correct, Abstained, Incorrect, Accuracy %, and Median latency.
  - Visual outcome distribution bar and category accuracy chart (Statement lines, Margins, Growth rates, Comparisons).
  - Searchable, filterable results table with pagination and per-item latency tracking.

- **About & Pipeline**:
  - Comprehensive 8-stage interactive visual architecture diagram.
  - Explanation of core guarantees and architectural principles.
  - Institutional and capstone project team credits.

---

## 🛠️ Tech Stack

### Frontend
- **Framework**: React 18, TypeScript, Vite
- **Styling**: Tailwind CSS, custom financial SaaS design system
- **Charts & Visualizations**: Recharts
- **Icons**: Lucide React

### Backend
- **Framework**: FastAPI, Uvicorn, Python 3.11–3.13
- **Database & ORM**: SQLite, SQLAlchemy
- **Information Retrieval & Embeddings**:
  - `BAAI/bge-small-en-v1.5` via `sentence-transformers`
  - FAISS (Facebook AI Similarity Search)
  - Rank-BM25 (sparse keyword ranking)
  - BeautifulSoup4 & lxml (SEC HTML filing parsing)
- **Market Data**:
  - Finnhub REST API & WebSocket trade stream
  - Yahoo Finance (`yfinance`) fallback

---

## 🚀 Getting Started

### 1. Clone Repository

```bash
git clone https://github.com/sanskrutishah14/tao-fin.git
cd tao-fin
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment (optional but recommended)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

#### Configuring `backend/.env`
Open `backend/.env` and provide your credentials:
```env
# SEC EDGAR requires a real user agent with contact email
SEC_USER_AGENT=YourName your.email@example.com

# Finnhub API Key for live market quotes (Free key: https://finnhub.io)
FINNHUB_API_KEY=your_finnhub_key_here

# Ollama local LLM endpoint (optional for RAG fallback)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b-instruct
```

> **Note**: Never commit your `.env` file to version control. The `.gitignore` file is preconfigured to prevent secret leaks.

#### Start the Backend Server:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API will be accessible at: `http://127.0.0.1:8000`
- Interactive Swagger docs: `http://127.0.0.1:8000/docs`

---

### 3. Frontend Setup

In a new terminal window:

```bash
cd frontend

# Install node dependencies
npm install

# Start Vite development server (with hot-reload)
npm run dev
```

The frontend will start at **`http://localhost:3000`** (or `http://localhost:5173`) and automatically proxy all `/api/*` calls to the running backend.

To create an optimized production build:
```bash
npm run build
```
The FastAPI backend is also configured to serve the built static production assets directly at `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/ui`.

---

## 🧪 Evaluation & Benchmarks

TAO-Fin includes reproducible automated evaluation suites:

```bash
# Run 8-question smoke evaluation
python evaluation/run_smoke.py

# Run validation baseline
python evaluation/run_validation.py

# Run table-lookup deterministic evaluation
python evaluation/run_table_lookup_eval.py
```

Results and accuracy breakdowns are automatically recorded in `evaluation/results/` and surfaced through the frontend **Evaluation** page.

---

## 👥 Capstone Project Team

- **Vedant Reshamdalal**
- **Dhruv Vidwans**
- **Sanskruti Shah**
- **Aditi Upganlawar**

- **Project Mentor**: Prof. Archana Lakhe  
- **Institution**: MPSTME, NMIMS University  
- **Academic Year**: 2026–27  

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
