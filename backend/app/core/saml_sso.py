"""
SAML 2.0 and OAuth 2.0/OIDC Single Sign-On (SSO) Integration

Provides enterprise-grade authentication with:
- SAML 2.0 protocol support
- OAuth 2.0 / OpenID Connect (OIDC)
- Multi-tenant identity management
- Single sign-on / sign-out
- Session management
- JIT (Just-In-Time) user provisioning
"""

import logging
import hashlib
import hmac
import base64
import json
import re
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.parse import urlencode, parse_qs, urlparse
import uuid

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


# ============================================================================
# XMLDSig signature verification (shared helper)
# ============================================================================
# SECURITY: This implements real XML Digital Signature verification for SAML
# responses using the `cryptography` library (already a dependency). It replaces
# the previous "check if <Signature> element exists" pseudo-verification that
# allowed forged assertions.
#
# What it verifies (RSA-SHA256 / RSA-SHA1 over SignedInfo):
#   1. Parses XML with defusedxml (XXE protection)
#   2. Locates <ds:Signature> and its <ds:SignedInfo>/<ds:SignatureValue>
#   3. Validates each <ds:Reference> digest against the referenced XML element
#   4. Canonicalizes <ds:SignedInfo> (simplified c14n: strip whitespace between tags)
#   5. Base64-decodes <ds:SignatureValue>
#   6. Loads the IdP X.509 cert, extracts public key
#   7. Verifies the signature over canonicalized SignedInfo bytes
#
# Limitations (documented, not silent):
#   - Simplified c14n: full xmldsig c14n requires xmlsec/libxml2. This
#     implementation strips inter-tag whitespace, which handles the common
#     case of IdP-signed responses. For strict c14n compliance, integrate xmlsec.
#   - SHA1 support retained for legacy IdPs but SHA256 preferred.
# It fails closed on every error path: missing signature, missing cert,
# invalid cert, malformed SignedInfo, or signature mismatch all return False.

_DS_NS = "http://www.w3.org/2000/09/xmldsig#"
_SAML_NS_MAP = {
    "ds": _DS_NS,
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
}


def _ensure_pem(cert_value: str) -> str:
    """Wrap a raw base64 DER cert in PEM headers if needed."""
    cert_value = cert_value.strip()
    if cert_value.startswith("-----BEGIN"):
        return cert_value
    body = cert_value.replace("\n", "").replace("\r", "")
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(lines) + "\n-----END CERTIFICATE-----"


def _canonicalize_signed_info(signed_info_element) -> bytes:
    """Simplified c14n of <ds:SignedInfo>.

    Strips insignificant whitespace between elements and serializes to UTF-8.
    NOT full xmldsig c14n (requires xmlsec) but handles the common IdP
    signing case where SignedInfo has no mixed content.
    """
    from defusedxml import ElementTree as ET
    raw = ET.tostring(signed_info_element, encoding="unicode")
    canonical = re.sub(r">\s+<", "><", raw).strip()
    return canonical.encode("utf-8")


def _canonicalize_xml_element(element) -> bytes:
    """Simplified c14n for referenced XML elements."""
    from defusedxml import ElementTree as ET
    raw = ET.tostring(element, encoding="unicode")
    canonical = re.sub(r">\s+<", "><", raw).strip()
    return canonical.encode("utf-8")


def _is_ds_signature(element) -> bool:
    return element.tag == f"{{{_DS_NS}}}Signature"


def _strip_enveloped_signature(element) -> None:
    """Remove descendant ds:Signature nodes for enveloped-signature transforms."""
    for child in list(element):
        if _is_ds_signature(child):
            element.remove(child)
        else:
            _strip_enveloped_signature(child)


def _find_referenced_element(root, reference_uri: str):
    """Resolve a same-document XMLDSig reference and reject duplicate IDs."""
    if not reference_uri or not reference_uri.startswith("#"):
        logger.warning(f"Unsupported SAML Reference URI: {reference_uri!r} - rejecting.")
        return None

    target_id = reference_uri[1:]
    matches = []
    id_attrs = ("ID", "Id", "id", "{http://www.w3.org/XML/1998/namespace}id")
    for element in root.iter():
        for attr in id_attrs:
            if element.get(attr) == target_id:
                matches.append(element)
                break

    if len(matches) != 1:
        logger.warning(
            f"SAML Reference URI {reference_uri!r} resolved to {len(matches)} elements - rejecting."
        )
        return None
    return matches[0]


