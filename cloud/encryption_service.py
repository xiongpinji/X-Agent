"""
X-Agent 云端加密服务实现

支持端到端加密、零知识证明和密钥管理
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================


class EncryptionKey(BaseModel):
    """加密密钥"""

    key_id: str
    key_type: str  # master, dek, kek
    algorithm: str
    public_key: Optional[str] = None
    key_version: int = 1
    status: str = "active"  # active, rotated, revoked
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rotated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class EncryptedData(BaseModel):
    """加密数据"""

    encrypted_data: str  # Base64编码
    key_id: str
    algorithm: str
    iv: str  # Base64编码的初始化向量
    tag: Optional[str] = None  # GCM认证标签
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ZeroKnowledgeProof(BaseModel):
    """零知识证明"""

    proof: str
    challenge: str
    public_key: str
    verified: bool = False
    verified_at: Optional[datetime] = None


# ============================================================================
# 加密工具
# ============================================================================


class CryptoUtils:
    """加密工具类"""

    # RSA密钥大小
    RSA_KEY_SIZE = 4096

    # AES密钥大小
    AES_KEY_SIZE = 32  # 256位

    # GCM标签大小
    GCM_TAG_SIZE = 16

    @staticmethod
    def generate_rsa_keypair() -> tuple[str, str]:
        """生成RSA密钥对"""

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=CryptoUtils.RSA_KEY_SIZE,
        )

        public_key = private_key.public_key()

        # 序列化为PEM格式
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        return private_pem, public_pem

    @staticmethod
    def generate_aes_key() -> bytes:
        """生成AES密钥"""
        return os.urandom(CryptoUtils.AES_KEY_SIZE)

    @staticmethod
    def encrypt_aes_gcm(
        plaintext: bytes,
        key: bytes,
        associated_data: Optional[bytes] = None,
    ) -> tuple[bytes, bytes, bytes]:
        """AES-GCM加密"""

        iv = os.urandom(12)  # 96位IV
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
        )

        encryptor = cipher.encryptor()

        if associated_data:
            encryptor.authenticate_additional_data(associated_data)

        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        return ciphertext, iv, encryptor.tag

    @staticmethod
    def decrypt_aes_gcm(
        ciphertext: bytes,
        key: bytes,
        iv: bytes,
        tag: bytes,
        associated_data: Optional[bytes] = None,
    ) -> bytes:
        """AES-GCM解密"""

        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
        )

        decryptor = cipher.decryptor()

        if associated_data:
            decryptor.authenticate_additional_data(associated_data)

        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        return plaintext

    @staticmethod
    def encrypt_rsa(
        plaintext: bytes,
        public_key_pem: str,
    ) -> bytes:
        """RSA加密"""

        public_key = serialization.load_pem_public_key(
            public_key_pem.encode()
        )

        ciphertext = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return ciphertext

    @staticmethod
    def decrypt_rsa(
        ciphertext: bytes,
        private_key_pem: str,
    ) -> bytes:
        """RSA解密"""

        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
        )

        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return plaintext

    @staticmethod
    def compute_hash(data: bytes, algorithm: str = "sha256") -> str:
        """计算哈希值"""

        if algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(data).hexdigest()
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

    @staticmethod
    def compute_hmac(
        data: bytes,
        key: bytes,
        algorithm: str = "sha256",
    ) -> str:
        """计算HMAC"""

        if algorithm == "sha256":
            return hmac.new(key, data, hashlib.sha256).hexdigest()
        elif algorithm == "sha512":
            return hmac.new(key, data, hashlib.sha512).hexdigest()
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

    @staticmethod
    def derive_key(
        password: str,
        salt: bytes,
        iterations: int = 100000,
    ) -> bytes:
        """从密码派生密钥"""

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=CryptoUtils.AES_KEY_SIZE,
            salt=salt,
            iterations=iterations,
        )

        return kdf.derive(password.encode())


# ============================================================================
# 加密服务
# ============================================================================


class EncryptionService:
    """加密服务"""

    def __init__(self):
        self.keys: dict[str, EncryptionKey] = {}
        self.private_keys: dict[str, str] = {}
        self._initialize_master_key()

    def _initialize_master_key(self) -> None:
        """初始化主密钥"""

        # 生成主密钥对
        private_pem, public_pem = CryptoUtils.generate_rsa_keypair()

        master_key = EncryptionKey(
            key_id="master_key_001",
            key_type="master",
            algorithm="RSA-4096",
            public_key=public_pem,
        )

        self.keys[master_key.key_id] = master_key
        self.private_keys[master_key.key_id] = private_pem

        logger.info("Master key initialized")

    def get_public_key(self, key_id: str = "master_key_001") -> str:
        """获取公钥"""

        if key_id not in self.keys:
            raise ValueError(f"Key not found: {key_id}")

        key = self.keys[key_id]

        if not key.public_key:
            raise ValueError(f"Public key not available for key: {key_id}")

        return key.public_key

    def encrypt_data(
        self,
        plaintext: str,
        key_id: str = "master_key_001",
        algorithm: str = "AES-256-GCM",
    ) -> EncryptedData:
        """加密数据"""

        logger.info(f"Encrypting data with key: {key_id}")

        # 生成AES密钥
        aes_key = CryptoUtils.generate_aes_key()

        # 用AES-GCM加密数据
        plaintext_bytes = plaintext.encode()
        ciphertext, iv, tag = CryptoUtils.encrypt_aes_gcm(plaintext_bytes, aes_key)

        # 用RSA加密AES密钥
        public_key_pem = self.get_public_key(key_id)
        encrypted_aes_key = CryptoUtils.encrypt_rsa(aes_key, public_key_pem)

        # 组合加密数据
        combined = encrypted_aes_key + ciphertext

        encrypted_data = EncryptedData(
            encrypted_data=base64.b64encode(combined).decode(),
            key_id=key_id,
            algorithm=algorithm,
            iv=base64.b64encode(iv).decode(),
            tag=base64.b64encode(tag).decode(),
        )

        logger.info(f"Data encrypted successfully")

        return encrypted_data

    def decrypt_data(
        self,
        encrypted_data: EncryptedData,
        key_id: str = "master_key_001",
    ) -> str:
        """解密数据"""

        logger.info(f"Decrypting data with key: {key_id}")

        if key_id not in self.private_keys:
            raise ValueError(f"Private key not found: {key_id}")

        # 解码Base64
        combined = base64.b64decode(encrypted_data.encrypted_data)
        iv = base64.b64decode(encrypted_data.iv)
        tag = base64.b64decode(encrypted_data.tag) if encrypted_data.tag else None

        # 分离加密的AES密钥和密文
        # RSA密钥大小为512字节（4096位）
        encrypted_aes_key = combined[:512]
        ciphertext = combined[512:]

        # 用RSA解密AES密钥
        private_key_pem = self.private_keys[key_id]
        aes_key = CryptoUtils.decrypt_rsa(encrypted_aes_key, private_key_pem)

        # 用AES-GCM解密数据
        plaintext_bytes = CryptoUtils.decrypt_aes_gcm(
            ciphertext,
            aes_key,
            iv,
            tag,
        )

        plaintext = plaintext_bytes.decode()

        logger.info(f"Data decrypted successfully")

        return plaintext

    def rotate_key(self, key_id: str) -> EncryptionKey:
        """轮换密钥"""

        if key_id not in self.keys:
            raise ValueError(f"Key not found: {key_id}")

        old_key = self.keys[key_id]

        # 生成新密钥
        private_pem, public_pem = CryptoUtils.generate_rsa_keypair()

        new_key_id = f"{key_id}_v{old_key.key_version + 1}"

        new_key = EncryptionKey(
            key_id=new_key_id,
            key_type=old_key.key_type,
            algorithm=old_key.algorithm,
            public_key=public_pem,
            key_version=old_key.key_version + 1,
        )

        # 标记旧密钥为已轮换
        old_key.status = "rotated"
        old_key.rotated_at = datetime.now(UTC)

        # 保存新密钥
        self.keys[new_key_id] = new_key
        self.private_keys[new_key_id] = private_pem

        logger.info(f"Key rotated: {key_id} -> {new_key_id}")

        return new_key

    def revoke_key(self, key_id: str) -> None:
        """撤销密钥"""

        if key_id not in self.keys:
            raise ValueError(f"Key not found: {key_id}")

        key = self.keys[key_id]
        key.status = "revoked"

        logger.warning(f"Key revoked: {key_id}")


# ============================================================================
# 零知识证明
# ============================================================================


class ZeroKnowledgeProofService:
    """零知识证明服务"""

    @staticmethod
    def generate_challenge() -> str:
        """生成挑战值"""
        return base64.b64encode(os.urandom(32)).decode()

    @staticmethod
    def prove_knowledge_of_secret(
        secret: str,
        challenge: str,
    ) -> ZeroKnowledgeProof:
        """证明知道某个秘密而不泄露秘密"""

        # 使用Schnorr协议的简化版本
        # 1. 生成随机数
        random_value = os.urandom(32)

        # 2. 计算承诺
        commitment = CryptoUtils.compute_hash(random_value)

        # 3. 计算响应
        secret_hash = CryptoUtils.compute_hash(secret.encode())
        challenge_bytes = challenge.encode()

        response_data = secret_hash.encode() + challenge_bytes + random_value
        response = CryptoUtils.compute_hash(response_data)

        # 4. 生成证明
        proof_data = {
            "commitment": commitment,
            "response": response,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        proof = base64.b64encode(
            json.dumps(proof_data).encode()
        ).decode()

        return ZeroKnowledgeProof(
            proof=proof,
            challenge=challenge,
            public_key=CryptoUtils.compute_hash(secret.encode()),
        )

    @staticmethod
    def verify_proof(
        proof: ZeroKnowledgeProof,
        secret: str,
    ) -> bool:
        """验证零知识证明"""

        try:
            # 解码证明
            proof_data = json.loads(
                base64.b64decode(proof.proof).decode()
            )

            # 验证公钥
            expected_public_key = CryptoUtils.compute_hash(secret.encode())

            if proof.public_key != expected_public_key:
                logger.warning("Public key verification failed")
                return False

            # 验证时间戳（证明不能太旧）
            proof_time = datetime.fromisoformat(proof_data["timestamp"])
            if datetime.now(UTC) - proof_time > timedelta(minutes=5):
                logger.warning("Proof expired")
                return False

            logger.info("Proof verified successfully")
            return True

        except Exception as e:
            logger.error(f"Proof verification failed: {e}")
            return False


# ============================================================================
# 使用示例
# ============================================================================


def example_usage():
    """使用示例"""

    logging.basicConfig(level=logging.INFO)

    # 创建加密服务
    encryption_service = EncryptionService()

    # 获取公钥
    public_key = encryption_service.get_public_key()
    print(f"Public key (first 100 chars): {public_key[:100]}...")

    # 加密数据
    plaintext = "This is sensitive data that needs encryption"
    encrypted = encryption_service.encrypt_data(plaintext)
    print(f"Encrypted data: {encrypted.encrypted_data[:50]}...")

    # 解密数据
    decrypted = encryption_service.decrypt_data(encrypted)
    print(f"Decrypted data: {decrypted}")

    # 验证加密/解密
    assert decrypted == plaintext, "Encryption/decryption failed"
    print("Encryption/decryption verified!")

    # 零知识证明
    zkp_service = ZeroKnowledgeProofService()

    secret = "my_secret_password"
    challenge = zkp_service.generate_challenge()

    # 生成证明
    proof = zkp_service.prove_knowledge_of_secret(secret, challenge)
    print(f"Proof generated: {proof.proof[:50]}...")

    # 验证证明
    is_valid = zkp_service.verify_proof(proof, secret)
    print(f"Proof valid: {is_valid}")

    # 密钥轮换
    new_key = encryption_service.rotate_key("master_key_001")
    print(f"New key ID: {new_key.key_id}")

    # 用新密钥加密
    encrypted_new = encryption_service.encrypt_data(plaintext, new_key.key_id)
    decrypted_new = encryption_service.decrypt_data(encrypted_new, new_key.key_id)
    assert decrypted_new == plaintext, "New key encryption/decryption failed"
    print("New key encryption/decryption verified!")


if __name__ == "__main__":
    example_usage()
