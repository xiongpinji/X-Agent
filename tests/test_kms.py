"""P2-02: KMS 密钥管理单元测试.

覆盖:
- LocalKMS: 加密/解密/轮换/多版本
- EnvelopeEncryption: 信封加密/解密/DEK 重加密
- KMSManager: 统一接口/自动轮换检查
"""

import tempfile
from pathlib import Path

import pytest

from backend.app.core.kms.base import KMSBackend, KMSConfig
from backend.app.core.kms.envelope import EnvelopeEncryption
from backend.app.core.kms.local import LocalKMS
from backend.app.core.kms.manager import KMSManager


# ─── LocalKMS 测试 ────────────────────────────────────────────────────────────


class TestLocalKMS:
    """LocalKMS 基本操作测试."""

    @pytest.fixture
    def kms(self, tmp_path):
        return LocalKMS(key_dir=str(tmp_path / "keys"), key_prefix="test")

    def test_encrypt_decrypt_roundtrip(self, kms):
        plaintext = b"hello world secret data"
        result = kms.encrypt(plaintext)
        assert result.ciphertext != plaintext
        assert result.key_version == 1
        assert result.key_id == "test-master"

        decrypted = kms.decrypt(result.ciphertext)
        assert decrypted.plaintext == plaintext
        assert decrypted.key_version == 1

    def test_encrypt_empty_bytes(self, kms):
        result = kms.encrypt(b"")
        decrypted = kms.decrypt(result.ciphertext)
        assert decrypted.plaintext == b""

    def test_encrypt_large_data(self, kms):
        data = b"x" * 1024 * 1024  # 1MB
        result = kms.encrypt(data)
        decrypted = kms.decrypt(result.ciphertext)
        assert decrypted.plaintext == data

    def test_different_plaintexts_different_ciphertexts(self, kms):
        r1 = kms.encrypt(b"data1")
        r2 = kms.encrypt(b"data2")
        assert r1.ciphertext != r2.ciphertext

    def test_key_rotation(self, kms):
        # 加密 v1
        r1 = kms.encrypt(b"before rotation")
        assert r1.key_version == 1

        # 轮换
        meta = kms.rotate_key()
        assert meta.version == 2
        assert meta.status == "active"

        # 新加密使用 v2
        r2 = kms.encrypt(b"after rotation")
        assert r2.key_version == 2

        # 旧密文仍可解密 (自动尝试所有版本)
        d1 = kms.decrypt(r1.ciphertext)
        assert d1.plaintext == b"before rotation"

        # 新密文解密
        d2 = kms.decrypt(r2.ciphertext)
        assert d2.plaintext == b"after rotation"

    def test_decrypt_with_explicit_version(self, kms):
        r1 = kms.encrypt(b"v1 data")
        kms.rotate_key()
        r2 = kms.encrypt(b"v2 data")

        # 指定版本解密
        d1 = kms.decrypt(r1.ciphertext, key_version=1)
        assert d1.plaintext == b"v1 data"
        assert d1.key_version == 1

        d2 = kms.decrypt(r2.ciphertext, key_version=2)
        assert d2.plaintext == b"v2 data"

    def test_multiple_rotations(self, kms):
        ciphertexts = []
        for i in range(5):
            r = kms.encrypt(f"data-{i}".encode())
            ciphertexts.append((r.ciphertext, f"data-{i}".encode()))
            if i < 4:
                kms.rotate_key()

        # 所有历史密文均可解密
        for ct, expected in ciphertexts:
            d = kms.decrypt(ct)
            assert d.plaintext == expected

    def test_get_key_metadata(self, kms):
        meta = kms.get_key_metadata()
        assert meta.version == 1
        assert meta.backend == KMSBackend.LOCAL
        assert meta.status == "active"

        kms.rotate_key()
        meta = kms.get_key_metadata()
        assert meta.version == 2

    def test_list_key_versions(self, kms):
        kms.rotate_key()
        kms.rotate_key()

        versions = kms.list_key_versions()
        assert len(versions) == 3
        assert versions[0].version == 3  # 降序
        assert versions[0].status == "active"
        assert versions[1].status == "rotated"
        assert versions[2].status == "rotated"

    def test_named_keys_isolated(self, kms):
        r1 = kms.encrypt(b"master data", key_name="master")
        r2 = kms.encrypt(b"api data", key_name="api-keys")

        # 不同密钥名不能互相解密
        d1 = kms.decrypt(r1.ciphertext, key_name="master")
        assert d1.plaintext == b"master data"

        d2 = kms.decrypt(r2.ciphertext, key_name="api-keys")
        assert d2.plaintext == b"api data"

    def test_health_check(self, kms):
        assert kms.health_check() is True

    def test_persistence(self, tmp_path):
        """密钥持久化: 新实例可解密旧数据."""
        key_dir = str(tmp_path / "keys")
        kms1 = LocalKMS(key_dir=key_dir, key_prefix="persist")
        r = kms1.encrypt(b"persistent data")

        # 新实例
        kms2 = LocalKMS(key_dir=key_dir, key_prefix="persist")
        d = kms2.decrypt(r.ciphertext)
        assert d.plaintext == b"persistent data"