def _digest_algorithm(digest_method: str):
    normalized = (digest_method or "").lower()
    if "sha256" in normalized:
        return hashlib.sha256
    if "sha512" in normalized:
        return hashlib.sha512
    if "sha1" in normalized:
        return hashlib.sha1
    logger.warning(f"Unsupported SAML digest algorithm: {digest_method} - rejecting.")
    return None


def _validate_reference_digests(root, signature, signed_info) -> bool:
    """Validate XMLDSig Reference digests and bind the signature to SAML content."""
    import copy

    references = signed_info.findall("ds:Reference", _SAML_NS_MAP)
    if not references:
        logger.warning("SAML SignedInfo has no Reference elements - rejecting.")
        return False

    saw_saml_payload_reference = False
    for reference in references:
        target = _find_referenced_element(root, reference.get("URI", ""))
        if target is None:
            return False

        transforms = reference.find("ds:Transforms", _SAML_NS_MAP)
        transform_algorithms = []
        if transforms is not None:
            transform_algorithms = [
                transform.get("Algorithm", "")
                for transform in transforms.findall("ds:Transform", _SAML_NS_MAP)
            ]

        supported_transforms = {
            "",
            "http://www.w3.org/2000/09/xmldsig#enveloped-signature",
            "http://www.w3.org/2001/10/xml-exc-c14n#",
            "http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        }
        unsupported = [algo for algo in transform_algorithms if algo not in supported_transforms]
        if unsupported:
            logger.warning(f"Unsupported SAML Reference transform(s): {unsupported} - rejecting.")
            return False

        digest_method = reference.find("ds:DigestMethod", _SAML_NS_MAP)
        digest_value = reference.find("ds:DigestValue", _SAML_NS_MAP)
        if digest_method is None or digest_value is None or not (digest_value.text or "").strip():
            logger.warning("SAML Reference missing DigestMethod or DigestValue - rejecting.")
            return False

        digest_factory = _digest_algorithm(digest_method.get("Algorithm", ""))
        if digest_factory is None:
            return False

        target_copy = copy.deepcopy(target)
        if "http://www.w3.org/2000/09/xmldsig#enveloped-signature" in transform_algorithms:
            _strip_enveloped_signature(target_copy)

        digest_bytes = digest_factory(_canonicalize_xml_element(target_copy)).digest()
        try:
            expected_digest = base64.b64decode(digest_value.text.strip())
        except Exception as e:
            logger.error(f"Failed to base64-decode DigestValue: {e}")
            return False

        if not hmac.compare_digest(digest_bytes, expected_digest):
            logger.warning("SAML Reference digest mismatch - rejecting.")
            return False

        if target is root or target.tag.endswith("Assertion"):
            saw_saml_payload_reference = True

    if not saw_saml_payload_reference:
        logger.warning("SAML signature does not reference the Response or Assertion - rejecting.")
        return False
    return True


def verify_saml_xml_signature(xml_bytes: bytes, idp_certificate_pem: str) -> bool:
    """Verify an XMLDSig signature in a SAML response against the IdP cert.

    Args:
        xml_bytes: Raw SAML Response XML bytes
        idp_certificate_pem: IdP X.509 certificate (PEM or raw base64 DER)

    Returns:
        True only if valid Reference digest(s) and a valid RSA/ECDSA signature
        over <ds:SignedInfo> are present and verify against the IdP certificate's
        public key.
        False on any failure (fail-closed).
    """
    try:
        from defusedxml import ElementTree as ET
        from cryptography import x509
        from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
    except ImportError as e:
        logger.error(f"Missing crypto dependency for SAML verification: {e}")
        return False

    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        logger.error(f"SAML XML parse failed: {e}")
        return False

    signature = root.find(".//ds:Signature", _SAML_NS_MAP)
    if signature is None:
        logger.warning("SAML Response has no <ds:Signature> element - rejecting.")
        return False

    signed_info = signature.find("ds:SignedInfo", _SAML_NS_MAP)
    if signed_info is None:
        logger.warning("SAML Signature has no <ds:SignedInfo> - rejecting.")
        return False

    sig_value_elem = signature.find("ds:SignatureValue", _SAML_NS_MAP)
    if sig_value_elem is None or not (sig_value_elem.text or "").strip():
        logger.warning("SAML Signature has no <ds:SignatureValue> - rejecting.")
        return False

    if not _validate_reference_digests(root, signature, signed_info):
        return False

    sig_method = signed_info.find("ds:SignatureMethod", _SAML_NS_MAP)
    algo_attr = sig_method.get("Algorithm", "") if sig_method is not None else ""
    if "sha1" in algo_attr.lower():
        hash_algo = hashes.SHA1()
        algo_name = "SHA1"
    elif "sha256" in algo_attr.lower() or not algo_attr:
        hash_algo = hashes.SHA256()
        algo_name = "SHA256"
    elif "sha512" in algo_attr.lower():
        hash_algo = hashes.SHA512()
        algo_name = "SHA512"
    else:
        logger.warning(f"Unsupported signature algorithm: {algo_attr} - rejecting.")
        return False

    try:
        signature_bytes = base64.b64decode(sig_value_elem.text.strip())
    except Exception as e:
        logger.error(f"Failed to base64-decode SignatureValue: {e}")
        return False

    if not idp_certificate_pem:
        logger.error("No IdP certificate configured - cannot verify. Rejecting.")
        return False
    try:
        cert_pem = _ensure_pem(idp_certificate_pem)
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        public_key = cert.public_key()
    except Exception as e:
        logger.error(f"Failed to load IdP certificate: {e}")
        return False

    signed_info_bytes = _canonicalize_signed_info(signed_info)

    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                signature_bytes, signed_info_bytes, padding.PKCS1v15(), hash_algo,
            )
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature_bytes, signed_info_bytes, ec.ECDSA(hash_algo))
        else:
            logger.error(f"Unsupported key type: {type(public_key)}")
            return False
    except InvalidSignature:
        logger.warning(f"SAML signature verification FAILED (RSA-{algo_name}) - mismatch. Rejecting.")
        return False
    except Exception as e:
        logger.error(f"SAML signature verification error: {e}")
        return False

    logger.info(f"SAML signature verified OK (RSA-{algo_name}).")
    return True


