"""SAML 2.0 Provider Implementation."""

from __future__ import annotations

import base64
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class SAMLConfig:
    """SAML configuration."""

    entity_id: str  # Service Provider Entity ID
    acs_url: str  # Assertion Consumer Service URL
    slo_url: str | None = None  # Single Logout URL
    idp_entity_id: str = ""  # Identity Provider Entity ID
    idp_sso_url: str = ""  # Identity Provider SSO URL
    idp_slo_url: str | None = None  # Identity Provider SLO URL
    idp_certificate: str = ""  # Identity Provider certificate
    sp_certificate: str | None = None  # Service Provider certificate
    sp_private_key: str | None = None  # Service Provider private key
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"


class SAMLAssertion(BaseModel):
    """SAML assertion."""

    assertion_id: str = Field(default_factory=lambda: f"_{uuid4().hex}")
    issuer: str
    subject: str
    name_id: str
    session_index: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(hours=1))
    attributes: dict[str, Any] = Field(default_factory=dict)
    authenticated: bool = False


class SAMLRequest(BaseModel):
    """SAML authentication request."""

    request_id: str = Field(default_factory=lambda: f"_{uuid4().hex}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=10))
    relay_state: str | None = None


class SAMLProvider:
    """SAML 2.0 provider for enterprise SSO."""

    def __init__(self, config: SAMLConfig) -> None:
        """Initialize SAML provider.

        Args:
            config: SAML configuration
        """
        self.config = config
        self._requests: dict[str, SAMLRequest] = {}
        self._assertions: dict[str, SAMLAssertion] = {}
        self._sessions: dict[str, SAMLAssertion] = {}

    def generate_auth_request(self, relay_state: str | None = None) -> tuple[str, str]:
        """Generate SAML authentication request.

        Args:
            relay_state: Relay state parameter

        Returns:
            Tuple of (request_id, auth_request_url)
        """
        request = SAMLRequest(relay_state=relay_state)
        self._requests[request.request_id] = request

        # Build SAML AuthnRequest XML
        authn_request_xml = self._build_authn_request(request.request_id)

        # Encode and deflate
        authn_request_b64 = base64.b64encode(authn_request_xml.encode("utf-8")).decode("utf-8")

        # Build redirect URL
        params = [f"SAMLRequest={authn_request_b64}"]
        if relay_state:
            params.append(f"RelayState={relay_state}")

        auth_url = f"{self.config.idp_sso_url}?{'&'.join(params)}"

        logger.debug(f"Generated SAML auth request: {request.request_id}")
        return request.request_id, auth_url

    def verify_response(
        self,
        saml_response: str,
        relay_state: str | None = None,
    ) -> SAMLAssertion | None:
        """Verify SAML response from IdP.

        Args:
            saml_response: Base64-encoded SAML response
            relay_state: Relay state parameter

        Returns:
            SAML assertion or None if verification fails
        """
        try:
            # Decode SAML response
            saml_response_xml = base64.b64decode(saml_response).decode("utf-8")

            # Parse XML using defusedxml to prevent XXE attacks (SECURITY P1-04).
            # The stdlib ET.fromstring is vulnerable to XML External Entity attacks.
            from defusedxml import ElementTree as DefusedET
            root = DefusedET.fromstring(saml_response_xml)

            # Extract assertion
            assertion = self._extract_assertion(root)
            if not assertion:
                logger.warning("Failed to extract assertion from SAML response")
                return None

            # Verify assertion
            if not self._verify_assertion(assertion):
                logger.warning("SAML assertion verification failed")
                return None

            # Store assertion
            self._assertions[assertion.assertion_id] = assertion
            self._sessions[assertion.session_index] = assertion

            logger.info(f"SAML response verified: {assertion.assertion_id}")
            return assertion

        except Exception as e:
            logger.error(f"SAML response verification failed: {e}")
            return None

    def _build_authn_request(self, request_id: str) -> str:
        """Build SAML AuthnRequest XML.

        Args:
            request_id: Request ID

        Returns:
            SAML AuthnRequest XML
        """
        now = datetime.now(UTC).isoformat() + "Z"

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{now}"
    Destination="{self.config.idp_sso_url}"
    AssertionConsumerServiceURL="{self.config.acs_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{self.config.entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="{self.config.name_id_format}" AllowCreate="true"/>
</samlp:AuthnRequest>"""

        return xml

    def _extract_assertion(self, root: ET.Element) -> SAMLAssertion | None:
        """Extract assertion from SAML response.

        Args:
            root: Root XML element

        Returns:
            SAML assertion or None
        """
        try:
            # Define namespaces
            namespaces = {
                "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
                "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
            }

            # Find assertion
            assertion_elem = root.find(".//saml:Assertion", namespaces)
            if assertion_elem is None:
                return None

            # Extract assertion ID
            assertion_id = assertion_elem.get("ID", f"_{uuid4().hex}")

            # Extract issuer
            issuer_elem = assertion_elem.find("saml:Issuer", namespaces)
            issuer = issuer_elem.text if issuer_elem is not None else ""

            # Extract subject
            subject_elem = assertion_elem.find("saml:Subject", namespaces)
            subject = ""
            name_id = ""
            if subject_elem is not None:
                name_id_elem = subject_elem.find("saml:NameID", namespaces)
                if name_id_elem is not None:
                    name_id = name_id_elem.text or ""
                    subject = name_id

            # Extract attributes
            attributes = {}
            attr_statement = assertion_elem.find("saml:AttributeStatement", namespaces)
            if attr_statement is not None:
                for attr in attr_statement.findall("saml:Attribute", namespaces):
                    attr_name = attr.get("Name", "")
                    attr_values = []
                    for value_elem in attr.findall("saml:AttributeValue", namespaces):
                        if value_elem.text:
                            attr_values.append(value_elem.text)
                    if attr_values:
                        attributes[attr_name] = attr_values[0] if len(attr_values) == 1 else attr_values

            # Extract session index
            authn_statement = assertion_elem.find("saml:AuthnStatement", namespaces)
            session_index = ""
            if authn_statement is not None:
                session_index = authn_statement.get("SessionIndex", uuid4().hex)

            assertion = SAMLAssertion(
                assertion_id=assertion_id,
                issuer=issuer,
                subject=subject,
                name_id=name_id,
                session_index=session_index,
                attributes=attributes,
                authenticated=True,
            )

            return assertion

        except Exception as e:
            logger.error(f"Failed to extract assertion: {e}")
            return None

    def _verify_assertion(self, assertion: SAMLAssertion) -> bool:
        """Verify SAML assertion.

        Args:
            assertion: SAML assertion

        Returns:
            True if assertion is valid
        """
        # Check issuer
        if assertion.issuer != self.config.idp_entity_id:
            logger.warning(f"Invalid issuer: {assertion.issuer}")
            return False

        # Check expiry
        if datetime.now(UTC) > assertion.expires_at:
            logger.warning("SAML assertion expired")
            return False

        # TODO: Verify signature using IdP certificate
        # This requires XML signature verification

        return True

    def create_logout_request(self, session_index: str) -> tuple[str, str]:
        """Create SAML logout request.

        Args:
            session_index: Session index

        Returns:
            Tuple of (request_id, logout_url)
        """
        if not self.config.idp_slo_url:
            logger.warning("SLO URL not configured")
            return "", ""

        request_id = f"_{uuid4().hex}"
        now = datetime.now(UTC).isoformat() + "Z"

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:LogoutRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{now}"
    Destination="{self.config.idp_slo_url}">
    <saml:Issuer>{self.config.entity_id}</saml:Issuer>
    <samlp:SessionIndex>{session_index}</samlp:SessionIndex>
</samlp:LogoutRequest>"""

        logout_request_b64 = base64.b64encode(xml.encode("utf-8")).decode("utf-8")
        logout_url = f"{self.config.idp_slo_url}?SAMLRequest={logout_request_b64}"

        logger.debug(f"Generated SAML logout request: {request_id}")
        return request_id, logout_url

    def get_assertion(self, assertion_id: str) -> SAMLAssertion | None:
        """Get SAML assertion.

        Args:
            assertion_id: Assertion ID

        Returns:
            SAML assertion or None
        """
        return self._assertions.get(assertion_id)

    def get_session(self, session_index: str) -> SAMLAssertion | None:
        """Get SAML session.

        Args:
            session_index: Session index

        Returns:
            SAML assertion or None
        """
        return self._sessions.get(session_index)

    def cleanup_expired_requests(self) -> int:
        """Clean up expired SAML requests.

        Returns:
            Number of requests cleaned up
        """
        now = datetime.now(UTC)
        expired = [rid for rid, req in self._requests.items() if now > req.expires_at]

        for rid in expired:
            del self._requests[rid]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired SAML requests")

        return len(expired)

    def cleanup_expired_assertions(self) -> int:
        """Clean up expired SAML assertions.

        Returns:
            Number of assertions cleaned up
        """
        now = datetime.now(UTC)
        expired = [aid for aid, assertion in self._assertions.items() if now > assertion.expires_at]

        for aid in expired:
            del self._assertions[aid]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired SAML assertions")

        return len(expired)
