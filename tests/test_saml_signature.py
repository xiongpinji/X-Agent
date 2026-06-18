"""SAML XMLDSig signature verification tests.

Tests the real signature verification in backend.app.core.saml_sso.verify_saml_xml_signature
and the fail-closed behavior of SAML processors.

Covers:
  1. XXE payload rejected (defusedxml)
  2. Unsigned response rejected
  3. Forged/tampered signature rejected
  4. Missing IdP certificate rejected
  5. Legitimately signed response accepted (clear mock with real RSA-SHA256)
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from backend.app.core.saml_sso import verify_saml_xml_signature


# ---------------------------------------------------------------------------
# Test fixtures: generate a real RSA key pair + self-signed cert ONCE per session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def idp_keypair():
    """Generate a real RSA-2048 key pair for signing SAML responses."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key


@pytest.fixture(scope="module")
def idp_cert_pem(idp_keypair) -> str:
    """Generate a self-signed X.509 cert (PEM) for the IdP."""
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "test-idp.example.com"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(idp_keypair.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
        .not_valid_after(datetime(2030, 1, 1, tzinfo=timezone.utc))
        .sign(idp_keypair, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def _sign_signed_info(signed_info_xml: str, private_key) -> bytes:
    """Sign canonicalized SignedInfo with RSA-SHA256, return signature bytes.

    IMPORTANT: must canonicalize the SAME WAY as verify_saml_xml_signature does
    (ET.tostring + strip inter-tag whitespace) so the signature matches.
    """
    from defusedxml import ElementTree as ET
    import re
    # Parse the SignedInfo fragment, re-serialize, strip whitespace — mirrors
    # what _canonicalize_signed_info() does in verify_saml_xml_signature.
    elem = ET.fromstring(signed_info_xml)
    canonical = ET.tostring(elem, encoding="unicode")
    canonical = re.sub(r">\s+<", "><", canonical).strip()
    return private_key.sign(canonical.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())


def _build_signed_saml_response(private_key, subject: str = "user@example.com") -> bytes:
    """Build a SAML Response with a REAL RSA-SHA256 signature over SignedInfo.

    The signature is computed by:
    1. Building the full XML with a placeholder SignatureValue
    2. Parsing it, extracting the SignedInfo element
    3. Serializing SignedInfo the SAME WAY verify_saml_xml_signature does
    4. Signing those exact bytes
    5. Replacing the placeholder with the real signature
    This guarantees the c14n bytes match between signing and verification.
    """
    import re
    from defusedxml import ElementTree as ET

    DS_NS = "http://www.w3.org/2000/09/xmldsig#"
    ns_map = {"ds": DS_NS}

    # Step 1: build XML with placeholders
    template = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
                ID="_response123" Version="2.0">
  <saml:Issuer>https://idp.example.com</saml:Issuer>
  <ds:Signature>
    <ds:SignedInfo>
      <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
      <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
      <ds:Reference URI="#_assertion123">
        <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
        <ds:DigestValue>DIGEST_PLACEHOLDER</ds:DigestValue>
      </ds:Reference>
    </ds:SignedInfo>
    <ds:SignatureValue>PLACEHOLDER</ds:SignatureValue>
  </ds:Signature>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion ID="_assertion123" Version="2.0">
    <saml:Issuer>https://idp.example.com</saml:Issuer>
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{subject}</saml:NameID>
    </saml:Subject>
  </saml:Assertion>
</samlp:Response>"""

    root = ET.fromstring(template)
    assertion = root.find(".//saml:Assertion", {"saml": "urn:oasis:names:tc:SAML:2.0:assertion"})
    assertion_canonical = ET.tostring(assertion, encoding="unicode")
    assertion_canonical = re.sub(r">\s+<", "><", assertion_canonical).strip()
    digest_value = base64.b64encode(hashlib.sha256(assertion_canonical.encode("utf-8")).digest()).decode("utf-8")
    template = template.replace("DIGEST_PLACEHOLDER", digest_value)

    # Step 2-3: parse, extract SignedInfo, canonicalize (mirror verify logic)
    root = ET.fromstring(template)
    sig_elem = root.find(".//ds:Signature", ns_map)
    signed_info = sig_elem.find("ds:SignedInfo", ns_map)
    canonical = ET.tostring(signed_info, encoding="unicode")
    canonical = re.sub(r">\s+<", "><", canonical).strip()

    # Step 4: sign the canonical bytes
    sig_bytes = private_key.sign(canonical.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    sig_value = base64.b64encode(sig_bytes).decode("utf-8")

    # Step 5: replace placeholder in the ORIGINAL template string and return
    return template.replace("PLACEHOLDER", sig_value).encode("utf-8")


def _build_unsigned_saml_response() -> bytes:
    """SAML Response with NO <ds:Signature> element at all."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_response456" Version="2.0">
  <saml:Issuer>https://idp.example.com</saml:Issuer>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion ID="_assertion456" Version="2.0">
    <saml:Subject><saml:NameID>attacker@example.com</saml:NameID></saml:Subject>
  </saml:Assertion>
</samlp:Response>""".encode("utf-8")


def _build_forged_signature_response() -> bytes:
    """SAML Response with a <ds:Signature> element but a FAKE SignatureValue
    (random bytes, not a real RSA signature over SignedInfo)."""
    fake_sig = base64.b64encode(b"0" * 256).decode("utf-8")  # 256 bytes of zeros
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_response789" Version="2.0">
  <saml:Issuer>https://idp.example.com</saml:Issuer>
  <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <ds:SignedInfo>
      <ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
      <ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
      <ds:Reference URI="#_assertion789"><ds:DigestValue>fake==</ds:DigestValue></ds:Reference>
    </ds:SignedInfo>
    <ds:SignatureValue>{fake_sig}</ds:SignatureValue>
  </ds:Signature>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion ID="_assertion789" Version="2.0">
    <saml:Subject><saml:NameID>attacker@example.com</saml:NameID></saml:Subject>
  </saml:Assertion>
</samlp:Response>""".encode("utf-8")


def _build_xxe_payload() -> bytes:
    """XXE attack payload: tries to read /etc/passwd via external entity."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                ID="_xxe" Version="2.0">
  <saml:Issuer>&xxe;</saml:Issuer>
</samlp:Response>"""


# ---------------------------------------------------------------------------
# Tests against the shared verify_saml_xml_signature() helper
# ---------------------------------------------------------------------------

class TestSamlSignatureVerification:
    """Tests for verify_saml_xml_signature()."""

    def test_legitimate_signature_accepted(self, idp_keypair, idp_cert_pem):
        """A response signed with the correct IdP key must verify OK."""
        xml = _build_signed_saml_response(idp_keypair)
        assert verify_saml_xml_signature(xml, idp_cert_pem) is True

    def test_unsigned_response_rejected(self, idp_cert_pem):
        """A response with no <ds:Signature> must be rejected (fail-closed)."""
        xml = _build_unsigned_saml_response()
        assert verify_saml_xml_signature(xml, idp_cert_pem) is False

    def test_forged_signature_rejected(self, idp_cert_pem):
        """A response with a fake SignatureValue must be rejected."""
        xml = _build_forged_signature_response()
        assert verify_saml_xml_signature(xml, idp_cert_pem) is False

    def test_missing_certificate_rejected(self, idp_keypair):
        """When no IdP cert is provided, verification must fail-closed."""
        xml = _build_signed_saml_response(idp_keypair)
        assert verify_saml_xml_signature(xml, "") is False

    def test_wrong_certificate_rejected(self, idp_keypair):
        """A signature verified against the WRONG cert (different key) must fail."""
        # Generate a DIFFERENT key/cert pair
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wrong-idp")])
        other_cert = (
            x509.CertificateBuilder()
            .subject_name(other_subject)
            .issuer_name(other_subject)
            .public_key(other_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
            .not_valid_after(datetime(2030, 1, 1, tzinfo=timezone.utc))
            .sign(other_key, hashes.SHA256())
        )
        other_cert_pem = other_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

        xml = _build_signed_saml_response(idp_keypair)  # signed by idp_keypair
        assert verify_saml_xml_signature(xml, other_cert_pem) is False  # verified against other cert

    def test_xxe_payload_rejected(self, idp_cert_pem):
        """An XXE payload must be rejected by defusedxml (not leak file content)."""
        xml = _build_xxe_payload()
        # defusedxml raises EntitiesForbidden, caught internally -> returns False
        assert verify_saml_xml_signature(xml, idp_cert_pem) is False

    def test_tampered_signedinfo_rejected(self, idp_keypair, idp_cert_pem):
        """Tampering with SignedInfo after signing must invalidate the signature."""
        xml = _build_signed_saml_response(idp_keypair)
        # Flip a character in SignedInfo (change Reference URI)
        tampered = xml.replace(b'URI="#_assertion123"', b'URI="#_assertion999"')
        assert verify_saml_xml_signature(tampered, idp_cert_pem) is False

    def test_tampered_assertion_rejected(self, idp_keypair, idp_cert_pem):
        """Tampering with the signed Assertion must invalidate Reference digest."""
        xml = _build_signed_saml_response(idp_keypair, subject="user@example.com")
        tampered = xml.replace(b"user@example.com", b"admin@example.com")
        assert verify_saml_xml_signature(tampered, idp_cert_pem) is False

    def test_bad_reference_digest_rejected(self, idp_keypair, idp_cert_pem):
        """A valid SignedInfo signature with a wrong Reference digest is rejected."""
        xml = _build_signed_saml_response(idp_keypair)
        import re
        tampered = re.sub(
            rb"(<ds:DigestValue>)[^<]+(</ds:DigestValue>)",
            rb"\1" + base64.b64encode(b"bad-digest") + rb"\2",
            xml,
            count=1,
        )
        assert verify_saml_xml_signature(tampered, idp_cert_pem) is False


# ---------------------------------------------------------------------------
# Tests against SAMLSSOManager (integration: parse_response uses _verify_signature)
# ---------------------------------------------------------------------------

class TestSamlSsoManagerIntegration:
    """Integration tests: SAMLSSOManager.parse_response enforces signature."""

    def _make_manager(self, cert_pem: str):
        from backend.app.core.saml_sso import SAMLConfig, SAMLManager
        config = SAMLConfig(
            tenant_id="default",
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate=cert_pem,
            sp_entity_id="https://sp.example.com",
            sp_acs_url="https://sp.example.com/acs",
        )
        return SAMLManager(config)

    def test_signed_response_parses_ok(self, idp_keypair, idp_cert_pem):
        """A properly signed response should parse and return signature_valid=True."""
        manager = self._make_manager(idp_cert_pem)
        xml = _build_signed_saml_response(idp_keypair)
        b64 = base64.b64encode(xml).decode("utf-8")
        assertion = manager.parse_response(b64)
        assert assertion is not None
        assert assertion.signature_valid is True

    def test_unsigned_response_rejected_by_manager(self, idp_cert_pem):
        """An unsigned response must raise ValueError (fail-closed)."""
        manager = self._make_manager(idp_cert_pem)
        xml = _build_unsigned_saml_response()
        b64 = base64.b64encode(xml).decode("utf-8")
        with pytest.raises(ValueError):
            manager.parse_response(b64)

    def test_forged_signature_rejected_by_manager(self, idp_cert_pem):
        """A forged-signature response must raise ValueError."""
        manager = self._make_manager(idp_cert_pem)
        xml = _build_forged_signature_response()
        b64 = base64.b64encode(xml).decode("utf-8")
        with pytest.raises(ValueError):
            manager.parse_response(b64)


class TestOIDCManagerFailClosed:
    def _make_manager(self):
        import jwt
        from backend.app.core.saml_sso import OIDCConfig, OIDCManager

        config = OIDCConfig(
            provider_name="test",
            discovery_url="https://issuer.example.com/.well-known/openid-configuration",
            client_id="client-123",
            client_secret="secret",
            redirect_uri="https://sp.example.com/callback",
            tenant_id="default",
        )
        manager = OIDCManager(config)
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": "user-123",
                "aud": "client-123",
                "iss": "https://issuer.example.com",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=5)).timestamp()),
                "nonce": "nonce-1",
            },
            "oidc-test-secret-with-at-least-32-bytes",
            algorithm="HS256",
        )
        return manager, token

    def test_decode_id_token_requires_verification_key(self):
        manager, token = self._make_manager()

        with pytest.raises(ValueError, match="verification key is required"):
            manager.decode_id_token(token)

    def test_decode_id_token_verifies_signature_and_nonce(self):
        manager, token = self._make_manager()

        claims = manager.decode_id_token(
            token,
            key="oidc-test-secret-with-at-least-32-bytes",
            algorithms=["HS256"],
            nonce="nonce-1",
        )

        assert claims["sub"] == "user-123"

    def test_decode_id_token_rejects_nonce_mismatch(self):
        manager, token = self._make_manager()

        with pytest.raises(ValueError, match="nonce mismatch"):
            manager.decode_id_token(
                token,
                key="oidc-test-secret-with-at-least-32-bytes",
                algorithms=["HS256"],
                nonce="wrong",
            )