class SSOProvider(str, Enum):
    """Supported SSO providers."""
    SAML = "saml"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    AZURE_AD = "azure_ad"
    OKTA = "okta"
    GOOGLE = "google"


class SAMLNameIDFormat(str, Enum):
    """SAML NameID formats."""
    PERSISTENT = "urn:oasis:names:tc:SAML:1.1:nameid-format:persistent"
    TRANSIENT = "urn:oasis:names:tc:SAML:1.1:nameid-format:transient"
    EMAIL = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    UNSPECIFIED = "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"


class SAMLBindingType(str, Enum):
    """SAML binding types."""
    HTTP_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    HTTP_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
    HTTP_ARTIFACT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Artifact"


class OIDCScope(str, Enum):
    """OpenID Connect scopes."""
    OPENID = "openid"
    PROFILE = "profile"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"


# ============================================================================
# SAML Models
# ============================================================================

class SAMLConfig(BaseModel):
    """SAML 2.0 configuration."""

    # Identity Provider (IdP) settings
    idp_entity_id: str = Field(..., description="IdP Entity ID")
    idp_sso_url: str = Field(..., description="IdP Single Sign-On URL")
    idp_slo_url: Optional[str] = Field(None, description="IdP Single Logout URL")
    idp_certificate: str = Field(..., description="IdP X.509 certificate (PEM format)")

    # Service Provider (SP) settings
    sp_entity_id: str = Field(..., description="SP Entity ID (usually app URL)")
    sp_acs_url: str = Field(..., description="SP Assertion Consumer Service URL")
    sp_slo_url: Optional[str] = Field(None, description="SP Single Logout URL")
    sp_certificate: Optional[str] = Field(None, description="SP X.509 certificate (PEM format)")
    sp_private_key: Optional[str] = Field(None, description="SP private key (PEM format)")

    # SAML settings
    name_id_format: SAMLNameIDFormat = SAMLNameIDFormat.PERSISTENT
    binding_type: SAMLBindingType = SAMLBindingType.HTTP_POST

    # Attribute mappings
    attribute_mappings: Dict[str, str] = Field(
        default_factory=lambda: {
            "uid": "urn:oid:0.9.2342.19200300.100.1.3",
            "email": "urn:oid:0.9.2342.19200300.100.1.3",
            "name": "urn:oid:2.5.4.3",
            "groups": "urn:oid:1.3.6.1.4.1.5923.1.1.1.7",
        },
        description="SAML attribute to user field mappings"
    )

    # Security settings
    sign_requests: bool = True
    encrypt_assertions: bool = False
    force_authn: bool = False

    # Tenant settings
    tenant_id: str = Field(..., description="Associated tenant ID")
    enabled: bool = True


