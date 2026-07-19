"""Remote configuration center integration module."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class RemoteConfigError(Exception):
    """Remote configuration error."""

    pass


class RemoteConfigProvider(ABC):
    """Abstract base class for remote configuration providers."""

    @abstractmethod
    async def get_config(self, key: str) -> Optional[Any]:
        """Get configuration value from remote source.

        Args:
            key: Configuration key

        Returns:
            Configuration value or None if not found
        """
        pass

    @abstractmethod
    async def set_config(self, key: str, value: Any) -> None:
        """Set configuration value in remote source.

        Args:
            key: Configuration key
            value: Configuration value
        """
        pass

    @abstractmethod
    async def watch_config(self, key: str, callback) -> None:
        """Watch configuration key for changes.

        Args:
            key: Configuration key
            callback: Callback function when value changes
        """
        pass


class ConsulConfigProvider(RemoteConfigProvider):
    """Consul-based remote configuration provider."""

    def __init__(self, host: str = "localhost", port: int = 8500, datacenter: str = "dc1"):
        """Initialize Consul provider.

        Args:
            host: Consul host
            port: Consul port
            datacenter: Consul datacenter
        """
        self.host = host
        self.port = port
        self.datacenter = datacenter
        self.base_url = f"http://{host}:{port}/v1"
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_config(self, key: str) -> Optional[Any]:
        """Get configuration from Consul KV store.

        Args:
            key: Configuration key

        Returns:
            Configuration value or None if not found
        """
        try:
            url = f"{self.base_url}/kv/{key}"
            response = await self.client.get(url)
            if response.status_code == 200:
                data = response.json()
                if data:
                    import base64
                    value = base64.b64decode(data[0]["Value"]).decode()
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value
            return None
        except Exception as e:
            logger.error(f"Failed to get config from Consul: {e}")
            raise RemoteConfigError(f"Failed to get config: {e}")

    async def set_config(self, key: str, value: Any) -> None:
        """Set configuration in Consul KV store.

        Args:
            key: Configuration key
            value: Configuration value
        """
        try:
            url = f"{self.base_url}/kv/{key}"
            if isinstance(value, dict):
                value = json.dumps(value)
            response = await self.client.put(url, content=str(value))
            if response.status_code != 200:
                raise RemoteConfigError(f"Failed to set config: {response.text}")
        except Exception as e:
            logger.error(f"Failed to set config in Consul: {e}")
            raise RemoteConfigError(f"Failed to set config: {e}")

    async def watch_config(self, key: str, callback) -> None:
        """Watch configuration key in Consul.

        Args:
            key: Configuration key
            callback: Callback function when value changes
        """
        try:
            index = 0
            while True:
                url = f"{self.base_url}/kv/{key}"
                params = {"index": index, "wait": "5m"}
                response = await self.client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        import base64
                        value = base64.b64decode(data[0]["Value"]).decode()
                        index = data[0]["ModifyIndex"]
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            pass
                        await callback(value)
        except asyncio.CancelledError:
            logger.info("Config watch cancelled")
        except Exception as e:
            logger.error(f"Error watching config in Consul: {e}")

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class EtcdConfigProvider(RemoteConfigProvider):
    """Etcd-based remote configuration provider."""

    def __init__(self, host: str = "localhost", port: int = 2379):
        """Initialize Etcd provider.

        Args:
            host: Etcd host
            port: Etcd port
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/v3"
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_config(self, key: str) -> Optional[Any]:
        """Get configuration from Etcd.

        Args:
            key: Configuration key

        Returns:
            Configuration value or None if not found
        """
        try:
            import base64
            url = f"{self.base_url}/kv/range"
            data = {"key": base64.b64encode(key.encode()).decode()}
            response = await self.client.post(url, json=data)
            if response.status_code == 200:
                result = response.json()
                if result.get("kvs"):
                    value = base64.b64decode(result["kvs"][0]["value"]).decode()
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value
            return None
        except Exception as e:
            logger.error(f"Failed to get config from Etcd: {e}")
            raise RemoteConfigError(f"Failed to get config: {e}")

    async def set_config(self, key: str, value: Any) -> None:
        """Set configuration in Etcd.

        Args:
            key: Configuration key
            value: Configuration value
        """
        try:
            import base64
            url = f"{self.base_url}/kv/put"
            if isinstance(value, dict):
                value = json.dumps(value)
            data = {
                "key": base64.b64encode(key.encode()).decode(),
                "value": base64.b64encode(str(value).encode()).decode(),
            }
            response = await self.client.post(url, json=data)
            if response.status_code != 200:
                raise RemoteConfigError(f"Failed to set config: {response.text}")
        except Exception as e:
            logger.error(f"Failed to set config in Etcd: {e}")
            raise RemoteConfigError(f"Failed to set config: {e}")

    async def watch_config(self, key: str, callback) -> None:
        """Watch configuration key in Etcd.

        Args:
            key: Configuration key
            callback: Callback function when value changes
        """
        try:
            import base64
            url = f"{self.base_url}/watch"
            data = {"create_request": {"key": base64.b64encode(key.encode()).decode()}}
            async with self.client.stream("POST", url, json=data) as response:
                async for line in response.aiter_lines():
                    if line:
                        event = json.loads(line)
                        if "result" in event and event["result"].get("events"):
                            for evt in event["result"]["events"]:
                                if evt.get("kv"):
                                    value = base64.b64decode(evt["kv"]["value"]).decode()
                                    try:
                                        value = json.loads(value)
                                    except json.JSONDecodeError:
                                        pass
                                    await callback(value)
        except asyncio.CancelledError:
            logger.info("Config watch cancelled")
        except Exception as e:
            logger.error(f"Error watching config in Etcd: {e}")

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class RemoteConfigManager:
    """Manage remote configuration."""

    def __init__(self, provider: RemoteConfigProvider):
        """Initialize remote config manager.

        Args:
            provider: Remote configuration provider
        """
        self.provider = provider
        self.cache: Dict[str, Any] = {}
        self.watch_tasks: Dict[str, asyncio.Task] = {}

    async def get(self, key: str, use_cache: bool = True) -> Optional[Any]:
        """Get configuration value.

        Args:
            key: Configuration key
            use_cache: Use cached value if available

        Returns:
            Configuration value or None if not found
        """
        if use_cache and key in self.cache:
            return self.cache[key]

        value = await self.provider.get_config(key)
        if value is not None:
            self.cache[key] = value
        return value

    async def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        await self.provider.set_config(key, value)
        self.cache[key] = value

    async def watch(self, key: str, callback) -> None:
        """Watch configuration key.

        Args:
            key: Configuration key
            callback: Callback function when value changes
        """
        async def watch_wrapper():
            await self.provider.watch_config(key, callback)

        task = asyncio.create_task(watch_wrapper())
        self.watch_tasks[key] = task

    def stop_watch(self, key: str) -> None:
        """Stop watching configuration key.

        Args:
            key: Configuration key
        """
        if key in self.watch_tasks:
            self.watch_tasks[key].cancel()
            del self.watch_tasks[key]

    async def close(self) -> None:
        """Close remote config manager."""
        for task in self.watch_tasks.values():
            task.cancel()
        self.watch_tasks.clear()
        await self.provider.close()
