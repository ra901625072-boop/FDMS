from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

# Create database engine
# check_same_thread: False is needed only for SQLite to allow multiple threads
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)

# Enable foreign key support for SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations():
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    # 1. Migrate families table
    if "families" in table_names:
        columns = [col["name"] for col in inspector.get_columns("families")]
        if "secret_code_sha256" not in columns:
            with engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE families ADD COLUMN secret_code_sha256 VARCHAR(64)"))
                    conn.execute(text("CREATE UNIQUE INDEX ix_families_secret_code_sha256 ON families(secret_code_sha256)"))
                    print("Migration: Successfully added secret_code_sha256 column and index to families table.")
                except Exception as e:
                    print(f"Migration error (families): {str(e)}")

    # 2. Migrate folders table
    if "folders" in table_names:
        columns = [col["name"] for col in inspector.get_columns("folders")]
        if "deleted_at" not in columns:
            with engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE folders ADD COLUMN deleted_at DATETIME"))
                    conn.execute(text("CREATE INDEX ix_folders_deleted_at ON folders(deleted_at)"))
                    print("Migration: Successfully added deleted_at column to folders table.")
                except Exception as e:
                    print(f"Migration error (folders): {str(e)}")

    # 3. Migrate files table
    if "files" in table_names:
        columns = [col["name"] for col in inspector.get_columns("files")]
        if "deleted_at" not in columns:
            with engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE files ADD COLUMN deleted_at DATETIME"))
                    conn.execute(text("CREATE INDEX ix_files_deleted_at ON files(deleted_at)"))
                    print("Migration: Successfully added deleted_at column to files table.")
                except Exception as e:
                    print(f"Migration error (files): {str(e)}")
