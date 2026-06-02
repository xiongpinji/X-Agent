"""LLM Provider Factory and Router

Factory for creating LLM providers and router for managing multiple providers.
"""

from __future__ import annotations

from typing import Any, Optional

from .anthropic import AnthropicProvider
from .base import BaseLLMProvider, LLMConfig, ProviderType
from .deepseek import DeepSeekProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    _providers = {
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.DEEPSEEK: DeepSeekProvider,
        ProviderType.OLLAMA: OllamaProvider,
    }

    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLMProvider:
        """Create an LLM provider based on configuration.

        Args:
            config: LLM configuration

        Returns:
            Configured LLM provider instance

        Raises:
            ValueError: If provider type is not supported
        """
        provider_type = config.provider
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderType(provider_type)
            except ValueError:
                raise ValueError(f"Unknown provider: {provider_type}")

        if provider_type not in cls._providers:
            raise ValueError(f"Unsupported provider: {provider_type}")

        provider_class = cls._providers[provider_type]
        return provider_class(config)

    @classmethod
    def register(cls, provider_type: ProviderType | str, provider_class: type[BaseLLMProvider]) -> None:
        """Register a custom provider.

        Args:
            provider_type: Provider type identifier
            provider_class: Provider class
        """
        if isinstance(provider_type, str):
            provider_type = ProviderType(provider_type)
        cls._providers[provider_type] = provider_class


class LLMRouter:
    """Router for managing multiple LLM providers."""

    def __init__(self) -> None:
        """Initialize router."""
        self._providers: dict[str, BaseLLMProvider] = {}
        self._default_provider: Optional[str] = None

    def register(self, name: str, config: LLMConfig) -> BaseLLMProvider:
        """Register an LLM provider.

        Args:
            name: Provider name/identifier
            config: LLM configuration

        Returns:
            Created provider instance
        """
        provider = LLMProviderFactory.create(config)
        self._providers[name] = provider

        if self._default_provider is None:
            self._default_provider = name

        return provider

    def get(self, name: Optional[str] = None) -> BaseLLMProvider:
        """Get an LLM provider.

        Args:
            name: Provider name. If None, returns default provider.

        Returns:
            LLM provider instance

        Raises:
            ValueError: If provider not found
        """
        if name is None:
            if self._default_provider is None:
                raise ValueError("No default provider configured")
            name = self._default_provider

        if name not in self._providers:
            raise ValueError(f"Provider '{name}' not found")

        return self._providers[name]

    def set_default(self, name: str) -> None:
        """Set default provider.

        Args:
            name: Provider name

        Raises:
            ValueError: If provider not found
        """
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' not found")
        self._default_provider = name

    def list_providers(self) -> list[str]:
        """List all registered providers.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get statistics for all providers.

        Returns:
            Dictionary with stats for each provider
        """
        return {
            name: provider.get_stats()
            for name, provider in self._providers.items()
        }