class OIDCConfig(BaseModel):
    """OpenID Connect configuration."""

    # Provider settings
    provider_name: str = Field(..., description="Provider name (e.g., 'okta', 'azure')")
    discovery_url: str = Field(..., description="OIDC Discovery endpoint URL")
    client_id: str = Field(..., description="OAuth 2.0 Client ID")
    client_secret: str = Field(..., description="OAuth 2.0 Client Secret")

    # Redirect settings
    redirect_uri: str = Field(..., description="Redirect URI after authentication")

    # Scopes and claims
    scopes: List[OIDCScope] = Field(
        default_factory=lambda: [OIDCScope.OPENID, OIDCScope.PROFILE, OIDCScope.EMAIL],
        description="Requested scopes"
    )

    # Claim mappings
    claim_mappings: Dict[str, str] = Field(
        default_factory=lambda: {
            "sub": "uid",
            "email": "email",
            "name": "name",
            "groups": "groups",
        },
        description="OIDC claim to user field mappings"
    )

    # Security settings
    require_https: bool = True
    validate_issuer: bool = True
    validate_audience: bool = True

    # Tenant settings
    tenant_id: str = Field(..., description="Associated tenant ID")
    enabled: bool = True


class SAMLAssertion(BaseModel):
    """SAML Assertion model."""

    assertion_id: str
    issuer: str
    subject: str
    subject_format: SAMLNameIDFormat
    not_before: datetime
    not_on_or_after: datetime
    session_index: str
    attributes: Dict[str, List[str]]
    signature_valid: bool
    encrypted: bool


class OIDCToken(BaseModel):
    """OIDC Token model."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: str


class SSOUser(BaseModel):
    """SSO user information."""

    uid: str = Field(..., description="Unique user identifier from IdP")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User display name")
    groups: List[str] = Field(default_factory=list, description="User groups/roles")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional attributes")
    provider: SSOProvider
    provider_user_id: str
    last_login: datetime = Field(default_factory=lambda: datetime.now(UTC))
    jit_provisioned: bool = False


class SSOSession(BaseModel):
    """SSO session model."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    tenant_id: str
    provider: SSOProvider
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ip_address: str
    user_agent: str
    active: bool = True

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now(UTC) > self.expires_at

    def is_idle_expired(self, idle_timeout_minutes: int = 30) -> bool:
        """Check if session is idle expired."""
        idle_threshold = datetime.now(UTC) - timedelta(minutes=idle_timeout_minutes)
        return self.last_activity < idle_threshold


# ============================================================================
# SAML Manager
# ============================================================================

