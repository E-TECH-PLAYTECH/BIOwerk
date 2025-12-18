"""
Enterprise-grade TLS/HTTPS configuration and certificate management.

This module provides:
- SSL context configuration with secure defaults
- Certificate validation and loading
- mTLS (mutual TLS) support
- Certificate generation utilities for development
- Production-ready TLS settings
 - Operational guidance for CA-issued certificate lifecycle and revocation hygiene
"""
import ssl
import os
import socket
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import logging
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID

logger = logging.getLogger(__name__)

# Operational reference for platform engineers maintaining TLS in regulated environments.
CA_CERTIFICATE_OPERATIONS = """
CA-issued certificate operational checklist:
- Acquisition: Request server certificates through the approved corporate CA or ACME/PKI automation
  workflow with the correct common name and SAN entries for every routable hostname and IP.
- Chain validation: Confirm the full chain is present (server + intermediate(s)) and verifies with
  `openssl verify -CAfile <trusted-bundle.pem> <server-cert.pem>` before deployment.
- Key protection: Store private keys in the designated secret manager or HSM-backed path with
  600/owner-only permissions and documented rotation procedures.
- Deployment: Ship cert/key/chain as atomic updates, reload listeners, and verify with
  `openssl s_client -connect host:port -servername <dns> -showcerts`.
- Revocation hygiene: Enable OCSP stapling where supported and ensure CRL/OCSP URLs in the
  certificate are reachable from the host. Maintain scheduled jobs (or load balancer settings) to
  refresh OCSP responses and rotate certificates ahead of expiry. If your load balancer terminates
  TLS, confirm OCSP stapling is enabled and that CRL distribution endpoints are reachable during
  health checks.
- Monitoring: Track expiry, OCSP freshness, and handshake errors in observability dashboards with
  environment labels (development/staging/production) for rapid triage. Alert when certs fall back
  to weak cipher bundles or below the mandated minimum TLS version.
"""


