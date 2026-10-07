import sys
from collections.abc import Callable
from typing import Any

# Check if native deprecation is available (Python 3.13+)
if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    # Fallback no-op decorator for Python 3.12
    def deprecated[F: Callable[..., Any]](
        message, category=DeprecationWarning, stacklevel=1
    ) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            return func  # Does nothing at runtime, prevents errors

        return decorator
