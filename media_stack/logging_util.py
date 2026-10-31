import json
import logging
import sys
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

F = TypeVar('F', bound=Callable[..., Any])


def log_tool_call(func: F) -> F:
    """Decorator to log tool calls with arguments before execution."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Combine positional and keyword arguments
        call_args = {}
        
        # Get function parameter names
        import inspect
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        # Map positional arguments to parameter names
        for i, arg in enumerate(args):
            if i < len(param_names):
                call_args[param_names[i]] = arg
        
        # Add keyword arguments
        call_args.update(kwargs)
        
        # Log tool call BEFORE execution
        log_message = {
            "tool_name": func.__name__,
            "arguments": call_args
        }
        logger.info(f"Tool called: {json.dumps(log_message)}")
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            return result
            
        except Exception as exc:
            # Print error to stderr for visibility
            print(f"Error in {func.__name__}: {exc}", file=sys.stderr)
            raise
    
    return wrapper  # type: ignore
