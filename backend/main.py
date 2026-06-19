import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import engine, Base
import models
from routers import auth, family, storage, folders, files
from config import FRONTEND_URL

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Family Document Management System",
    description="Full-stack family vault powered by Google Drive or Mega storage",
    version="1.0.0"
)

# CORS Configuration
# Allows requests from a separate frontend server if running in dev mode
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, allow all, or configure: [FRONTEND_URL]
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

# Route root requests to index.html
@app.get("/")
def read_root():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Family Document Management System Backend is running. Frontend index.html not found."}
