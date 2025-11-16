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


# ============================================================================
# GDPR Compliance Models
# ============================================================================


class ConsentRecord(Base):
    """
    GDPR Article 7 - Conditions for consent.

    Tracks user consent for various data processing activities.
    Consent must be freely given, specific, informed, and unambiguous.
    """
    __tablename__ = "consent_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Consent details
    purpose = Column(String(100), nullable=False, index=True)  # analytics, marketing, profiling, etc.
    purpose_description = Column(Text, nullable=False)  # Clear description shown to user
    consent_given = Column(Boolean, nullable=False, index=True)
    consent_method = Column(String(50), nullable=False)  # checkbox, api, email, etc.

    # Legal basis (GDPR Article 6)
    legal_basis = Column(String(50), nullable=False)  # consent, contract, legal_obligation, vital_interest, public_task, legitimate_interest

    # Granular consent categories
    consent_category = Column(String(50), nullable=False, index=True)  # essential, functional, analytics, marketing, third_party

    # Withdrawal tracking
    withdrawn_at = Column(DateTime(timezone=True), nullable=True, index=True)
    withdrawal_method = Column(String(50), nullable=True)

    # Audit trail
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    consent_version = Column(String(20), nullable=False)  # Version of terms/privacy policy

    # Expiration (some consents may expire after a period)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Timestamps
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index("idx_consent_user_purpose", "user_id", "purpose", "consent_given"),
        Index("idx_consent_active", "user_id", "consent_given", "withdrawn_at"),
        Index("idx_consent_category", "consent_category", "consent_given"),
        Index("idx_consent_expiration", "expires_at", "consent_given"),
    )

    def __repr__(self):
        return f"<ConsentRecord(id={self.id}, user_id={self.user_id}, purpose={self.purpose}, given={self.consent_given})>"


class DataRequest(Base):
    """
    GDPR Articles 15, 17, 20 - Data Subject Access Requests (DSAR).

    Tracks requests for:
    - Article 15: Right to access (data export)
    - Article 17: Right to erasure (right to be forgotten)
    - Article 20: Right to data portability
    """
    __tablename__ = "data_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Request details
    request_type = Column(String(50), nullable=False, index=True)  # access, erasure, portability, rectification, restriction
    request_status = Column(String(50), nullable=False, index=True)  # pending, in_progress, completed, rejected, failed
    priority = Column(String(20), default="normal")  # low, normal, high, urgent

    # Request metadata
    description = Column(Text, nullable=True)  # User's description/reason
    requested_data_types = Column(JSON, nullable=True)  # Specific data types requested (for access/portability)

    # Processing details
    assigned_to = Column(String(100), nullable=True)  # DPO or admin handling request
    rejection_reason = Column(Text, nullable=True)  # If rejected, why

    # Completion details
    completed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_by = Column(String(100), nullable=True)  # Admin who completed

    # Data export details (for access/portability requests)
    export_format = Column(String(20), nullable=True)  # json, csv, pdf
    export_file_path = Column(String(500), nullable=True)  # Path to exported data (encrypted storage)
    export_file_hash = Column(String(64), nullable=True)  # SHA-256 hash for integrity
    export_expires_at = Column(DateTime(timezone=True), nullable=True)  # Temporary download link expiration
    download_count = Column(Integer, default=0)  # Track downloads

    # Erasure details (for deletion requests)
    erasure_method = Column(String(50), nullable=True)  # soft_delete, anonymization, hard_delete
    data_deleted = Column(JSON, nullable=True)  # Summary of deleted data
    anonymization_applied = Column(Boolean, default=False)

    # Legal holds (prevent deletion during investigations)
    legal_hold = Column(Boolean, default=False, nullable=False, index=True)
    legal_hold_reason = Column(Text, nullable=True)
    legal_hold_placed_at = Column(DateTime(timezone=True), nullable=True)
    legal_hold_released_at = Column(DateTime(timezone=True), nullable=True)

    # Verification (identity verification required for sensitive requests)
    verification_required = Column(Boolean, default=True, nullable=False)
    verification_method = Column(String(50), nullable=True)  # email, phone, id_document, video_call
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(100), nullable=True)

    # Audit trail
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # SLA tracking (GDPR requires response within 30 days)
    due_date = Column(DateTime(timezone=True), nullable=False, index=True)  # Auto-set to +30 days
    sla_breached = Column(Boolean, default=False, nullable=False, index=True)

    # Timestamps
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index("idx_data_request_user", "user_id", "request_type", "request_status"),
        Index("idx_data_request_status", "request_status", "due_date"),
        Index("idx_data_request_sla", "sla_breached", "request_status"),
        Index("idx_data_request_legal_hold", "legal_hold", "user_id"),
    )

    def __repr__(self):
        return f"<DataRequest(id={self.id}, type={self.request_type}, status={self.request_status}, user_id={self.user_id})>"


