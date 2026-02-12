"""
VibeOps - FastAPI Main Application

Entry point for the backend server.
Multi-tenant AI operations platform.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import os
import traceback

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import settings
from .database import init_db, close_db, async_session
from .services.seed_service import run_all_seeds
from .services.scheduler_service import scheduler_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# Frontend directory path
FRONTEND_DIR = os.path.join(settings.PROJECT_ROOT, "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup:
    - Initialize database tables
    - Seed default data (teams, admin users)
    - Start scheduler service

    Shutdown:
    - Stop scheduler service
    - Close database connections
    """
    # Startup
    logger.info("Starting VibeOps API...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Seed default data
    async with async_session() as db:
        seed_result = await run_all_seeds(db)
        logger.info(f"Database seeded: {seed_result}")

    # Start scheduler and load existing schedules
    scheduler_service.start()
    logger.info("Scheduler service started")

    async with async_session() as db:
        await scheduler_service.load_schedules_from_db(db)
        logger.info("Schedules loaded from database")

    yield

    # Shutdown
    logger.info("Shutting down VibeOps API...")

    # Stop scheduler
    scheduler_service.stop()
    logger.info("Scheduler service stopped")

    await close_db()
    logger.info("Database connection closed")


app = FastAPI(
    title="VibeOps API",
    description="AI-First 운영 자동화 플랫폼 API - Multi-Tenant Architecture",
    version="0.3.0",
    lifespan=lifespan,
)

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [settings.ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Global Exception Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent JSON response"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail
            }
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    Logs the full traceback but returns a safe message to the user.
    """
    # Log the full error with traceback
    error_id = datetime.now().strftime("%Y%m%d%H%M%S")
    logger.error(
        f"Unhandled exception [ID: {error_id}] on {request.method} {request.url.path}:\n"
        f"{traceback.format_exc()}"
    )

    # Return safe error response to user
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": "내부 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                "error_id": error_id  # For support reference
            }
        }
    )

# Include API routers
from .routers import (
    auth_router, teams_router, knowledge_router, bridge_router,
    ai_router, admin_router, agents_router, schedules_router
)
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(teams_router, prefix="/api/teams", tags=["Teams"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["Knowledge"])
app.include_router(bridge_router, prefix="/bridge", tags=["Bridge"])
app.include_router(ai_router, prefix="/api", tags=["AI"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(agents_router, prefix="/api", tags=["Agents"])
app.include_router(schedules_router, prefix="/api", tags=["Schedules"])

# Mount static files (CSS, JS)
if os.path.exists(FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "ok",
            "bridge": "ok",
            "scheduler": "running" if scheduler_service.is_running else "stopped",
            "agents": {}
        }
    }


@app.get("/api/info")
async def api_info():
    """API information endpoint"""
    return {
        "name": "VibeOps Multi-Tenant API",
        "version": "0.2.0",
        "features": [
            "Multi-tenant team isolation",
            "Role-based access control",
            "Knowledge inheritance system",
            "AI bridge integration"
        ],
        "teams": [
            "management (경영기획팀)",
            "robotics (로보틱스팀)",
            "software (SW팀)",
            "strategy (기술전략팀)",
            "raqa (RA/QA팀)"
        ]
    }


# Serve frontend HTML files
@app.get("/login.html")
async def login_page():
    """Serve login page"""
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


@app.get("/admin.html")
async def admin_page():
    """Serve admin dashboard page"""
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))


@app.get("/admin")
async def admin_redirect():
    """Redirect /admin to /admin.html"""
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))


@app.get("/")
async def index_page():
    """Serve main dashboard page"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": "VibeOps API",
        "version": "0.2.0",
        "message": "Frontend not found. API is running."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
