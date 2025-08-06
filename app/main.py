from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.database import init_db
from app.api import auth, keys, chats, messages, stream, models


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the FastAPI application."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Multi-LLM chatbot backend with streaming support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    # allow_origins=settings.cors_origins,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(stream.router)
app.include_router(models.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Teehee Chat Backend",
        "version": "1.0.0",
        "docs": "/docs"
    } 