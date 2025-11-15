"""SQLAlchemy models for PostgreSQL."""
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, JSON, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import uuid

from .database import Base


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth users
    auth_provider = Column(String(50), default="local")  # local, oauth2, etc.
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    executions = relationship("Execution", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"


class Project(Base):
    """Project model for organizing artifacts."""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="projects")
    artifacts = relationship("Artifact", back_populates="project", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_user_projects", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, user_id={self.user_id})>"


class Artifact(Base):
    """Artifact model for storing generated documents/spreadsheets/presentations."""
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(50), nullable=False, index=True)  # osteon, myotab, synslide
    title = Column(String(500), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    state_hash = Column(String(64), nullable=False, index=True)  # BLAKE3 hash
    mongo_id = Column(String(24), nullable=False, unique=True, index=True)  # Reference to MongoDB document
    metadata = Column(JSON, nullable=True)  # Additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="artifacts")

    # Indexes
    __table_args__ = (
        Index("idx_project_artifacts", "project_id", "kind", "created_at"),
        Index("idx_artifact_hash", "state_hash"),
    )

    def __repr__(self):
        return f"<Artifact(id={self.id}, kind={self.kind}, title={self.title}, version={self.version})>"


class Execution(Base):
    """Execution model for audit logging of all agent requests/responses."""
    __tablename__ = "executions"

    id = Column(String(36), primary_key=True)  # Uses msg.id from request
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    agent = Column(String(50), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False, index=True)
    origin = Column(String(255), nullable=True)
    target = Column(String(50), nullable=True)
    request_data = Column(JSON, nullable=False)  # Full Msg object
    response_data = Column(JSON, nullable=True)  # Full Reply object
    ok = Column(Boolean, nullable=True, index=True)  # Response status
    state_hash = Column(String(64), nullable=True, index=True)  # Response state hash
    duration_ms = Column(Float, nullable=True)  # Processing duration
    error_message = Column(Text, nullable=True)  # Error details if failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="executions")

    # Indexes
    __table_args__ = (
        Index("idx_executions_agent", "agent", "endpoint", "created_at"),
        Index("idx_executions_user", "user_id", "created_at"),
        Index("idx_executions_status", "ok", "created_at"),
    )

    def __repr__(self):
        return f"<Execution(id={self.id}, agent={self.agent}, endpoint={self.endpoint}, ok={self.ok})>"


class APIKey(Base):
    """API Key model for service-to-service authentication."""
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)  # Hashed API key
    name = Column(String(255), nullable=False)  # Friendly name for the key
    scopes = Column(JSON, nullable=True)  # List of allowed scopes/permissions
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, user_id={self.user_id})>"
