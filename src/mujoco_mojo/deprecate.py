import sys

# Check if native deprecation is available (Python 3.13+)
if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    # Fallback no-op decorator for Python 3.12
    def deprecated(message, category=DeprecationWarning, stacklevel=1):
        def decorator(func):
            return func  # Does nothing at runtime, prevents errors

        return decorator
