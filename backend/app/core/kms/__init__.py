"""X-Agent KMS (Key Management Service) 抽象层.

P2-02: 统一密钥管理接口, 支持多后端:
- LocalKMS: 本地 Fernet 密钥 (默认, 无外部依赖)
- VaultKMS: HashiCorp Vault Transit 引擎
- AWSKMS: AWS KMS (boto3)

核心能力:
- 信封加密 (Envelope Encryption): DEK 加密数据, KEK 加密 DEK
- 主密钥轮换: 自动/手动轮换 KEK, 旧版本密钥保留用于解密
- 密钥版本管理: 每个密文绑定密钥版本, 解密时自动选择正确版本
"""

from backend.app.core.kms.base import KeyMetadata, KMSConfig, KMSProvider
from backend.app.core.kms.envelope import EnvelopeEncryption
from backend.app.core.kms.manager import KMSManager, get_kms_manager

__all__ = [
    "EnvelopeEncryption",
    "KMSConfig",
    "KMSManager",
    "KMSProvider",
    "KeyMetadata",
    "get_kms_manager",
]
