from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from backend.app.core.feishu_bridge import FeishuBridge, FeishuSyncStore, feishu_bridge
from backend.app.main import app


def _configure_feishu() -> None:
    feishu_bridge.store = FeishuSyncStore()
    feishu_bridge.configure(
        app_id="cli_a_domestic_pilot",
        app_secret="app-secret",
        encrypt_key="encrypt-key",
    )


def _signed_headers(body: bytes, *, timestamp: str = "1780890000", nonce: str = "pilot") -> dict[str, str]:
    signature = FeishuBridge.calculate_lark_signature(
        timestamp=timestamp,
        nonce=nonce,
        encrypt_key="encrypt-key",
        body=body,
    )
    return {
        "Content-Type": "application/json",
        "X-Lark-Signature": signature,
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
    }


def _event_body(event_id: str = "commercial-pilot-feishu-event") -> bytes:
    payload = {
        "header": {
            "event_id": event_id,
            "event_type": "im.message.receive_v1",
            "tenant_key": "tenant-key",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": f"message-{event_id}",
                "chat_id": "oc_chat",
                "content": json.dumps({"text": "国内试点飞书消息"}, ensure_ascii=False),
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _encrypted_body(payload: dict[str, object]) -> dict[str, str]:
    key = hashlib.sha256("encrypt-key".encode("utf-8")).digest()
    iv = b"0123456789abcdef"
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    padding_size = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([padding_size]) * padding_size
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return {"encrypt": base64.b64encode(iv + ciphertext).decode("utf-8")}


def test_feishu_event_accepts_signed_domestic_pilot_message() -> None:
    _configure_feishu()
    body = _event_body()
    client = TestClient(app)

    response = client.post(
        "/api/v1/integrations/feishu/events",
        content=body,
        headers=_signed_headers(body),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"]["accepted"] is True
    assert payload["result"]["event_id"] == "commercial-pilot-feishu-event"
    assert payload["result"]["event_type"] == "im.message.receive_v1"


def test_feishu_bridge_configures_from_owner_environment(monkeypatch) -> None:
    bridge = FeishuBridge()
    monkeypatch.setenv("XAGENT_FEISHU_APP_ID", "cli_a_env")
    monkeypatch.setenv("XAGENT_FEISHU_APP_SECRET", "env-secret")
    monkeypatch.setenv("XAGENT_FEISHU_ENCRYPT_KEY", "env-encrypt")
    monkeypatch.setenv("XAGENT_FEISHU_BASE_URL", "https://open.feishu.cn/")

    assert bridge.configure_from_env() is True
    assert bridge.app_id == "cli_a_env"
    assert bridge.app_secret == "env-secret"
    assert bridge.encrypt_key == "env-encrypt"
    assert bridge.base_url == "https://open.feishu.cn"


def test_feishu_url_verification_challenge_is_returned() -> None:
    _configure_feishu()
    client = TestClient(app)

    response = client.post(
        "/api/v1/integrations/feishu/events",
        json={"type": "url_verification", "challenge": "plain-challenge"},
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "plain-challenge"}


def test_feishu_encrypted_url_verification_challenge_is_returned() -> None:
    _configure_feishu()
    client = TestClient(app)

    response = client.post(
        "/api/v1/integrations/feishu/events",
        json=_encrypted_body({"type": "url_verification", "challenge": "encrypted-challenge"}),
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "encrypted-challenge"}


def test_feishu_encrypted_event_requires_signature_headers() -> None:
    _configure_feishu()
    client = TestClient(app)
    encrypted_event = _encrypted_body(
        {
            "header": {
                "event_id": "encrypted-event-without-signature",
                "event_type": "im.message.receive_v1",
            }
        }
    )

    response = client.post(
        "/api/v1/integrations/feishu/events",
        json=encrypted_event,
    )

    assert response.status_code == 401
    assert "Missing Feishu signature headers" in response.json()["message"]


def test_feishu_live_evidence_report_is_written_when_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_feishu()
    body = _event_body("commercial-pilot-live-event")
    output_path = tmp_path / "commercial-pilot-feishu-live.json"
    monkeypatch.setenv("XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_EVIDENCE", "1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_REPORT_PATH", str(output_path))
    client = TestClient(app)

    response = client.post(
        "/api/v1/integrations/feishu/events",
        content=body,
        headers=_signed_headers(body),
    )

    assert response.status_code == 200
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["channel"] == "feishu"
    assert report["evidence_type"] == "commercial_pilot_feishu_live"
    assert report["event_id"] == "commercial-pilot-live-event"
    assert report["signature_mode"] == "lark_sha256"
    assert report["mutation_performed"] is False
    assert report["outbound_message_sent"] is False


def test_feishu_event_rejects_missing_signature_headers() -> None:
    _configure_feishu()
    client = TestClient(app)

    response = client.post(
        "/api/v1/integrations/feishu/events",
        content=_event_body("commercial-pilot-missing-signature"),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401
    assert "Missing Feishu signature headers" in response.json()["message"]


def test_feishu_event_rejects_invalid_signature() -> None:
    _configure_feishu()
    body = _event_body("commercial-pilot-bad-signature")
    client = TestClient(app)

    headers = _signed_headers(body)
    headers["X-Lark-Signature"] = "bad"
    response = client.post(
        "/api/v1/integrations/feishu/events",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert "Invalid Feishu signature" in response.json()["message"]
