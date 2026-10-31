from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.routes.sec import router as sec_router
from app.routes.analyze import router as analyze_router
from app.routes.market import router as market_router
from app.routes.companies import router as companies_router
from app.routes.eval_status import router as eval_status_router

from app.db.database import init_db
from app.services.rag_index import build_tao_pipeline

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


app = FastAPI(
    title="TAO-Fin API",
    description="Verifier-guided financial reasoning system",
    version="0.1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(sec_router)
app.include_router(analyze_router)
app.include_router(market_router)
app.include_router(companies_router)
app.include_router(eval_status_router)

dist_dir = FRONTEND_DIR / "dist"
if (dist_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")


@app.on_event("startup")
def init_market_stream():
    """
    Attach the Finnhub WebSocket manager. The socket itself is not
    opened until something actually subscribes — a missing key or a
    later stream failure must not block REST quotes or RAG startup.
    """

    from app.services.finnhub_websocket import get_stream_manager

    app.state.market_stream = get_stream_manager()


@app.on_event("shutdown")
def shutdown_market_stream():
    from app.services.finnhub_websocket import get_stream_manager

    try:
        get_stream_manager().disconnect()
    except Exception as exc:
        print(f"[startup] market stream shutdown: {type(exc).__name__}")


@app.on_event("startup")
def build_rag_index():
    """
    Create DB tables and index any filings that have already been
    synced. If none exist yet, leave tao_pipeline as None --
    /api/analyze will sync the requested company on demand and build
    the index then, so a manual sync + restart is no longer required.
    """

    init_db()

    try:
        pipeline, indexed = build_tao_pipeline()
    except Exception as e:
        print(f"[startup] Warning: RAG index load deferred ({e})")
        pipeline, indexed = None, []

    app.state.tao_pipeline = pipeline
    app.state.indexed_tickers = indexed

    if pipeline is None:
        print(
            "[startup] No synced filings yet. /api/analyze will sync "
            "the company mentioned in the question on first use."
        )


@app.get("/")
def root():
    return RedirectResponse(url="/ui")


@app.get("/ui")
def demo_ui():
    dist_page = FRONTEND_DIR / "dist" / "index.html"
    page = dist_page if dist_page.exists() else FRONTEND_DIR / "index.html"
    if not page.exists():
        return {"error": f"UI not found at {page}"}
    return FileResponse(page)