class DataRetentionPolicy(Base):
    """
    GDPR Article 5(1)(e) - Storage limitation principle.

    Defines retention policies for different data types.
    Data should be kept no longer than necessary for the purposes for which it is processed.
    """
    __tablename__ = "data_retention_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Policy details
    policy_name = Column(String(255), nullable=False, unique=True, index=True)
    data_type = Column(String(100), nullable=False, index=True)  # user_data, audit_logs, artifacts, sessions, etc.
    description = Column(Text, nullable=False)

    # Retention rules
    retention_period_days = Column(Integer, nullable=False)  # How long to keep data
    retention_basis = Column(String(100), nullable=False)  # legal_requirement, business_need, consent, contract

    # Auto-deletion settings
    auto_delete_enabled = Column(Boolean, default=True, nullable=False)
    delete_method = Column(String(50), nullable=False, default="soft_delete")  # soft_delete, anonymization, hard_delete

    # Exceptions
    legal_hold_exempt = Column(Boolean, default=False, nullable=False)  # Can this be deleted during legal holds?
    minimum_retention_days = Column(Integer, nullable=True)  # Minimum retention (e.g., for legal compliance)

    # Applicable regulations
    regulations = Column(JSON, nullable=True)  # ["GDPR", "HIPAA", "PCI-DSS", "SOX"]

    # Policy status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Archival settings
    archive_after_days = Column(Integer, nullable=True)  # Archive before deletion
    archive_location = Column(String(255), nullable=True)  # S3 bucket, cold storage, etc.

    # Approval and compliance
    approved_by = Column(String(100), nullable=True)  # DPO or legal team approval
    approved_at = Column(DateTime(timezone=True), nullable=True)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    next_review_date = Column(DateTime(timezone=True), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_retention_data_type", "data_type", "is_active"),
        Index("idx_retention_review", "next_review_date", "is_active"),
    )

    def __repr__(self):
        return f"<DataRetentionPolicy(id={self.id}, name={self.policy_name}, retention_days={self.retention_period_days})>"


class PrivacySettings(Base):
    """
    User privacy preferences and settings.

    Allows users to control how their data is used and shared.
    """
    __tablename__ = "privacy_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Communication preferences
    email_marketing_enabled = Column(Boolean, default=False, nullable=False)
    email_product_updates = Column(Boolean, default=True, nullable=False)
    email_security_alerts = Column(Boolean, default=True, nullable=False)

    # Data processing preferences
    analytics_enabled = Column(Boolean, default=True, nullable=False)
    personalization_enabled = Column(Boolean, default=True, nullable=False)
    third_party_sharing = Column(Boolean, default=False, nullable=False)

    # AI/ML processing
    ai_training_opt_in = Column(Boolean, default=False, nullable=False)  # Can data be used for AI training?
    profiling_enabled = Column(Boolean, default=False, nullable=False)  # Automated decision-making

    # Data retention preferences
    custom_retention_period = Column(Integer, nullable=True)  # User-requested shorter retention (days)

    # Export/portability preferences
    preferred_export_format = Column(String(20), default="json")  # json, csv, pdf

    # Privacy level presets
    privacy_level = Column(String(20), default="balanced")  # minimal, balanced, convenience

    # Cookie preferences
    essential_cookies = Column(Boolean, default=True, nullable=False)  # Always true (required for functionality)
    functional_cookies = Column(Boolean, default=True, nullable=False)
    analytics_cookies = Column(Boolean, default=False, nullable=False)
    marketing_cookies = Column(Boolean, default=False, nullable=False)

    # Session preferences
    remember_me = Column(Boolean, default=False, nullable=False)
    session_timeout_minutes = Column(Integer, default=60)

    # Data sharing controls
    share_with_partners = Column(Boolean, default=False, nullable=False)
    share_for_research = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)  # User last reviewed settings

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<PrivacySettings(id={self.id}, user_id={self.user_id}, privacy_level={self.privacy_level})>"


