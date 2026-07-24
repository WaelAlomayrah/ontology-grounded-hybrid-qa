import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import auth, chat, connectors, evaluation, graph, health, ingestion, monitoring
from app.config import get_settings
from app.logging_config import configure_logging, request_id_context

settings = get_settings(); configure_logging(settings.log_level)
app = FastAPI(title="Ontology AI Pilot API", version="0.1.0", description="Traceable hybrid RDF and vector question answering")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Admin-Token", "X-Request-ID"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
    token = request_id_context.set(request_id); started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_context.reset(token)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(round((time.perf_counter()-started)*1000, 2))
    return response


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail: body = {"error": exc.detail}
    else: body = {"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}}}
    return JSONResponse(status_code=exc.status_code, content=body)

for router in (health.router, auth.router, chat.router, graph.router, ingestion.router, connectors.router, evaluation.router, monitoring.router): app.include_router(router)
Instrumentator().instrument(app).expose(app, include_in_schema=False)