class TLSConfig:
    """Enterprise TLS configuration with security best practices."""

    # Secure TLS cipher suites (OWASP recommended)
    # Prioritizes forward secrecy (ECDHE) and modern ciphers (AES-GCM, ChaCha20)
    SECURE_CIPHERS = ":".join([
        # TLS 1.3 ciphers (preferred)
        "TLS_AES_256_GCM_SHA384",
        "TLS_AES_128_GCM_SHA256",
        "TLS_CHACHA20_POLY1305_SHA256",
        # TLS 1.2 ciphers (backward compatibility)
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-AES128-GCM-SHA256",
    ])

    # TLS version mapping
    TLS_VERSIONS = {
        "TLSv1.2": ssl.TLSVersion.TLSv1_2,
        "TLSv1.3": ssl.TLSVersion.TLSv1_3,
    }
    PRODUCTION_ENVIRONMENTS = {"production", "staging"}

    @staticmethod
    def _normalize_environment(environment: Optional[str]) -> str:
        """
        Normalize an environment name, defaulting to DEVELOPMENT semantics.

        The environment influences validation strictness for TLS posture.
        """
        return (environment or os.getenv("ENVIRONMENT") or "development").strip().lower()

    @staticmethod
    def _load_certificate(cert_file: Path) -> x509.Certificate:
        with open(cert_file, "rb") as f:
            cert_data = f.read()
            return x509.load_pem_x509_certificate(cert_data, default_backend())

    @staticmethod
    def _load_private_key(key_file: Path):
        with open(key_file, "rb") as f:
            key_data = f.read()
            return serialization.load_pem_private_key(
                key_data, password=None, backend=default_backend()
            )

    @classmethod
    def _validate_certificate_strength(
        cls, cert: x509.Certificate
    ) -> tuple[list[str], list[str]]:
        """
        Validate certificate strength properties and SAN coverage.

        Returns:
            Tuple of (errors, san_entries)
        """
        errors: list[str] = []
        san_entries: list[str] = []
        san_extension_present = True

        try:
            san_extension = cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            for entry in san_extension:
                san_entries.append(str(entry.value))
        except x509.ExtensionNotFound:
            san_extension_present = False
            errors.append("Certificate is missing a Subject Alternative Name (SAN) extension.")

        if san_extension_present and not san_entries:
            errors.append("Certificate does not declare any DNS or IP SAN entries.")

        public_key = cert.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            if public_key.key_size < 2048:
                errors.append("RSA public key size is below 2048 bits.")
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            if public_key.curve.key_size < 256:
                errors.append(f"Elliptic curve key size is below 256 bits: {public_key.curve.name}.")
        else:
            errors.append(f"Unsupported public key type: {public_key.__class__.__name__}.")

        sig_hash = cert.signature_hash_algorithm
        if sig_hash and sig_hash.name.lower() in {"md5", "sha1"}:
            errors.append(f"Weak signature hash algorithm detected: {sig_hash.name}.")

        return errors, san_entries

    @staticmethod
    def _validate_hostname_coverage(
        expected_hostnames: Optional[list[str]],
        san_entries: list[str],
    ) -> list[str]:
        if not expected_hostnames:
            return []

        sanitized_expected = {host.strip().lower() for host in expected_hostnames if host and host.strip()}
        if not sanitized_expected:
            return []

        san_lower = {san.lower() for san in san_entries}
        missing = [host for host in sanitized_expected if host not in san_lower]
        if missing:
            return [f"Certificate SAN does not cover expected hostnames: {', '.join(sorted(missing))}"]
        return []

    @staticmethod
    def _extract_revocation_metadata(cert: x509.Certificate) -> tuple[list[str], list[str]]:
        ocsp_urls: list[str] = []
        crl_urls: list[str] = []

        try:
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
            for access_description in aia:
                if access_description.access_method == AuthorityInformationAccessOID.OCSP:
                    ocsp_urls.append(access_description.access_location.value)
        except x509.ExtensionNotFound:
            pass

        try:
            crl_dist_points = cert.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS).value
            for point in crl_dist_points:
                if point.full_name:
                    crl_urls.extend([name.value for name in point.full_name])
        except x509.ExtensionNotFound:
            pass

        return ocsp_urls, crl_urls

    @classmethod
    def _validate_private_key_strength(cls, private_key) -> list[str]:
        errors: list[str] = []

        if isinstance(private_key, rsa.RSAPrivateKey):
            if private_key.key_size < 2048:
                errors.append("RSA private key size must be at least 2048 bits.")
        elif isinstance(private_key, ec.EllipticCurvePrivateKey):
            if private_key.curve.key_size < 256:
                errors.append(f"Elliptic curve private key size is below 256 bits: {private_key.curve.name}.")
        else:
            errors.append(f"Unsupported private key type: {private_key.__class__.__name__}.")

        return errors

    @staticmethod
    def _validate_key_certificate_pair(private_key, cert: x509.Certificate) -> Optional[str]:
        cert_public_key = cert.public_key()
        private_public_key = private_key.public_key()

        if isinstance(cert_public_key, rsa.RSAPublicKey) and isinstance(private_public_key, rsa.RSAPublicKey):
            if cert_public_key.public_numbers() != private_public_key.public_numbers():
                return "TLS private key does not match the certificate's public key."
        elif isinstance(cert_public_key, ec.EllipticCurvePublicKey) and isinstance(private_public_key, ec.EllipticCurvePublicKey):
            cert_numbers = cert_public_key.public_numbers()
            private_numbers = private_public_key.public_numbers()
            if cert_numbers.x != private_numbers.x or cert_numbers.y != private_numbers.y:
                return "Elliptic curve private key does not match the certificate's public key."
        elif cert_public_key.__class__ != private_public_key.__class__:
            return (
                "Certificate public key type does not match private key type: "
                f"{cert_public_key.__class__.__name__} vs {private_public_key.__class__.__name__}."
            )

        return None

    @classmethod
    def _enforce_environmental_tls_policy(
        cls,
        environment: str,
        metadata: dict,
        key_errors: list[str],
        cert_errors: list[str],
        hostname_errors: list[str],
        ciphers: Optional[str],
        min_version: Optional[str],
        expect_ocsp: bool,
        expect_crl: bool,
    ) -> None:
        is_prod_like = environment in cls.PRODUCTION_ENVIRONMENTS

        if is_prod_like and not ciphers:
            raise ValueError(
                "Production/staging require an explicit TLS cipher suite. "
                "Set TLS_CIPHERS (or pass ciphers) to a vetted value such as TLSConfig.SECURE_CIPHERS."
            )

        if is_prod_like and not min_version:
            raise ValueError(
                "Production/staging require an explicit minimum TLS version. "
                "Set TLS_MIN_VERSION (or pass min_version) to TLSv1.2 or TLSv1.3."
            )

        enforced_errors: list[str] = []
        if is_prod_like and metadata.get("is_self_signed"):
            enforced_errors.append("Self-signed certificates are not permitted in staging/production.")
        enforced_errors.extend(key_errors)
        enforced_errors.extend(cert_errors)
        enforced_errors.extend(hostname_errors)

        if expect_ocsp and not metadata.get("ocsp_urls"):
            message = "OCSP stapling/endpoint is expected but certificate does not advertise an OCSP URL."
            if is_prod_like:
                enforced_errors.append(message)
            else:
                logger.warning(message)
        if expect_crl and not metadata.get("crl_urls"):
            message = "CRL distribution points expected but certificate is missing CRL URLs."
            if is_prod_like:
                enforced_errors.append(message)
            else:
                logger.warning(message)

        if is_prod_like and enforced_errors:
            raise ValueError(
                "TLS configuration failed production/staging validation: "
                + "; ".join(enforced_errors)
            )


    @classmethod
    def create_ssl_context(
        cls,
        cert_file: str,
        key_file: str,
        ca_file: Optional[str] = None,
        verify_client: bool = False,
        min_version: str = "TLSv1.2",
        ciphers: Optional[str] = None,
        environment: Optional[str] = None,
        expected_hostnames: Optional[list[str]] = None,
        expect_ocsp_stapling: bool = False,
        expect_crl_distribution: bool = False,
    ) -> ssl.SSLContext:
        """
        Create a secure SSL context for HTTPS servers.

        Args:
            cert_file: Path to server certificate file (PEM format)
            key_file: Path to server private key file (PEM format)
            ca_file: Path to CA certificate for client verification (optional)
            verify_client: Require and verify client certificates (mTLS)
            min_version: Minimum TLS version ("TLSv1.2" or "TLSv1.3")
            ciphers: Custom cipher suite (None = use secure defaults)
            environment: Deployment environment driving validation strictness
            expected_hostnames: Hostnames that must be present in the certificate SAN set
            expect_ocsp_stapling: Whether the deployment expects OCSP stapling/URLs to be present
            expect_crl_distribution: Whether CRL distribution points are required on the certificate

        Returns:
            Configured SSL context

        Raises:
            FileNotFoundError: If certificate or key files don't exist
            ssl.SSLError: If certificate/key loading fails
            ValueError: If configuration is invalid
        """
        normalized_env = cls._normalize_environment(environment)

        # Validate certificate files exist
        cert_path = Path(cert_file)
        key_path = Path(key_file)

        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_file}")
        if not key_path.exists():
            raise FileNotFoundError(f"Private key file not found: {key_file}")

        # Validate CA file if client verification is enabled
        if verify_client:
            if not ca_file:
                raise ValueError("ca_file is required when verify_client=True")
            ca_path = Path(ca_file)
            if not ca_path.exists():
                raise FileNotFoundError(f"CA certificate file not found: {ca_file}")

        normalized_env = cls._normalize_environment(environment)

        cert = cls._load_certificate(cert_path)
        metadata = cls.validate_certificate(cert_file, cert=cert)
        cert_strength_errors = list(metadata.get("strength_errors", []))
        private_key = cls._load_private_key(key_path)
        key_strength_errors = cls._validate_private_key_strength(private_key)
        hostname_errors = cls._validate_hostname_coverage(expected_hostnames, metadata.get("san_entries", []))
        key_cert_error = cls._validate_key_certificate_pair(private_key, cert)
        if key_cert_error:
            key_strength_errors.append(key_cert_error)
            if normalized_env not in cls.PRODUCTION_ENVIRONMENTS:
                logger.error("TLS private key and certificate mismatch detected: %s", key_cert_error)

        cls._enforce_environmental_tls_policy(
            environment=normalized_env,
            metadata=metadata,
            key_errors=key_strength_errors,
            cert_errors=cert_strength_errors,
            hostname_errors=hostname_errors,
            ciphers=ciphers,
            min_version=min_version,
            expect_ocsp=expect_ocsp_stapling,
            expect_crl=expect_crl_distribution,
        )

        if key_strength_errors or cert_strength_errors or hostname_errors or metadata.get("is_self_signed"):
            logger.warning(
                "TLS material validation warnings detected (%s environment): %s",
                normalized_env,
                "; ".join(
                    key_strength_errors
                    + cert_strength_errors
                    + hostname_errors
                    + (["certificate is self-signed"] if metadata.get("is_self_signed") else [])
                ),
            )

        # Create SSL context with secure defaults
        # PROTOCOL_TLS_SERVER: Modern protocol selection, server mode
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

        # Load server certificate and private key
        try:
            context.load_cert_chain(
                certfile=str(cert_path),
                keyfile=str(key_path)
            )
            logger.info(f"Loaded TLS certificate: {cert_file}")
        except ssl.SSLError as e:
            logger.error(f"Failed to load TLS certificate/key: {e}")
            raise

        # Configure minimum TLS version
        if not min_version:
            raise ValueError("min_version is required and must be set explicitly.")

        if min_version not in cls.TLS_VERSIONS:
            raise ValueError(
                f"Invalid TLS version: {min_version}. "
                f"Must be one of: {list(cls.TLS_VERSIONS.keys())}"
            )

        context.minimum_version = cls.TLS_VERSIONS[min_version]
        logger.info(f"Minimum TLS version: {min_version}")
        if normalized_env == "production" and min_version == "TLSv1.2":
            logger.warning("TLSv1.2 selected for production. Prefer TLSv1.3 where possible.")

        # Set secure cipher suite
        cipher_suite = ciphers or cls.SECURE_CIPHERS
        try:
            context.set_ciphers(cipher_suite)
            logger.info("Configured secure TLS cipher suite")
        except ssl.SSLError as e:
            if normalized_env in cls.PRODUCTION_ENVIRONMENTS:
                raise ValueError(
                    f"Failed to apply configured TLS cipher suite in {normalized_env}: {e}"
                ) from e
            logger.warning(f"Failed to set custom ciphers, using defaults: {e}")

        # Configure client certificate verification (mTLS)
        if verify_client:
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(cafile=ca_file)
            logger.info(f"Client certificate verification enabled (mTLS)")
            logger.info(f"Loaded CA certificate: {ca_file}")
        else:
            context.verify_mode = ssl.CERT_NONE
            logger.info("Client certificate verification disabled")

        # Security hardening options
        context.options |= ssl.OP_NO_SSLv2  # Disable SSLv2 (insecure)
        context.options |= ssl.OP_NO_SSLv3  # Disable SSLv3 (POODLE vulnerability)
        context.options |= ssl.OP_NO_TLSv1  # Disable TLSv1.0 (deprecated)
        context.options |= ssl.OP_NO_TLSv1_1  # Disable TLSv1.1 (deprecated)
        context.options |= ssl.OP_NO_COMPRESSION  # Disable compression (CRIME attack)
        context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE  # Server chooses cipher
        context.options |= ssl.OP_SINGLE_DH_USE  # Use new DH key for each session
        context.options |= ssl.OP_SINGLE_ECDH_USE  # Use new ECDH key for each session

        logger.info("SSL context created with enterprise security settings")
        return context

    @classmethod
    def _normalize_environment(cls, environment: Optional[str]) -> str:
        """Normalize environment values to a lowercase token."""

        if not environment:
            return "development"

        return environment.strip().lower()

    @classmethod
    def validate_certificate(
        cls,
        cert_file: str,
        expected_hostnames: Optional[list[str]] = None,
        environment: str = os.getenv("ENVIRONMENT", "development"),
    ) -> dict:
        """
        Validate a certificate and extract metadata.

        Args:
            cert_file: Path to certificate file
            expected_hostnames: Hostnames/IPs that must appear in the SAN (enforced in production)
            environment: Deployment environment (development, staging, production)

        Returns:
            Dictionary with certificate metadata:
            - subject: Certificate subject
            - issuer: Certificate issuer
            - not_before: Certificate valid from date
            - not_after: Certificate expiration date
            - days_remaining: Days until expiration
            - is_expired: Whether certificate is expired
            - is_self_signed: Whether certificate is self-signed
            - key_type: Public key algorithm
            - key_size: Public key size
            - san_dns: Subject Alternative Name DNS entries
            - san_ips: Subject Alternative Name IP entries
            - ocsp_urls: Authority Information Access OCSP responders
            - crl_urls: CRL Distribution Point URLs

        Raises:
            FileNotFoundError: If certificate file doesn't exist
            ssl.SSLError: If certificate is invalid
            ValueError: If certificate fails compliance checks
        """
        import cryptography.x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID, NameOID
        from cryptography.hazmat.primitives.asymmetric import rsa, ec

        normalized_env = cls._normalize_environment(environment)

        cert_path = Path(cert_file)
        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_file}")

        cert = cert or cls._load_certificate(cert_path)

        # Extract metadata
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
        cert_strength_errors, san_entries = cls._validate_certificate_strength(cert)
        ocsp_urls, crl_urls = cls._extract_revocation_metadata(cert)
        common_name_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        common_name = common_name_attrs[0].value if common_name_attrs else ""
        common_name_value = common_name.lower() if common_name else ""

        # Public key validation
        public_key = cert.public_key()
        key_size = getattr(public_key, "key_size", None)

        if isinstance(public_key, rsa.RSAPublicKey):
            key_type = "RSA"
            if not key_size or key_size < 2048:
                raise ValueError("RSA key size must be at least 2048 bits.")
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            key_type = f"EC-{public_key.curve.name}"
            if not key_size or key_size < 256:
                raise ValueError("Elliptic Curve key size must be at least 256 bits.")
        else:
            key_type = type(public_key).__name__
            raise ValueError(f"Unsupported public key algorithm: {key_type}")

        # SAN parsing
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
            san_dns = san_ext.get_values_for_type(cryptography.x509.DNSName)
            san_ips = san_ext.get_values_for_type(cryptography.x509.IPAddress)
        except cryptography.x509.ExtensionNotFound:
            san_dns = []
            san_ips = []

        san_dns_values = [dns.value.lower() for dns in san_dns]
        san_ip_values = [ip.exploded for ip in san_ips]

        # Ensure CN is represented in SAN to avoid mismatched hostname validation
        if common_name_value and common_name_value not in san_dns_values:
            message = f"Common Name {common_name} is not present in SAN entries."
            if normalized_env == "production":
                raise ValueError(message)
            logger.warning(message)
        elif not common_name_value:
            logger.warning("Certificate subject does not include a Common Name.")

        # Hostname enforcement
        expected = [host.lower() for host in expected_hostnames] if expected_hostnames else []
        missing_hosts = [
            host for host in expected
            if host not in san_dns_values and host not in san_ip_values
        ]
        if missing_hosts:
            message = f"Certificate SAN is missing required hostnames/IPs: {missing_hosts}"
            if normalized_env == "production":
                raise ValueError(message)
            logger.warning(message)

        # OCSP/CRL visibility
        ocsp_urls = []
        try:
            aia_ext = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
            for access_description in aia_ext:
                if access_description.access_method == AuthorityInformationAccessOID.OCSP:
                    ocsp_urls.append(access_description.access_location.value)
        except cryptography.x509.ExtensionNotFound:
            pass

        crl_urls = []
        try:
            crl_ext = cert.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS).value
            for dp in crl_ext:
                for name in dp.full_name or []:
                    crl_urls.append(name.value)
        except cryptography.x509.ExtensionNotFound:
            pass

        now = datetime.now(not_after.tzinfo)
        days_remaining = (not_after - now).days
        is_expired = now > not_after
        is_self_signed = subject == issuer

        metadata = {
            "subject": subject,
            "issuer": issuer,
            "not_before": not_before.isoformat(),
            "not_after": not_after.isoformat(),
            "days_remaining": days_remaining,
            "is_expired": is_expired,
            "is_self_signed": is_self_signed,
            "san_entries": san_entries,
            "signature_hash": cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else "unknown",
            "strength_errors": cert_strength_errors,
            "key_type": key_type,
            "key_size": key_size,
            "san_dns": san_dns_values,
            "san_ips": san_ip_values,
            "common_name": common_name,
            "ocsp_urls": ocsp_urls,
            "crl_urls": crl_urls,
        }

        # Log warnings
        if is_expired:
            logger.error(f"Certificate is EXPIRED: {cert_file}")
        elif days_remaining < 30:
            logger.warning(
                f"Certificate expires soon ({days_remaining} days): {cert_file}"
            )

        if is_self_signed:
            logger.warning(f"Certificate is self-signed: {cert_file}")
            if normalized_env == "production":
                raise ValueError("Self-signed certificates are forbidden in production.")

        if normalized_env == "production" and not ocsp_urls and not crl_urls:
            raise ValueError(
                "Certificate must expose OCSP or CRL endpoints in production to enable revocation checks."
            )
        elif not ocsp_urls and not crl_urls:
            logger.warning(
                "Certificate does not advertise OCSP or CRL endpoints. "
                "Revocation status cannot be verified in this environment."
            )

        return metadata


