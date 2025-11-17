"""SQLAlchemy base class and model imports."""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models here so Alembic can detect them
from src.db.models import (  # noqa: F401, E402
    Tenant,
    TenantAPIKey,
    ChatSession,
    Message,
    MessageFeedback,
)
