"""
Middleware integration guide and examples.

This module demonstrates how to integrate the new middleware system
into the FastAPI application.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from backend.app.core.middleware.config import MiddlewareConfig, MiddlewareFactory


def setup_middleware(app: FastAPI, config: MiddlewareConfig | None = None) -> None:
    """
    Setup middleware for FastAPI application.

    Args:
        app: FastAPI application instance
        config: Middleware configuration (uses defaults if None)

    Example:
        from fastapi import FastAPI
        from backend.app.core.middleware.config import MiddlewareConfig, setup_middleware

        app = FastAPI()

        # Use default configuration
        setup_middleware(app)

        # Or customize configuration
        config = MiddlewareConfig()
        config.set_logging_config(
            slow_query_threshold=2.0,
            log_request_body=True,
        )
        config.set_error_handler_config(
            include_traceback=True,
            report_errors=True,
        )
        setup_middleware(app, config)
    """
    if config is None:
        config = MiddlewareConfig()

    # Create middleware chain
    chain = MiddlewareFactory.create_chain(app, config)

    # Add chain as middleware
    @app.middleware("http")
    async def middleware_chain(request, call_next):
        return await chain.execute(request, call_next)


def setup_middleware_with_custom_error_reporter(
    app: FastAPI,
    error_reporter: Any,
) -> None:
    """
    Setup middleware with custom error reporter (e.g., Sentry).

    Args:
        app: FastAPI application instance
        error_reporter: Async callable for reporting errors

    Example:
        import sentry_sdk
        from backend.app.core.middleware.config import MiddlewareConfig, setup_middleware_with_custom_error_reporter

        app = FastAPI()

        async def report_to_sentry(error_data):
            sentry_sdk.capture_exception(error_data)

        setup_middleware_with_custom_error_reporter(app, report_to_sentry)
    """
    config = MiddlewareConfig()
    config.set_error_handler_config(
        report_errors=True,
        error_reporter=error_reporter,
    )
    setup_middleware(app, config)


def setup_middleware_with_langfuse(
    app: FastAPI,
    langfuse_client: Any,
) -> None:
    """
    Setup middleware with Langfuse integration.

    Args:
        app: FastAPI application instance
        langfuse_client: Langfuse client instance

    Example:
        from langfuse import Langfuse
        from backend.app.core.middleware.config import MiddlewareConfig, setup_middleware_with_langfuse

        app = FastAPI()
        langfuse = Langfuse(api_key="your-api-key")

        setup_middleware_with_langfuse(app, langfuse)
    """
    config = MiddlewareConfig()
    config.set_request_tracer_config(
        langfuse_enabled=True,
        langfuse_client=langfuse_client,
    )
    setup_middleware(app, config)


def setup_middleware_for_production(app: FastAPI) -> None:
    """
    Setup middleware with production-optimized configuration.

    Args:
        app: FastAPI application instance

    Example:
        from backend.app.core.middleware.config import setup_middleware_for_production

        app = FastAPI()
        setup_middleware_for_production(app)
    """
    config = MiddlewareConfig()

    # Optimize for production
    config.set_logging_config(
        slow_query_threshold=2.0,
        log_request_body=False,
        log_response_body=False,
    )

    config.set_error_handler_config(
        include_traceback=False,
        include_details=False,
        report_errors=True,
    )

    config.set_performance_monitor_config(
        slow_request_threshold=2.0,
        enable_metrics=True,
    )

    setup_middleware(app, config)


def setup_middleware_for_development(app: FastAPI) -> None:
    """
    Setup middleware with development-optimized configuration.

    Args:
        app: FastAPI application instance

    Example:
        from backend.app.core.middleware.config import setup_middleware_for_development

        app = FastAPI()
        setup_middleware_for_development(app)
    """
    config = MiddlewareConfig()

    # Optimize for development
    config.set_logging_config(
        slow_query_threshold=0.5,
        log_request_body=True,
        log_response_body=True,
        max_body_size=5000,
    )

    config.set_error_handler_config(
        include_traceback=True,
        include_details=True,
        report_errors=False,
    )

    config.set_performance_monitor_config(
        slow_request_threshold=0.5,
        enable_metrics=True,
    )

    setup_middleware(app, config)


# Integration examples
INTEGRATION_EXAMPLES = {
    "basic": """
# Basic integration
from fastapi import FastAPI
from backend.app.core.middleware.config import setup_middleware

app = FastAPI()
setup_middleware(app)
""",
    "custom_config": """
# Custom configuration
from fastapi import FastAPI
from backend.app.core.middleware.config import MiddlewareConfig, setup_middleware

app = FastAPI()

config = MiddlewareConfig()
config.set_logging_config(slow_query_threshold=2.0)
config.set_error_handler_config(include_traceback=True)

setup_middleware(app, config)
""",
    "with_sentry": """
# With Sentry error reporting
import sentry_sdk
from fastapi import FastAPI
from backend.app.core.middleware.config import MiddlewareConfig, setup_middleware

app = FastAPI()

sentry_sdk.init(dsn="your-sentry-dsn")

async def report_to_sentry(error_data):
    sentry_sdk.capture_exception(error_data)

config = MiddlewareConfig()
config.set_error_handler_config(
    report_errors=True,
    error_reporter=report_to_sentry,
)

setup_middleware(app, config)
""",
    "with_langfuse": """
# With Langfuse tracing
from langfuse import Langfuse
from fastapi import FastAPI
from backend.app.core.middleware.config import MiddlewareConfig, setup_middleware

app = FastAPI()
langfuse = Langfuse(api_key="your-api-key")

config = MiddlewareConfig()
config.set_request_tracer_config(
    langfuse_enabled=True,
    langfuse_client=langfuse,
)

setup_middleware(app, config)
""",
    "production": """
# Production setup
from fastapi import FastAPI
from backend.app.core.middleware.config import setup_middleware_for_production

app = FastAPI()
setup_middleware_for_production(app)
""",
    "development": """
# Development setup
from fastapi import FastAPI
from backend.app.core.middleware.config import setup_middleware_for_development

app = FastAPI()
setup_middleware_for_development(app)
""",
}
