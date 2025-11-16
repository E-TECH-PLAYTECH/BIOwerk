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


class AuditLog(Base):
    """
    Enterprise audit log model with encryption at rest for sensitive data.

    This model captures comprehensive audit trails for:
    - Authentication events (login, logout, token refresh, MFA)
    - Authorization events (permission checks, access denials)
    - Data access (read, query, export)
    - Data modifications (create, update, delete)
    - Administrative actions (user management, config changes)
    - Security events (failed logins, suspicious activity)

    Sensitive fields are encrypted at rest using AES-256-GCM envelope encryption.
    """
    __tablename__ = "audit_logs"

    # Primary identifiers
    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), nullable=False, unique=True, index=True)  # Unique event ID for correlation

    # Event classification
    event_type = Column(String(50), nullable=False, index=True)  # AUTH, ACCESS, DATA_READ, DATA_WRITE, DATA_DELETE, ADMIN, SECURITY
    event_category = Column(String(50), nullable=False, index=True)  # authentication, authorization, data, admin, security
    event_action = Column(String(100), nullable=False, index=True)  # login, logout, create, update, delete, etc.
    event_status = Column(String(20), nullable=False, index=True)  # success, failure, error, warning
    severity = Column(String(20), nullable=False, index=True, default="INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Actor (who performed the action)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(100), nullable=True)  # Denormalized for audit trail persistence
    actor_type = Column(String(50), default="user")  # user, service, system, anonymous

    # Subject (what was acted upon)
    resource_type = Column(String(100), nullable=True, index=True)  # project, artifact, user, api_key, etc.
    resource_id = Column(String(36), nullable=True, index=True)
    resource_name = Column(String(500), nullable=True)

    # Request context
    service_name = Column(String(100), nullable=True, index=True)  # osteon, myocyte, synapse, mesh, etc.
    endpoint = Column(String(255), nullable=True, index=True)
    http_method = Column(String(10), nullable=True)
    http_status_code = Column(Integer, nullable=True)

    # Network context
    ip_address = Column(String(45), nullable=True, index=True)  # IPv4 or IPv6
    ip_address_hash = Column(String(64), nullable=True, index=True)  # Searchable hash for encrypted IP
    user_agent = Column(Text, nullable=True)
    user_agent_hash = Column(String(64), nullable=True, index=True)  # Searchable hash

    # Session context
    session_id = Column(String(255), nullable=True, index=True)
    trace_id = Column(String(100), nullable=True, index=True)  # Distributed tracing correlation ID
    request_id = Column(String(100), nullable=True, index=True)

    # Geolocation context (optional)
    geo_country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    geo_region = Column(String(100), nullable=True)
    geo_city = Column(String(100), nullable=True)

    # Data changes (encrypted at rest for sensitive data)
    changes_before = Column(JSON, nullable=True)  # State before modification
    changes_after = Column(JSON, nullable=True)  # State after modification
    request_data = Column(JSON, nullable=True)  # Request payload
    response_data = Column(JSON, nullable=True)  # Response payload

    # Encrypted sensitive fields (stores encrypted JSON from encryption service)
    changes_before_encrypted = Column(JSON, nullable=True)  # Encrypted state before
    changes_after_encrypted = Column(JSON, nullable=True)  # Encrypted state after
    request_data_encrypted = Column(JSON, nullable=True)  # Encrypted request
    response_data_encrypted = Column(JSON, nullable=True)  # Encrypted response
    ip_address_encrypted = Column(JSON, nullable=True)  # Encrypted IP address
    user_agent_encrypted = Column(JSON, nullable=True)  # Encrypted user agent

    # Error details
    error_message = Column(Text, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_stack_trace = Column(Text, nullable=True)

    # Performance metrics
    duration_ms = Column(Float, nullable=True)

    # Security context
    authentication_method = Column(String(50), nullable=True)  # jwt, api_key, oauth2, mTLS
    authorization_result = Column(String(50), nullable=True)  # allowed, denied, error
    risk_score = Column(Integer, nullable=True)  # 0-100, for anomaly detection

    # Compliance and retention
    retention_period_days = Column(Integer, nullable=True)  # Custom retention period
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Cryptographic integrity
    record_hash = Column(String(64), nullable=True)  # SHA-256 hash of critical fields for tamper detection
    encryption_key_version = Column(Integer, nullable=True)  # Track which key version was used

    # Timestamps
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)  # When event actually occurred
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # When logged

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Composite indexes for common query patterns
    __table_args__ = (
        # Query by user and time range
        Index("idx_audit_user_time", "user_id", "event_timestamp"),
        # Query by event type and status
        Index("idx_audit_event_status", "event_type", "event_status", "event_timestamp"),
        # Query by resource
        Index("idx_audit_resource", "resource_type", "resource_id", "event_timestamp"),
        # Query by service
        Index("idx_audit_service", "service_name", "endpoint", "event_timestamp"),
        # Security monitoring
        Index("idx_audit_security", "event_category", "severity", "event_timestamp"),
        # IP-based analysis
        Index("idx_audit_ip", "ip_address", "event_timestamp"),
        # Session tracking
        Index("idx_audit_session", "session_id", "event_timestamp"),
        # Archive management
        Index("idx_audit_archive", "is_archived", "created_at"),
        # Compliance queries
        Index("idx_audit_compliance", "event_category", "event_action", "user_id", "event_timestamp"),
    )

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, event_type={self.event_type}, "
            f"action={self.event_action}, status={self.event_status}, "
            f"user_id={self.user_id}, resource={self.resource_type}:{self.resource_id})>"
        )
