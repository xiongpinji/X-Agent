"""Serverless sandbox backends (Daytona / Modal) with graceful degradation.

Mirrors Codex cloud-sandbox / Hermes multi-backend design: the same
start/run/stop lifecycle is backed by a remote serverless workspace API
instead of a local Docker daemon. Selection is config-driven:

    XAGENT_SANDBOX_BACKEND = auto | daytona | modal | docker | subprocess

Backend credentials (explicit availability — a backend with missing
credentials is *unavailable*, never silently faked):

    Daytona: XAGENT_DAYTONA_API_KEY, XAGENT_DAYTONA_API_URL
    Modal:   XAGENT_MODAL_TOKEN_ID, XAGENT_MODAL_TOKEN_SECRET
             (optional XAGENT_MODAL_API_URL gateway override)

Degradation policy: any serverless API failure (unreachable, 5xx, timeout)
logs a WARNING and permanently degrades the sandbox to the local
DockerSandbox (docker -> subprocess chain). We never fabricate success.

Known gaps (honest coverage notes):
- Daytona workspace file upload (host workspace_path sync) is NOT covered;
  a warning is logged when spec.workspace_path is set.
- Modal's official API is SDK-centric (App.lookup/Sandbox.create over a
  custom protocol); this adapter targets a REST gateway
  (XAGENT_MODAL_API_URL) exposing create/exec/destroy. Token refresh and
  image-build flows are NOT covered.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from backend.app.core.sandbox.docker_sandbox import (
    DockerSandbox,
    SandboxResult,
    SandboxSpec,
)

logger = logging.getLogger(__name__)

ENV_BACKEND = "XAGENT_SANDBOX_BACKEND"


class ServerlessSandboxError(Exception):
    """Raised when a serverless sandbox backend fails or is unavailable."""


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


class _HTTPBackend:
    """Shared httpx plumbing for REST-style serverless sandbox APIs.

    `transport` lets tests inject httpx.MockTransport without real network.
    """

    backend = "serverless"

    def __init__(
        self,
        spec: SandboxSpec | None = None,
        *,
        base_url: str,
        headers: dict[str, str],
        request_timeout: float = 60.0,
        transport: Any = None,
    ):
        self.spec = spec or SandboxSpec()
        self._base_url = base_url.rstrip("/")
        self._headers = headers
        self._request_timeout = request_timeout
        self._transport = transport
        self._client: Any = None
        self._remote_id: str | None = None

    # -- subclass hooks -------------------------------------------------
    def _create_payload(self) -> dict[str, Any]:  # pragma: no cover - abstract
        raise NotImplementedError

    def _create_path(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def _exec_path(self, remote_id: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def _destroy_path(self, remote_id: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def _parse_create(self, data: dict[str, Any]) -> str:  # pragma: no cover
        raise NotImplementedError

    def _parse_exec(self, data: dict[str, Any]) -> tuple[int, str, str]:  # pragma: no cover
        raise NotImplementedError

    # -- lifecycle ------------------------------------------------------
    def _url(self, path: str) -> str:
        """Join API path onto base URL without clobbering base path segments."""
        return f"{self._base_url}/{path.lstrip('/')}"

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                import httpx  # lazy: backend must import without httpx installed
            except ImportError as e:  # pragma: no cover
                raise ServerlessSandboxError("httpx is required for serverless backends") from e
            kwargs: dict[str, Any] = {
                "headers": self._headers,
                "timeout": self._request_timeout,
            }
            if self._transport is not None:
                kwargs["transport"] = self._transport
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def start(self) -> None:
        """Create the remote workspace/sandbox. Raises ServerlessSandboxError on failure."""
        if self.spec.workspace_path:
            logger.warning(
                "%s backend does not sync host workspace_path=%s into the remote "
                "sandbox (not covered); commands run in a fresh remote workspace.",
                self.backend, self.spec.workspace_path,
            )
        client = await self._get_client()
        try:
            resp = await client.post(self._url(self._create_path()), json=self._create_payload())
            resp.raise_for_status()
            self._remote_id = self._parse_create(resp.json())
        except ServerlessSandboxError:
            raise
        except Exception as e:
            raise ServerlessSandboxError(
                f"{self.backend} workspace create failed: {type(e).__name__}: {e}"
            ) from e
        if not self._remote_id:
            raise ServerlessSandboxError(f"{self.backend} create returned no workspace id")
        logger.info("%s workspace %s created", self.backend, self._remote_id)

    async def run(self, command: str, timeout: float | None = None) -> SandboxResult:
        """Execute a command remotely. Raises ServerlessSandboxError on API failure."""
        if not self._remote_id:
            raise ServerlessSandboxError(f"{self.backend} backend not started")
        eff_timeout = timeout if timeout is not None else self.spec.timeout_seconds
        client = await self._get_client()
        t0 = time.perf_counter()
        try:
            resp = await client.post(
                self._url(self._exec_path(self._remote_id)),
                json={"command": command, "timeout": eff_timeout},
                timeout=eff_timeout + 30.0,
            )
            resp.raise_for_status()
            exit_code, stdout, stderr = self._parse_exec(resp.json())
        except ServerlessSandboxError:
            raise
        except Exception as e:
            raise ServerlessSandboxError(
                f"{self.backend} exec failed: {type(e).__name__}: {e}"
            ) from e
        return SandboxResult(
            success=exit_code == 0,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=(time.perf_counter() - t0) * 1000,
            backend=self.backend,
            container_id=self._remote_id,
        )

    async def stop(self) -> None:
        """Destroy the remote workspace. Best-effort; never raises."""
        if self._remote_id and self._client is not None:
            try:
                resp = await self._client.delete(self._url(self._destroy_path(self._remote_id)))
                resp.raise_for_status()
            except Exception as e:
                logger.warning(
                    "%s workspace %s destroy failed: %s", self.backend, self._remote_id, e
                )
        self._remote_id = None
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # pragma: no cover
                pass
            self._client = None

    async def __aenter__(self) -> _HTTPBackend:
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()


class DaytonaSandbox(_HTTPBackend):
    """Daytona workspace backend (https://daytona.io API).

    Lifecycle: POST /workspace -> POST /workspace/{id}/execute -> DELETE /workspace/{id}
    """

    backend = "daytona"

    def __init__(self, spec: SandboxSpec | None = None, *, transport: Any = None):
        api_key = _env("XAGENT_DAYTONA_API_KEY")
        api_url = _env("XAGENT_DAYTONA_API_URL") or "https://app.daytona.io/api"
        if not api_key:
            raise ServerlessSandboxError(
                "Daytona backend unavailable: XAGENT_DAYTONA_API_KEY not set"
            )
        super().__init__(
            spec,
            base_url=api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    @classmethod
    def is_configured(cls) -> bool:
        return bool(_env("XAGENT_DAYTONA_API_KEY"))

    def _create_path(self) -> str:
        return "/workspace"

    def _create_payload(self) -> dict[str, Any]:
        return {
            "image": self.spec.image,
            "env": self.spec.env,
            "resources": {
                "cpu": self.spec.cpu_limit,
                "memory": f"{self.spec.memory_limit_mb}Mi",
            },
            "network_disabled": not self.spec.enable_network,
            "labels": {"xagent-name-prefix": self.spec.name_prefix},
        }

    def _parse_create(self, data: dict[str, Any]) -> str:
        return str(data.get("id") or data.get("workspace_id") or "")

    def _exec_path(self, remote_id: str) -> str:
        return f"/workspace/{remote_id}/execute"

    def _parse_exec(self, data: dict[str, Any]) -> tuple[int, str, str]:
        return (
            int(data.get("exit_code", data.get("code", 1))),
            str(data.get("stdout", "")),
            str(data.get("stderr", "")),
        )

    def _destroy_path(self, remote_id: str) -> str:
        return f"/workspace/{remote_id}"


class ModalSandbox(_HTTPBackend):
    """Modal sandbox backend via a REST gateway.

    Auth headers follow Modal's token pair (Modal-Key / Modal-Secret).
    NOTE: Modal's official control plane is SDK-driven; point
    XAGENT_MODAL_API_URL at a gateway exposing POST /sandbox,
    POST /sandbox/{id}/exec, DELETE /sandbox/{id}. Not covered: token
    refresh, image builds, volume mounts (see module docstring).
    """

    backend = "modal"

    def __init__(self, spec: SandboxSpec | None = None, *, transport: Any = None):
        token_id = _env("XAGENT_MODAL_TOKEN_ID")
        token_secret = _env("XAGENT_MODAL_TOKEN_SECRET")
        api_url = _env("XAGENT_MODAL_API_URL") or "https://api.modal.com"
        if not token_id or not token_secret:
            raise ServerlessSandboxError(
                "Modal backend unavailable: XAGENT_MODAL_TOKEN_ID / "
                "XAGENT_MODAL_TOKEN_SECRET not set"
            )
        super().__init__(
            spec,
            base_url=api_url,
            headers={"Modal-Key": token_id, "Modal-Secret": token_secret},
            transport=transport,
        )

    @classmethod
    def is_configured(cls) -> bool:
        return bool(_env("XAGENT_MODAL_TOKEN_ID")) and bool(_env("XAGENT_MODAL_TOKEN_SECRET"))

    def _create_path(self) -> str:
        return "/sandbox"

    def _create_payload(self) -> dict[str, Any]:
        return {
            "image": self.spec.image,
            "timeout_secs": int(self.spec.timeout_seconds),
            "cpu": self.spec.cpu_limit,
            "memory_mb": self.spec.memory_limit_mb,
            "block_network": not self.spec.enable_network,
            "env": self.spec.env,
        }

    def _parse_create(self, data: dict[str, Any]) -> str:
        return str(data.get("sandbox_id") or data.get("id") or "")

    def _exec_path(self, remote_id: str) -> str:
        return f"/sandbox/{remote_id}/exec"

    def _parse_exec(self, data: dict[str, Any]) -> tuple[int, str, str]:
        return (
            int(data.get("returncode", data.get("exit_code", 1))),
            str(data.get("stdout", "")),
            str(data.get("stderr", "")),
        )

    def _destroy_path(self, remote_id: str) -> str:
        return f"/sandbox/{remote_id}"


class UnifiedSandbox:
    """Backend-selecting sandbox with Codex-style graceful degradation.

    Selection (XAGENT_SANDBOX_BACKEND):
        auto       -> daytona (if configured) -> modal (if configured)
                      -> docker -> subprocess
        daytona    -> daytona, degrade to docker/subprocess on failure
        modal      -> modal, degrade to docker/subprocess on failure
        docker     -> DockerSandbox as-is
        subprocess -> DockerSandbox forced to subprocess mode

    The first serverless failure logs a WARNING and permanently degrades
    this sandbox instance to the local chain; results keep flowing through
    the same SandboxResult shape with backend="docker"|"subprocess".
    """

    def __init__(
        self,
        spec: SandboxSpec | None = None,
        *,
        backend: str | None = None,
        transport: Any = None,
    ):
        self.spec = spec or SandboxSpec()
        self._requested = (backend or _env(ENV_BACKEND) or "auto").lower()
        self._transport = transport
        self._active: Any = None  # _HTTPBackend | DockerSandbox
        self._fallback: DockerSandbox | None = None
        self._degraded = False

    # -- selection ------------------------------------------------------
    def _pick_serverless(self) -> type[_HTTPBackend] | None:
        if self._requested == "daytona":
            return DaytonaSandbox if DaytonaSandbox.is_configured() else None
        if self._requested == "modal":
            return ModalSandbox if ModalSandbox.is_configured() else None
        if self._requested == "auto":
            if DaytonaSandbox.is_configured():
                return DaytonaSandbox
            if ModalSandbox.is_configured():
                return ModalSandbox
        return None

    def _make_fallback(self) -> DockerSandbox:
        if self._fallback is None:
            fb = DockerSandbox(self.spec)
            if self._requested == "subprocess":
                fb._use_docker = False
            self._fallback = fb
        return self._fallback

    async def _degrade(self, reason: str) -> None:
        if not self._degraded:
            logger.warning(
                "Serverless sandbox backend '%s' unavailable (%s); "
                "degrading to local docker/subprocess chain.",
                getattr(self._active, "backend", self._requested), reason,
            )
        self._degraded = True
        fb = self._make_fallback()
        if fb._workspace is None:
            await fb.start()
        self._active = fb

    @property
    def backend(self) -> str:
        if self._active is not None:
            return self._active.backend
        cls = self._pick_serverless()
        if cls is not None:
            return cls.backend
        return "subprocess" if self._requested == "subprocess" else DockerSandbox(self.spec).backend

    # -- lifecycle ------------------------------------------------------
    async def start(self) -> None:
        cls = self._pick_serverless()
        if cls is None:
            if self._requested in ("daytona", "modal"):
                logger.warning(
                    "Requested sandbox backend '%s' has no credentials configured; "
                    "falling back to local docker/subprocess chain.",
                    self._requested,
                )
            self._active = self._make_fallback()
            await self._active.start()
            return
        serverless = cls(self.spec, transport=self._transport)
        self._active = serverless
        try:
            await serverless.start()
        except Exception as e:
            await self._degrade(str(e))

    async def run(self, command: str, timeout: float | None = None) -> SandboxResult:
        if self._active is None:
            await self.start()
        try:
            return await self._active.run(command, timeout)
        except ServerlessSandboxError as e:
            if isinstance(self._active, DockerSandbox):
                raise
            await self._degrade(str(e))
            return await self._active.run(command, timeout)

    async def stop(self) -> None:
        if self._active is not None and not isinstance(self._active, DockerSandbox):
            await self._active.stop()
        if self._fallback is not None:
            await self._fallback.stop()
        self._active = None

    async def __aenter__(self) -> UnifiedSandbox:
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()


def create_sandbox(
    spec: SandboxSpec | None = None,
    *,
    backend: str | None = None,
    transport: Any = None,
) -> UnifiedSandbox:
    """Factory: build a backend-selected sandbox (config-driven).

    Same async API as DockerSandbox (start/run/stop, async context manager).
    """
    return UnifiedSandbox(spec, backend=backend, transport=transport)
