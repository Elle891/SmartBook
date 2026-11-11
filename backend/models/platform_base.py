"""SQLAlchemy base for platform-registry tables (users, otp_records, audit_logs)."""

from sqlalchemy.orm import DeclarativeBase


class PlatformBase(DeclarativeBase):
    pass
