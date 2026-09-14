from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

_sqlite = settings.database_url.startswith("sqlite")
_engine_options = {
    "future": True,
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False} if _sqlite else {},
}
# Supabase's session pooler has a small per-project connection quota. Keep
# the web process deliberately below that quota so reloads/workers cannot
# exhaust all 15 sessions and prevent the application from starting.
if not _sqlite:
    _engine_options.update(pool_size=3, max_overflow=1, pool_timeout=15, pool_recycle=1800)
engine = create_engine(settings.database_url, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