def get_ca_certificate_operations() -> str:
    """
    Provide human-readable operational guidance for CA-issued certificates.

    Includes steps for acquisition, chain verification, deployment, and OCSP/CRL hygiene.
    """
    return CA_CERTIFICATE_OPERATIONS.strip()


def generate_self_signed_cert(
    cert_file: str = "./certs/cert.pem",
    key_file: str = "./certs/key.pem",
    days_valid: int = 365,
    country: str = "US",
    state: str = "California",
    locality: str = "San Francisco",
    organization: str = "BIOwerk",
    common_name: str = "localhost",
    san_dns: Optional[list[str]] = None,
    san_ips: Optional[list[str]] = None,
    environment: str = os.getenv("ENVIRONMENT", "development"),
) -> None:
    """
    Generate a self-signed certificate for development/testing.

    WARNING: Self-signed certificates should NEVER be used in production!
    For production, use certificates from a trusted CA (Let's Encrypt, DigiCert, etc.)

    Args:
        cert_file: Output path for certificate file
        key_file: Output path for private key file
        days_valid: Number of days the certificate is valid
        country: Country name (2-letter code)
        state: State or province name
        locality: Locality or city name
        organization: Organization name
        common_name: Common name (hostname/domain)
        san_dns: Subject Alternative Names (DNS)
        san_ips: Subject Alternative Names (IP addresses)
        environment: Deployment environment (blocks production usage)
    """
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtensionOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    import ipaddress

    normalized_env = TLSConfig._normalize_environment(environment)
    if normalized_env == "production":
        raise ValueError("Self-signed certificate generation is forbidden in production environments.")

    # Create output directory
    cert_path = Path(cert_file)
    key_path = Path(key_file)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate private key (RSA 4096-bit for development)
    logger.info("Generating RSA 4096-bit private key...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )

    # Build subject and issuer (same for self-signed)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # Build Subject Alternative Names (SAN)
    san_list = []

    # Add common name to SAN
    san_list.append(x509.DNSName(common_name))

    # Add additional DNS names
    if san_dns:
        for dns in san_dns:
            san_list.append(x509.DNSName(dns))

    # Add IP addresses
    if san_ips:
        for ip in san_ips:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip)))

    # Always include localhost and 127.0.0.1 for development
    if common_name != "localhost":
        san_list.append(x509.DNSName("localhost"))
    san_list.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))

    # Build certificate
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=days_valid))
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256(), backend=default_backend())
    )

    # Write private key to file (PEM format, no encryption for dev)
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    os.chmod(key_path, 0o600)  # Restrict permissions (owner read/write only)
    logger.info(f"Private key written to: {key_file}")

    # Write certificate to file (PEM format)
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    logger.info(f"Certificate written to: {cert_file}")

    logger.warning(
        "Self-signed certificate generated. "
        "This is suitable for development ONLY. "
        "DO NOT use self-signed certificates in production!"
    )
    logger.info(f"Certificate valid for {days_valid} days")
    logger.info(f"Common Name: {common_name}")
    logger.info(f"Subject Alternative Names: {[str(san) for san in san_list]}")


