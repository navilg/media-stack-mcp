import json
import logging
import sys
from functools import wraps
from typing import Any, Callable, TypeVar

# ANSI color codes
COLORS = {
    'INFO': '\033[92m',      # Green
    'WARNING': '\033[93m',   # Yellow
    'ERROR': '\033[91m',     # Red
    'RESET': '\033[0m'       # Reset
}


def colorize_level(levelname: str) -> str:
    """Colorize log level name."""
    if levelname in COLORS:
        return f"{COLORS[levelname]}{levelname}:{COLORS['RESET']}"
    return f"{levelname}:"


def format_log_record(record: logging.LogRecord) -> str:
    """Format a log record with color and timestamp."""
    levelname = colorize_level(record.levelname)
    timestamp = record.created
    import time
    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
    message = record.getMessage()
    return f"{levelname} {time_str}: {message}"


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler
handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.INFO)

# Custom formatter using function
class CustomFormatter(logging.Formatter):
    def format(self, record):
        return format_log_record(record)

formatter = CustomFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)

F = TypeVar('F', bound=Callable[..., Any])


def log_tool_call(func: F) -> F:
    """Decorator to log tool calls with arguments before execution, and status after."""
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
            # Log successful completion
            logger.info(f"Tool calling successful: {func.__name__}")
            return result
            
        except Exception as exc:
            # Log failure with error message
            logger.error(f"Tool calling failed: {func.__name__} - {exc}")
            # Print error to stderr for visibility
            print(f"Error in {func.__name__}: {exc}", file=sys.stderr)
            raise
    
    return wrapper  # type: ignore