class CookieConsent(Base):
    """
    Cookie consent tracking for GDPR compliance.

    Tracks cookie consent per user session/device.
    """
    __tablename__ = "cookie_consents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Session/device identification
    session_id = Column(String(255), nullable=True, index=True)
    device_fingerprint = Column(String(64), nullable=True, index=True)  # Hash of device characteristics

    # Consent details
    essential_accepted = Column(Boolean, default=True, nullable=False)  # Always true
    functional_accepted = Column(Boolean, default=False, nullable=False)
    analytics_accepted = Column(Boolean, default=False, nullable=False)
    marketing_accepted = Column(Boolean, default=False, nullable=False)

    # Consent metadata
    consent_method = Column(String(50), nullable=False)  # banner, settings_page, implicit
    banner_version = Column(String(20), nullable=False)  # Track which banner version was shown

    # Geolocation (determines which privacy laws apply)
    geo_country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    geo_region = Column(String(100), nullable=True)

    # Technical details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)  # Consents expire after 12 months

    # Timestamps
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index("idx_cookie_consent_user", "user_id", "granted_at"),
        Index("idx_cookie_consent_session", "session_id", "expires_at"),
        Index("idx_cookie_consent_device", "device_fingerprint", "expires_at"),
    )

    def __repr__(self):
        return f"<CookieConsent(id={self.id}, user_id={self.user_id}, analytics={self.analytics_accepted}, marketing={self.marketing_accepted})>"


class DataBreachIncident(Base):
    """
    GDPR Article 33/34 - Breach notification requirements.

    Tracks data breach incidents and notifications.
    Must notify supervisory authority within 72 hours of becoming aware.
    """
    __tablename__ = "data_breach_incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Incident details
    incident_id = Column(String(50), nullable=False, unique=True, index=True)  # Public incident reference
    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical
    status = Column(String(50), nullable=False, index=True)  # detected, investigating, contained, notified, resolved

    # Description
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    root_cause = Column(Text, nullable=True)

    # Breach classification
    breach_type = Column(String(100), nullable=False)  # unauthorized_access, data_loss, ransomware, insider_threat, etc.
    attack_vector = Column(String(100), nullable=True)  # phishing, sql_injection, brute_force, etc.

    # Impact assessment
    affected_user_count = Column(Integer, nullable=True)
    affected_data_types = Column(JSON, nullable=False)  # ["email", "password", "pii", "financial", "health"]
    risk_to_individuals = Column(String(20), nullable=False)  # low, medium, high

    # Affected users
    affected_user_ids = Column(JSON, nullable=True)  # List of user IDs (encrypted)

    # Containment
    contained_at = Column(DateTime(timezone=True), nullable=True, index=True)
    containment_measures = Column(Text, nullable=True)

    # Notification requirements
    requires_authority_notification = Column(Boolean, nullable=False, index=True)  # Article 33
    requires_individual_notification = Column(Boolean, nullable=False, index=True)  # Article 34

    # Authority notification (72-hour deadline)
    authority_notified_at = Column(DateTime(timezone=True), nullable=True, index=True)
    authority_notification_method = Column(String(50), nullable=True)
    authority_reference_number = Column(String(100), nullable=True)
    notification_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    deadline_met = Column(Boolean, nullable=True, index=True)

    # Individual notifications
    individuals_notified_at = Column(DateTime(timezone=True), nullable=True)
    individuals_notification_method = Column(String(50), nullable=True)  # email, mail, in_app
    notification_template_id = Column(String(100), nullable=True)

    # Remediation
    remediation_steps = Column(JSON, nullable=True)
    remediation_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Responsible parties
    discovered_by = Column(String(100), nullable=True)
    assigned_to = Column(String(100), nullable=True)  # DPO, security team
    dpo_notified_at = Column(DateTime(timezone=True), nullable=True)

    # Costs and impact
    estimated_cost = Column(Float, nullable=True)
    downtime_minutes = Column(Integer, nullable=True)

    # Lessons learned
    post_incident_review_completed = Column(Boolean, default=False)
    lessons_learned = Column(Text, nullable=True)
    preventive_measures = Column(JSON, nullable=True)

    # Timestamps
    detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=True)  # Estimated time breach occurred
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_breach_status", "status", "severity", "detected_at"),
        Index("idx_breach_notification", "requires_authority_notification", "authority_notified_at"),
        Index("idx_breach_deadline", "notification_deadline", "deadline_met"),
    )

    def __repr__(self):
        return f"<DataBreachIncident(id={self.id}, incident_id={self.incident_id}, severity={self.severity}, status={self.status})>"
