from __future__ import annotations

import subprocess
import sys

from backend.app.core.audit_signing import ExternalCommandAuditSigner, HMACAuditSigner


def test_hmac_audit_signer_signs_and_verifies_digest() -> None:
    signer = HMACAuditSigner("audit-secret")
    digest = "sha256:abc123"
    signature = signer.sign(digest)

    assert signature
    assert signer.verify(digest, signature) is True
    assert signer.verify("sha256:tampered", signature) is False
    assert signer.verify(digest, None) is False


def test_hmac_audit_signer_allows_unsigned_records_without_secret() -> None:
    signer = HMACAuditSigner(None)

    assert signer.sign("sha256:abc123") is None
    assert signer.verify("sha256:abc123", None) is True
    assert signer.verify("sha256:abc123", "unexpected") is False


def test_external_command_audit_signer_can_verify_by_resigning(tmp_path) -> None:
    script = tmp_path / "sign.py"
    script.write_text("import sys\nprint('sig:' + sys.argv[1])\n", encoding="utf-8")
    signer = ExternalCommandAuditSigner(
        sign_command=f"{sys.executable} {script}",
    )

    signature = signer.sign("digest-1")

    assert signature == "sig:digest-1"
    assert signer.verify("digest-1", "sig:digest-1") is True
    assert signer.verify("digest-2", "sig:digest-1") is False


def test_external_command_audit_signer_can_use_verify_command(tmp_path) -> None:
    sign_script = tmp_path / "sign.py"
    sign_script.write_text("import sys\nprint('ok:' + sys.argv[1])\n", encoding="utf-8")
    verify_script = tmp_path / "verify.py"
    verify_script.write_text(
        "import sys\nraise SystemExit(0 if sys.argv[2] == 'ok:' + sys.argv[1] else 1)\n",
        encoding="utf-8",
    )
    signer = ExternalCommandAuditSigner(
        sign_command=f"{sys.executable} {sign_script}",
        verify_command=f"{sys.executable} {verify_script}",
    )

    assert signer.verify("digest-1", "ok:digest-1") is True
    assert signer.verify("digest-1", "bad") is False


def test_external_command_audit_signer_propagates_sign_failures(tmp_path) -> None:
    script = tmp_path / "fail.py"
    script.write_text("raise SystemExit(7)\n", encoding="utf-8")
    signer = ExternalCommandAuditSigner(
        sign_command=f"{sys.executable} {script}",
    )

    try:
        signer.sign("digest-1")
    except subprocess.CalledProcessError as exc:
        assert exc.returncode == 7
    else:
        raise AssertionError("Expected failing sign command to raise.")
