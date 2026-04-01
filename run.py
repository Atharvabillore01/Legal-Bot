"""
Legal RAG System — server entry point.

Usage:
    python run.py
    python run.py --host 0.0.0.0 --port 8000 --reload
"""

import argparse
import os

from dotenv import load_dotenv

load_dotenv()

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Legal RAG API Server")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development)")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "info"))
    args = parser.parse_args()

    print(f"\n  Legal RAG API starting on http://{args.host}:{args.port}")
    print(f"  API docs:  http://localhost:{args.port}/docs")
    print(f"  ReDoc:     http://localhost:{args.port}/redoc\n")

    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