# Convenience function for FastAPI/Uvicorn integration
def get_ssl_config_for_uvicorn(
    cert_file: str,
    key_file: str,
    ca_file: Optional[str] = None,
    verify_client: bool = False,
    min_version: str = "TLSv1.2",
    expected_hostnames: Optional[list[str]] = None,
    environment: str = os.getenv("ENVIRONMENT", "development"),
) -> dict:
    """
    Get SSL configuration dictionary for Uvicorn server.

    Args:
        cert_file: Path to certificate file
        key_file: Path to private key file
        ca_file: Path to CA certificate (for client verification)
        verify_client: Require client certificates (mTLS)
        min_version: Minimum TLS version
        expected_hostnames: Hostnames/IPs that must be present in the certificate SAN
        environment: Deployment environment

    Returns:
        Dictionary with Uvicorn SSL configuration:
        - ssl_certfile
        - ssl_keyfile
        - ssl_ca_certs (if verify_client=True)
        - ssl_cert_reqs (if verify_client=True)
        - ssl_version

    Example:
        >>> ssl_config = get_ssl_config_for_uvicorn("cert.pem", "key.pem")
        >>> uvicorn.run(app, host="0.0.0.0", port=8443, **ssl_config)
    """
    TLSConfig.validate_certificate(
        cert_file=cert_file,
        expected_hostnames=expected_hostnames or [socket.getfqdn()],
        environment=environment,
    )

    config = {
        "ssl_certfile": cert_file,
        "ssl_keyfile": key_file,
    }

    if verify_client:
        if not ca_file:
            raise ValueError("ca_file is required when verify_client=True")
        config["ssl_ca_certs"] = ca_file
        config["ssl_cert_reqs"] = ssl.CERT_REQUIRED

    # Map TLS version to ssl module constant
    if min_version == "TLSv1.3":
        config["ssl_version"] = ssl.PROTOCOL_TLS_SERVER
        config["ssl_min_version"] = ssl.TLSVersion.TLSv1_3
    else:  # TLSv1.2
        config["ssl_version"] = ssl.PROTOCOL_TLS_SERVER
        config["ssl_min_version"] = ssl.TLSVersion.TLSv1_2

    return config
