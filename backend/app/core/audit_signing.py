from __future__ import annotations

import os
import shlex
import subprocess
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from typing import Protocol


class AuditSigner(Protocol):
    def sign(self, digest: str) -> str | None: ...

    def verify(self, digest: str, signature: str | None) -> bool: ...


class HMACAuditSigner:
    def __init__(self, secret: str | None) -> None:
        self.secret = secret

    def sign(self, digest: str) -> str | None:
        if self.secret is None:
            return None
        return hmac_new(
            self.secret.encode("utf-8"),
            digest.encode("utf-8"),
            sha256,
        ).hexdigest()

    def verify(self, digest: str, signature: str | None) -> bool:
        expected = self.sign(digest)
        if expected is None:
            return signature is None
        return signature is not None and compare_digest(signature, expected)


class ExternalCommandAuditSigner:
    def __init__(
        self,
        *,
        sign_command: str,
        verify_command: str | None = None,
        timeout_seconds: int = 5,
    ) -> None:
        self.sign_command = sign_command
        self.verify_command = verify_command
        self.timeout_seconds = max(1, timeout_seconds)

    def sign(self, digest: str) -> str | None:
        completed = subprocess.run(
            [*_split_command(self.sign_command), digest],
            check=True,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        signature = completed.stdout.strip()
        return signature or None

    def verify(self, digest: str, signature: str | None) -> bool:
        if signature is None:
            return False
        if self.verify_command:
            completed = subprocess.run(
                [*_split_command(self.verify_command), digest, signature],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return completed.returncode == 0
        expected = self.sign(digest)
        return expected is not None and compare_digest(signature, expected)


def _split_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")
