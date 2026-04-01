"""
Legal RAG System — FastAPI Application (Module 5)

Entry point for the REST API server.

Run with:
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

Or via the project entry point:
    python run.py
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import create_tables
from .routers import auth, documents, ingest, query, audit

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

def _reset_stuck_documents() -> None:
    """
    On startup, any document stuck in 'pending' or 'processing' means the
    server restarted while a BackgroundTask was running — that task is gone.
    Mark them 'failed' so the user knows to re-upload.
    """
    from .database import SessionLocal, Document
    from datetime import datetime

    db = SessionLocal()
    try:
        stuck = (
            db.query(Document)
            .filter(Document.status.in_(["pending", "processing"]))
            .all()
        )
        if stuck:
            for doc in stuck:
                doc.status = "failed"
                doc.error_message = (
                    "Processing was interrupted because the server restarted. "
                    "Please delete and re-upload this document."
                )
                doc.processed_at = datetime.utcnow()
            db.commit()
            logger.warning(
                f"Reset {len(stuck)} stuck document(s) to 'failed' on startup."
            )
    except Exception as e:
        logger.warning(f"Could not reset stuck documents: {e}")
    finally:
        db.close()


def _seed_demo_user() -> None:
    """Create demo user (user@example.com / password123) if not present."""
    from .database import SessionLocal, User
    from .auth import hash_password
    import uuid

    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.email == "user@example.com").first()
        if not exists:
            demo = User(
                id=str(uuid.uuid4()),
                email="user@example.com",
                hashed_password=hash_password("password123"),
                full_name="Demo User",
                is_active=True,
            )
            db.add(demo)
            db.commit()
            logger.info("Seeded demo user: user@example.com / password123")
    except Exception as e:
        logger.warning(f"Could not seed demo user: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    logger.info("Starting Legal RAG API server...")
    create_tables()
    logger.info("Database tables ensured.")
    _reset_stuck_documents()
    _seed_demo_user()
    yield
    logger.info("Legal RAG API server shutting down.")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Legal RAG System API",
    description=(
        "Secure, multi-tenant REST API for legal document analysis. "
        "Upload PDFs, query with natural language, and get cited answers with confidence scores."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request ID + timing middleware ───────────────────────────────────────────

@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.perf_counter()

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response


# ─── Global exception handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled exception [{request_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "request_id": request_id},
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(documents.router)
app.include_router(audit.router)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe — returns 200 if the server is running."""
    from datetime import datetime
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Legal RAG API. Visit /docs for the interactive API explorer."}
