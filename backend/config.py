import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# App Settings
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")

# Database Settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./family_documents.db")

# JWT Authentication Settings
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-family-document-vault-key-1234567890")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) # Default 24 hours

# Mega Storage Settings
MEGA_EMAIL = os.getenv("MEGA_EMAIL", "")
MEGA_PASSWORD = os.getenv("MEGA_PASSWORD", "")