class SAMLManager:
    """SAML 2.0 authentication manager."""

    def __init__(self, config: SAMLConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.SAMLManager")

    def generate_auth_request(self) -> str:
        """Generate SAML AuthnRequest.

        Returns:
            SAML AuthnRequest XML (base64 encoded for HTTP-Redirect binding)
        """
        request_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(UTC).isoformat()

        authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{self.config.idp_sso_url}"
    AssertionConsumerServiceURL="{self.config.sp_acs_url}"
    ProtocolBinding="{self.config.binding_type.value}">
    <saml:Issuer>{self.config.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="{self.config.name_id_format.value}" AllowCreate="true"/>
    <samlp:RequestedAuthnContext Comparison="exact">
        <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:Password</saml:AuthnContextClassRef>
    </samlp:RequestedAuthnContext>
</samlp:AuthnRequest>"""

        # Compress and encode for HTTP-Redirect binding
        import zlib
        compressed = zlib.compress(authn_request.encode('utf-8'))
        encoded = base64.b64encode(compressed).decode('utf-8')

        self.logger.debug(f"Generated SAML AuthnRequest: {request_id}")
        return encoded

    def parse_response(self, saml_response: str) -> SAMLAssertion:
        """Parse and validate SAML Response.

        Args:
            saml_response: Base64-encoded SAML Response

        Returns:
            Parsed SAMLAssertion

        Raises:
            ValueError: If response is invalid or signature verification fails
        """
        try:
            # Decode base64
            decoded = base64.b64decode(saml_response)

            # Parse XML using defusedxml to prevent XXE attacks (SECURITY P1-04).
            # The stdlib xml.etree is vulnerable to XML External Entity attacks.
            from defusedxml import ElementTree as ET
            root = ET.fromstring(decoded)

            # Extract assertion data
            namespaces = {
                'samlp': 'urn:oasis:names:tc:SAML:2.0:protocol',
                'saml': 'urn:oasis:names:tc:SAML:2.0:assertion',
                'ds': 'http://www.w3.org/2000/09/xmldsig#'
            }

            # Get assertion
            assertion = root.find('.//saml:Assertion', namespaces)
            if assertion is None:
                raise ValueError("No Assertion found in SAML Response")

            # Extract subject
            subject_elem = assertion.find('.//saml:Subject/saml:NameID', namespaces)
            subject = subject_elem.text if subject_elem is not None else ""

            # Extract attributes
            attributes = {}
            for attr in assertion.findall('.//saml:Attribute', namespaces):
                attr_name = attr.get('Name')
                attr_values = [v.text for v in attr.findall('saml:AttributeValue', namespaces)]
                attributes[attr_name] = attr_values

            # Verify signature against IdP certificate (SECURITY P1-04)
            signature_valid = self._verify_signature(decoded)
            if not signature_valid:
                raise ValueError("SAML response signature verification failed.")

            self.logger.info(f"Parsed SAML Response for subject: {subject}")

            return SAMLAssertion(
                assertion_id=assertion.get('ID', ''),
                issuer=assertion.find('.//saml:Issuer', namespaces).text or '',
                subject=subject,
                subject_format=SAMLNameIDFormat.PERSISTENT,
                not_before=datetime.now(UTC),
                not_on_or_after=datetime.now(UTC) + timedelta(hours=1),
                session_index=uuid.uuid4().hex,
                attributes=attributes,
                signature_valid=signature_valid,
                encrypted=False
            )
        except Exception as e:
            self.logger.error(f"Failed to parse SAML Response: {e}")
            raise ValueError(f"Invalid SAML Response: {e}")

    def _verify_signature(self, saml_response: bytes) -> bool:
        """Verify SAML Response signature against the configured IdP certificate.

        SECURITY: Real XMLDSig verification via verify_saml_xml_signature().
        Fails closed on: missing signature, missing/invalid cert, signature
        mismatch. No longer accepts responses merely because a <Signature>
        element exists.
        """
        idp_cert = getattr(self.config, 'idp_certificate', None)
        return verify_saml_xml_signature(saml_response, idp_cert or "")

    def generate_logout_request(self, session_index: str) -> str:
        """Generate SAML LogoutRequest.

        Args:
            session_index: Session index from assertion

        Returns:
            SAML LogoutRequest XML (base64 encoded)
        """
        request_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(UTC).isoformat()

        logout_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:LogoutRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{self.config.idp_slo_url}">
    <saml:Issuer>{self.config.sp_entity_id}</saml:Issuer>
    <saml:NameID Format="{self.config.name_id_format.value}">user@example.com</saml:NameID>
    <samlp:SessionIndex>{session_index}</samlp:SessionIndex>
</samlp:LogoutRequest>"""

        import zlib
        compressed = zlib.compress(logout_request.encode('utf-8'))
        encoded = base64.b64encode(compressed).decode('utf-8')

        self.logger.debug(f"Generated SAML LogoutRequest: {request_id}")
        return encoded


# ============================================================================
# OIDC Manager
# ============================================================================

class OIDCManager:
    """OpenID Connect authentication manager."""

    def __init__(self, config: OIDCConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.OIDCManager")
        self._discovery_cache: Optional[Dict[str, Any]] = None

    async def get_discovery_document(self) -> Dict[str, Any]:
        """Fetch OIDC Discovery document.

        Returns:
            Discovery document with endpoints and capabilities
        """
        if self._discovery_cache:
            return self._discovery_cache

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.config.discovery_url) as resp:
                    if resp.status != 200:
                        raise ValueError(f"Discovery failed: {resp.status}")
                    self._discovery_cache = await resp.json()
                    self.logger.debug(f"Fetched OIDC discovery document from {self.config.provider_name}")
                    return self._discovery_cache
        except Exception as e:
            self.logger.error(f"Failed to fetch discovery document: {e}")
            raise

    def generate_authorization_url(self, state: str, nonce: str) -> str:
        """Generate OIDC authorization URL.

        Args:
            state: CSRF protection state
            nonce: Nonce for ID token validation

        Returns:
            Authorization URL
        """
        params = {
            'client_id': self.config.client_id,
            'response_type': 'code',
            'scope': ' '.join([s.value for s in self.config.scopes]),
            'redirect_uri': self.config.redirect_uri,
            'state': state,
            'nonce': nonce,
        }

        # This would use discovery_url in production
        auth_endpoint = f"{self.config.discovery_url.replace('/.well-known/openid-configuration', '')}/authorize"
        url = f"{auth_endpoint}?{urlencode(params)}"

        self.logger.debug(f"Generated authorization URL for {self.config.provider_name}")
        return url

    async def exchange_code_for_token(self, code: str) -> OIDCToken:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback

        Returns:
            OIDC Token
        """
        try:
            import aiohttp

            discovery = await self.get_discovery_document()
            token_endpoint = discovery.get('token_endpoint')

            if not token_endpoint:
                raise ValueError("No token_endpoint in discovery document")

            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': self.config.client_id,
                'client_secret': self.config.client_secret,
                'redirect_uri': self.config.redirect_uri,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(token_endpoint, data=data) as resp:
                    if resp.status != 200:
                        raise ValueError(f"Token exchange failed: {resp.status}")

                    token_data = await resp.json()
                    token = OIDCToken(
                        access_token=token_data['access_token'],
                        token_type=token_data.get('token_type', 'Bearer'),
                        expires_in=token_data.get('expires_in', 3600),
                        refresh_token=token_data.get('refresh_token'),
                        id_token=token_data.get('id_token'),
                        scope=token_data.get('scope', ''),
                    )

                    self.logger.info(f"Successfully exchanged code for token from {self.config.provider_name}")
                    return token
        except Exception as e:
            self.logger.error(f"Failed to exchange code for token: {e}")
            raise

    def decode_id_token(
        self,
        id_token: str,
        *,
        key: str | None = None,
        algorithms: list[str] | None = None,
        nonce: str | None = None,
    ) -> Dict[str, Any]:
        """Decode and validate ID token (JWT).

        Args:
            id_token: ID token JWT

        Returns:
            Decoded token claims
        """
        try:
            import jwt

            if not key:
                raise ValueError("OIDC ID token verification key is required.")

            decoded = jwt.decode(
                id_token,
                key=key,
                algorithms=algorithms or ["RS256"],
                audience=self.config.client_id if self.config.validate_audience else None,
                issuer=self._expected_issuer() if self.config.validate_issuer else None,
                options={
                    "verify_signature": True,
                    "verify_aud": self.config.validate_audience,
                    "verify_iss": self.config.validate_issuer,
                    "require": ["exp", "iat", "sub"],
                },
            )
            if nonce is not None and decoded.get("nonce") != nonce:
                raise ValueError("OIDC ID token nonce mismatch.")

            self.logger.debug(f"Decoded ID token for user: {decoded.get('sub')}")
            return decoded
        except Exception as e:
            self.logger.error(f"Failed to decode ID token: {e}")
            raise

    def _expected_issuer(self) -> str:
        if self._discovery_cache and self._discovery_cache.get("issuer"):
            return str(self._discovery_cache["issuer"])
        return self.config.discovery_url.replace("/.well-known/openid-configuration", "")


# ============================================================================
# SSO Session Manager
# ============================================================================

class SSOSessionManager:
    """Manages SSO sessions."""

    def __init__(self, session_timeout_minutes: int = 480, idle_timeout_minutes: int = 30):
        self.session_timeout_minutes = session_timeout_minutes
        self.idle_timeout_minutes = idle_timeout_minutes
        self.sessions: Dict[str, SSOSession] = {}
        self.logger = logging.getLogger(f"{__name__}.SSOSessionManager")

    def create_session(
        self,
        user_id: str,
        tenant_id: str,
        provider: SSOProvider,
        ip_address: str,
        user_agent: str,
    ) -> SSOSession:
        """Create new SSO session.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            provider: SSO provider
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created SSOSession
        """
        session = SSOSession(
            user_id=user_id,
            tenant_id=tenant_id,
            provider=provider,
            expires_at=datetime.now(UTC) + timedelta(minutes=self.session_timeout_minutes),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.sessions[session.session_id] = session
        self.logger.info(f"Created SSO session {session.session_id} for user {user_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SSOSession]:
        """Get SSO session.

        Args:
            session_id: Session ID

        Returns:
            SSOSession or None if not found/expired
        """
        session = self.sessions.get(session_id)

        if session is None:
            return None

        if session.is_expired() or session.is_idle_expired(self.idle_timeout_minutes):
            self.invalidate_session(session_id)
            return None

        # Update last activity
        session.last_activity = datetime.now(UTC)
        return session

    def invalidate_session(self, session_id: str) -> None:
        """Invalidate SSO session.

        Args:
            session_id: Session ID
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.active = False
            self.logger.info(f"Invalidated SSO session {session_id}")

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired() or session.is_idle_expired(self.idle_timeout_minutes)
        ]

        for sid in expired:
            del self.sessions[sid]

        if expired:
            self.logger.info(f"Cleaned up {len(expired)} expired SSO sessions")

        return len(expired)


# ============================================================================
# Multi-tenant SSO Manager
# ============================================================================

class MultiTenantSSOManager:
    """Manages SSO for multiple tenants."""

    def __init__(self):
        self.saml_configs: Dict[str, SAMLConfig] = {}
        self.oidc_configs: Dict[str, OIDCConfig] = {}
        self.saml_managers: Dict[str, SAMLManager] = {}
        self.oidc_managers: Dict[str, OIDCManager] = {}
        self.session_manager = SSOSessionManager()
        self.logger = logging.getLogger(f"{__name__}.MultiTenantSSOManager")

    def register_saml_config(self, config: SAMLConfig) -> None:
        """Register SAML configuration for tenant.

        Args:
            config: SAML configuration
        """
        if not config.enabled:
            self.logger.warning(f"SAML config for tenant {config.tenant_id} is disabled")
            return

        self.saml_configs[config.tenant_id] = config
        self.saml_managers[config.tenant_id] = SAMLManager(config)
        self.logger.info(f"Registered SAML config for tenant {config.tenant_id}")

    def register_oidc_config(self, config: OIDCConfig) -> None:
        """Register OIDC configuration for tenant.

        Args:
            config: OIDC configuration
        """
        if not config.enabled:
            self.logger.warning(f"OIDC config for tenant {config.tenant_id} is disabled")
            return

        self.oidc_configs[config.tenant_id] = config
        self.oidc_managers[config.tenant_id] = OIDCManager(config)
        self.logger.info(f"Registered OIDC config for tenant {config.tenant_id}")

    def get_saml_manager(self, tenant_id: str) -> Optional[SAMLManager]:
        """Get SAML manager for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            SAMLManager or None
        """
        return self.saml_managers.get(tenant_id)

    def get_oidc_manager(self, tenant_id: str) -> Optional[OIDCManager]:
        """Get OIDC manager for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            OIDCManager or None
        """
        return self.oidc_managers.get(tenant_id)

    def get_enabled_providers(self, tenant_id: str) -> List[SSOProvider]:
        """Get enabled SSO providers for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of enabled providers
        """
        providers = []

        if tenant_id in self.saml_configs:
            providers.append(SSOProvider.SAML)

        if tenant_id in self.oidc_configs:
            providers.append(SSOProvider.OIDC)

        return providers


# Global instance
_sso_manager = MultiTenantSSOManager()


def get_sso_manager() -> MultiTenantSSOManager:
    """Get global SSO manager instance."""
    return _sso_manager
