"""FastAPI integration example for LLM providers.

This module demonstrates how to integrate LLM providers into a FastAPI application.
"""


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.app.core.llm_providers import (
    LLMConfig,
    LLMMessage,
    MessageRole,
    ProviderType,
)
from backend.app.core.llm_providers.base import LLMProviderError
from backend.app.core.llm_providers.factory import LLMRouter


# Pydantic models for API
class Message(BaseModel):
    """Message model for API."""
    role: str
    content: str


class CompletionRequest(BaseModel):
    """Completion request model."""
    messages: list[Message]
    provider: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class CompletionResponse(BaseModel):
    """Completion response model."""
    content: str
    provider: str
    model: str
    usage: dict
    cost_usd: float
    latency_ms: float


class ProviderStats(BaseModel):
    """Provider statistics model."""
    provider: str
    model: str
    request_count: int
    total_cost_usd: float


# Global router instance
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Get or create global LLM router."""
    global _router
    if _router is None:
        _router = LLMRouter()
        # Initialize with default providers
        _initialize_router(_router)
    return _router


def _initialize_router(router: LLMRouter) -> None:
    """Initialize router with configured providers."""
    import os

    # Configure OpenAI
    if os.getenv("OPENAI_API_KEY"):
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        router.register("openai", config)

    # Configure Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
        router.register("anthropic", config)

    # Configure DeepSeek
    if os.getenv("DEEPSEEK_API_KEY"):
        config = LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
        )
        router.register("deepseek", config)

    # Configure Ollama
    config = LLMConfig(
        provider=ProviderType.OLLAMA,
        model=os.getenv("OLLAMA_MODEL", "llama2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    router.register("ollama", config)


def create_app() -> FastAPI:
    """Create FastAPI application with LLM provider endpoints."""
    app = FastAPI(
        title="X-Agent LLM Provider API",
        description="API for accessing multiple LLM providers",
        version="1.0.0",
    )

    @app.on_event("startup")
    async def startup():
        """Initialize router on startup."""
        get_router()

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok"}

    @app.get("/providers")
    async def list_providers():
        """List available providers."""
        router = get_router()
        return {
            "providers": router.list_providers(),
            "default": router._default_provider,
        }

    @app.get("/providers/{provider_name}/stats")
    async def get_provider_stats(provider_name: str):
        """Get statistics for a provider."""
        router = get_router()
        try:
            provider = router.get(provider_name)
            stats = provider.get_stats()
            return ProviderStats(**stats)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/complete")
    async def complete(request: CompletionRequest) -> CompletionResponse:
        """Generate a completion.

        Args:
            request: Completion request with messages and optional provider

        Returns:
            Completion response

        Raises:
            HTTPException: If provider not found or request fails
        """
        router = get_router()

        try:
            # Get provider
            provider = router.get(request.provider)

            # Convert messages
            messages = [
                LLMMessage(
                    role=MessageRole(msg.role) if msg.role in ["system", "user", "assistant"] else msg.role,
                    content=msg.content,
                )
                for msg in request.messages
            ]

            # Prepare kwargs
            kwargs = {}
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.max_tokens is not None:
                kwargs["max_tokens"] = request.max_tokens

            # Get completion
            response = await provider.complete(messages, **kwargs)

            return CompletionResponse(
                content=response.content,
                provider=response.provider,
                model=response.model,
                usage=response.usage,
                cost_usd=response.cost_usd,
                latency_ms=response.latency_ms,
            )

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except LLMProviderError as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/stream")
    async def stream(request: CompletionRequest):
        """Stream a completion.

        Args:
            request: Completion request with messages and optional provider

        Returns:
            Server-sent events stream
        """
        from fastapi.responses import StreamingResponse

        router = get_router()

        async def generate():
            try:
                # Get provider
                provider = router.get(request.provider)

                # Convert messages
                messages = [
                    LLMMessage(
                        role=MessageRole(msg.role) if msg.role in ["system", "user", "assistant"] else msg.role,
                        content=msg.content,
                    )
                    for msg in request.messages
                ]

                # Prepare kwargs
                kwargs = {}
                if request.temperature is not None:
                    kwargs["temperature"] = request.temperature
                if request.max_tokens is not None:
                    kwargs["max_tokens"] = request.max_tokens

                # Stream completion
                async for chunk in provider.stream(messages, **kwargs):
                    yield f"data: {chunk.content}\n\n"

            except ValueError as e:
                yield f"data: ERROR: {e!s}\n\n"
            except LLMProviderError as e:
                yield f"data: ERROR: {e!s}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/stats")
    async def get_all_stats():
        """Get statistics for all providers."""
        router = get_router()
        stats = router.get_stats()
        return {
            provider: ProviderStats(**provider_stats)
            for provider, provider_stats in stats.items()
        }

    return app


# Example usage
if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
