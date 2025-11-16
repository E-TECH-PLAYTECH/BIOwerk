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


class RetentionPolicy(Base):
    """
    Data Retention Policy model for SOC2, HIPAA, GDPR, PCI-DSS compliance.

    Defines rules for how long different types of data should be retained,
    what action to take when retention period expires, and compliance framework alignment.
    """
    __tablename__ = "retention_policies"

    # Primary identifiers
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Policy scope
    data_type = Column(String(50), nullable=False, index=True)  # user, project, artifact, execution, api_key, audit_log, session
    category_filter = Column(JSON, nullable=True)  # Optional: filter by category/subcategory
    user_filter = Column(JSON, nullable=True)  # Optional: apply to specific users
    conditions = Column(JSON, nullable=True)  # Custom conditions as JSON (field: value pairs)

    # Retention configuration
    retention_period_days = Column(Integer, nullable=False)  # How long to retain (e.g., 90, 365, 2555)
    action = Column(String(50), nullable=False, default="delete")  # archive, delete, anonymize, retain
    archive_before_delete = Column(Boolean, default=True, nullable=False)  # Always archive before deleting

    # Compliance framework
    compliance_framework = Column(String(50), nullable=False, index=True)  # soc2, hipaa, gdpr, pci_dss, ccpa, iso27001
    regulatory_citation = Column(Text, nullable=True)  # Reference to specific regulation (e.g., "HIPAA 164.530(j)(2)")

    # Policy priority and status
    priority = Column(Integer, default=0, nullable=False)  # Higher priority policies are evaluated first
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Metadata
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_enforced_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])

    # Indexes
    __table_args__ = (
        Index("idx_retention_policy_type", "data_type", "is_active"),
        Index("idx_retention_policy_framework", "compliance_framework", "is_active"),
        Index("idx_retention_policy_priority", "priority", "is_active"),
    )

    def __repr__(self):
        return f"<RetentionPolicy(id={self.id}, name={self.name}, data_type={self.data_type}, retention_days={self.retention_period_days})>"


class RetentionSchedule(Base):
    """
    Retention Schedule model for tracking when data is scheduled for deletion/archival.

    Tracks individual data items and their scheduled retention actions.
    Supports legal holds to prevent deletion during litigation or investigations.
    """
    __tablename__ = "retention_schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Data reference
    data_type = Column(String(50), nullable=False, index=True)
    data_id = Column(String(36), nullable=False, index=True)  # ID of the actual data record
    policy_id = Column(String(36), ForeignKey("retention_policies.id", ondelete="SET NULL"), nullable=True)

    # Schedule information
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)  # When to execute retention action
    action = Column(String(50), nullable=False)  # archive, delete, anonymize
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, in_progress, completed, failed

    # Legal hold (prevents deletion)
    legal_hold = Column(Boolean, default=False, nullable=False, index=True)
    legal_hold_reason = Column(Text, nullable=True)  # Reason for hold (case number, investigation details)
    legal_hold_applied_at = Column(DateTime(timezone=True), nullable=True)
    legal_hold_applied_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    legal_hold_removed_at = Column(DateTime(timezone=True), nullable=True)
    legal_hold_removed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Execution tracking
    executed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    policy = relationship("RetentionPolicy", foreign_keys=[policy_id])
    hold_applied_by_user = relationship("User", foreign_keys=[legal_hold_applied_by])
    hold_removed_by_user = relationship("User", foreign_keys=[legal_hold_removed_by])

    # Indexes
    __table_args__ = (
        Index("idx_retention_schedule_data", "data_type", "data_id"),
        Index("idx_retention_schedule_pending", "status", "scheduled_for"),
        Index("idx_retention_schedule_hold", "legal_hold", "data_type"),
    )

    def __repr__(self):
        return f"<RetentionSchedule(id={self.id}, data_type={self.data_type}, data_id={self.data_id}, action={self.action}, legal_hold={self.legal_hold})>"


class DataArchive(Base):
    """
    Data Archive model for storing archived data before deletion.

    Securely stores complete snapshots of deleted data with encryption.
    Enables data recovery if needed and maintains compliance audit trails.
    """
    __tablename__ = "data_archives"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Data reference
    data_type = Column(String(50), nullable=False, index=True)
    data_id = Column(String(36), nullable=False, index=True)  # Original ID of the data
    policy_id = Column(String(36), ForeignKey("retention_policies.id", ondelete="SET NULL"), nullable=True)

    # Archived data (encrypted)
    archived_data = Column(JSON, nullable=False)  # Encrypted complete data snapshot
    data_hash = Column(String(64), nullable=False)  # SHA-256 hash for integrity verification
    encryption_key_version = Column(Integer, nullable=True)  # Which encryption key was used

    # Archive metadata
    archive_reason = Column(String(100), default="retention_policy")  # retention_policy, manual, legal_requirement
    archive_status = Column(String(50), default="completed", nullable=False, index=True)  # pending, in_progress, completed, failed, restored

    # Restoration tracking
    restored_at = Column(DateTime(timezone=True), nullable=True)
    restored_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)  # When archive itself should be deleted

    # Relationships
    policy = relationship("RetentionPolicy", foreign_keys=[policy_id])
    restored_by = relationship("User", foreign_keys=[restored_by_user_id])

    # Indexes
    __table_args__ = (
        Index("idx_archive_data", "data_type", "data_id"),
        Index("idx_archive_status", "archive_status", "archived_at"),
        Index("idx_archive_expiration", "expires_at"),
    )

    def __repr__(self):
        return f"<DataArchive(id={self.id}, data_type={self.data_type}, data_id={self.data_id}, status={self.archive_status})>"


class RetentionAuditLog(Base):
    """
    Retention Audit Log for tracking all retention policy enforcement actions.

    Provides complete audit trail for SOC2/HIPAA/GDPR compliance reporting.
    Tracks every archival, deletion, and anonymization action.
    """
    __tablename__ = "retention_audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Action details
    data_type = Column(String(50), nullable=False, index=True)
    data_id = Column(String(36), nullable=False, index=True)
    policy_id = Column(String(36), ForeignKey("retention_policies.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False, index=True)  # archive, delete, anonymize, legal_hold_applied, legal_hold_removed

    # Execution details
    status = Column(String(50), nullable=False, index=True)  # completed, failed
    error_message = Column(Text, nullable=True)
    archive_id = Column(String(36), ForeignKey("data_archives.id", ondelete="SET NULL"), nullable=True)  # Link to archive if created

    # Actor
    executed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # NULL for automated actions
    execution_type = Column(String(50), default="automated")  # automated, manual

    # Timestamps
    executed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    policy = relationship("RetentionPolicy", foreign_keys=[policy_id])
    archive = relationship("DataArchive", foreign_keys=[archive_id])
    executor = relationship("User", foreign_keys=[executed_by])

    # Indexes
    __table_args__ = (
        Index("idx_retention_audit_action", "action", "executed_at"),
        Index("idx_retention_audit_data", "data_type", "data_id"),
        Index("idx_retention_audit_policy", "policy_id", "executed_at"),
        Index("idx_retention_audit_status", "status", "executed_at"),
    )

    def __repr__(self):
        return f"<RetentionAuditLog(id={self.id}, data_type={self.data_type}, action={self.action}, status={self.status})>"