# ─── EnvelopeEncryption 测试 ──────────────────────────────────────────────────


class TestEnvelopeEncryption:
    """信封加密测试."""

    @pytest.fixture
    def envelope(self, tmp_path):
        kms = LocalKMS(key_dir=str(tmp_path / "keys"), key_prefix="env-test")
        return EnvelopeEncryption(kms)

    def test_encrypt_decrypt_roundtrip(self, envelope):
        plaintext = b"sensitive data for envelope encryption"
        result = envelope.encrypt(plaintext)

        assert result.envelope != plaintext
        assert result.key_version == 1

        decrypted = envelope.decrypt(result.envelope)
        assert decrypted.plaintext == plaintext

    def test_with_associated_data(self, envelope):
        plaintext = b"data with aad"
        aad = b"context: user-123"

        result = envelope.encrypt(plaintext, associated_data=aad)
        decrypted = envelope.decrypt(result.envelope, associated_data=aad)
        assert decrypted.plaintext == plaintext

    def test_wrong_aad_fails(self, envelope):
        plaintext = b"data with aad"
        result = envelope.encrypt(plaintext, associated_data=b"correct")

        with pytest.raises(Exception):
            envelope.decrypt(result.envelope, associated_data=b"wrong")

    def test_large_data(self, envelope):
        """信封加密无大小限制 (不像 AWS KMS 4KB)."""
        data = b"y" * 10 * 1024 * 1024  # 10MB
        result = envelope.encrypt(data)
        decrypted = envelope.decrypt(result.envelope)
        assert decrypted.plaintext == data

    def test_re_encrypt_dek_after_rotation(self, tmp_path):
        """密钥轮换后重新加密 DEK."""
        kms = LocalKMS(key_dir=str(tmp_path / "keys"), key_prefix="reenc")
        envelope = EnvelopeEncryption(kms)

        # 加密
        result = envelope.encrypt(b"original data")
        assert result.key_version == 1

        # 轮换 KEK
        kms.rotate_key()

        # 重新加密 DEK
        new_envelope = envelope.re_encrypt_dek(result.envelope)

        # 用新信封解密
        decrypted = envelope.decrypt(new_envelope)
        assert decrypted.plaintext == b"original data"
        assert decrypted.key_version == 2

    def test_tampered_envelope_fails(self, envelope):
        result = envelope.encrypt(b"tamper test")
        # 篡改密文区域 (信封中部, 避开头部元数据)
        tampered = bytearray(result.envelope)
        mid = len(tampered) // 2
        tampered[mid] ^= 0xFF
        with pytest.raises(Exception):
            envelope.decrypt(bytes(tampered))


# ─── KMSManager 测试 ──────────────────────────────────────────────────────────


class TestKMSManager:
    """KMS Manager 统一接口测试."""

    @pytest.fixture
    def manager(self, tmp_path):
        config = KMSConfig(
            backend=KMSBackend.LOCAL,
            local_key_path=str(tmp_path / "keys"),
            key_prefix="mgr-test",
            auto_rotate_days=90,
        )
        return KMSManager(config)

    def test_encrypt_decrypt_bytes(self, manager):
        data = b"manager test data"
        encrypted = manager.encrypt(data)
        decrypted = manager.decrypt(encrypted)
        assert decrypted == data

    def test_encrypt_decrypt_str(self, manager):
        text = "中文密钥管理测试 🔐"
        encrypted = manager.encrypt_str(text)
        decrypted = manager.decrypt_str(encrypted)
        assert decrypted == text

    def test_encrypt_raw(self, manager):
        result = manager.encrypt_raw(b"raw data")
        assert result.key_version == 1
        decrypted = manager.decrypt_raw(result.ciphertext)
        assert decrypted.plaintext == b"raw data"

    def test_manual_rotate(self, manager):
        meta = manager.rotate()
        assert meta.version == 2

        # 轮换后仍可加密解密
        encrypted = manager.encrypt(b"post-rotation")
        assert manager.decrypt(encrypted) == b"post-rotation"

    def test_auto_rotate_not_triggered(self, manager):
        """新密钥不应触发自动轮换."""
        result = manager.rotate_if_needed()
        assert result is None

    def test_health_check(self, manager):
        assert manager.health_check() is True

    def test_backend_property(self, manager):
        assert manager.backend == KMSBackend.LOCAL

    def test_key_metadata(self, manager):
        meta = manager.get_key_metadata()
        assert meta.version == 1
        assert meta.status == "active"

    def test_list_versions(self, manager):
        manager.rotate()
        versions = manager.list_key_versions()
        assert len(versions) == 2
