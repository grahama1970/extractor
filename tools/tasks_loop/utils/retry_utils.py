import time
import subprocess
import functools
from typing import Callable, Any, List

def retry_subprocess(attempts: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """
    Decorator to retry a function that executes a subprocess.
    Retries on non-zero return code or CalledProcessError.
    
    Args:
        attempts: Number of total attempts (1 means no retry).
        delay: Initial delay in seconds.
        backoff: Multiplier for delay after each failure.
    """
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for i in range(attempts):
                try:
                    result = func(*args, **kwargs)
                    if isinstance(result, bool):
                        if not result:
                             raise RuntimeError("Command returned False")
                    elif isinstance(result, int):
                         if result != 0:
                             raise RuntimeError(f"Command returned exit code {result}")
                    return result
                
                except (subprocess.CalledProcessError, RuntimeError, Exception) as e:
                    last_exception = e
                    if i < attempts - 1:
                        print(f"⚠️  Command failed (Attempt {i+1}/{attempts}). Retrying in {current_delay}s... Error: {e}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"❌ Command failed permanently after {attempts} attempts.")
                        raise last_exception
            return False # Should be unreachable if we raise on last attempt
        return wrapper
    return decorator
