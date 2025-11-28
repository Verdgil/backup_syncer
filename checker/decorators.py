import logging
from typing import Callable, Any


def retry(count=10):
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            error = None
            for i in range(count):
                try:
                    res = func(*args, **kwargs)
                except Exception as e:
                    error = e
                else:
                    return res
            logging.error(error)
            raise error
        return wrapper
    return decorator


def lru_cache_custom(func: Callable) -> Callable:
    cache = {}
    def wrapper(*args, **kwargs) -> Any:
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return wrapper

