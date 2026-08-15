import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from playlist_migrate.exceptions import NetworkError, RateLimitError

logger = logging.getLogger(__name__)


def with_retries(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: type[Exception] | tuple[type[Exception], ...] = (RateLimitError, NetworkError),
):
    """Async Exponential Backoff decorator."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error("Max retries reached for %s: %s", func.__name__, e)
                        raise
                    logger.warning("Error in %s: %s. Retrying in %s seconds...", func.__name__, e, delay)
                    await asyncio.sleep(delay)
                    delay *= 2
            return await func(*args, **kwargs)

        return wrapper

    return decorator
