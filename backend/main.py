import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base, run_migrations
import models
from routers import auth, family, storage, folders, files, recycle_bin, search, dashboard, share, views
from config import CORS_ORIGINS, IS_DEFAULT_JWT_SECRET

# Create database tables
Base.metadata.create_all(bind=engine)
run_migrations()

# JWT Secret Key Security Validation
if IS_DEFAULT_JWT_SECRET:
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("SECURITY CRITICAL: Default JWT_SECRET is used in a production environment! Server startup aborted.")
    else:
        print("WARNING: Using default JWT secret key. This is unsafe for production deployment.")

app = FastAPI(
    title="Family Document Management System",
    description="Full-stack family vault powered by Google Drive or Mega storage",
    version="1.0.0"
)

# CORS Configuration
# Restricted to CORS_ORIGINS configured in config.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST API routers
app.include_router(auth.router)
app.include_router(family.router)
app.include_router(storage.router)
app.include_router(folders.router)
app.include_router(files.router)
app.include_router(recycle_bin.router)
app.include_router(search.router)
app.include_router(dashboard.router)
app.include_router(share.router)
app.include_router(views.router)

# Mount Frontend Static Files
# Path to the frontend directory relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
frontend_path = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

# Ensure the frontend folder exists
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path)
    os.makedirs(os.path.join(frontend_path, "css"), exist_ok=True)
    os.makedirs(os.path.join(frontend_path, "js"), exist_ok=True)

# Register static files mounting last so that API routes take precedence
# Mount /css, /js, and other folders
app.mount("/css", StaticFiles(directory=os.path.join(frontend_path, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(frontend_path, "js")), name="js")



# Mount the entire frontend directory at the root to serve all HTML files (login.html, dashboard.html, etc.)
# This must be the last route registered so API routes take precedence.
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
