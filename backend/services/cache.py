import os
import json
from typing import Optional, Any
import redis

# URL di Redis, es. redis://localhost:6379/1
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def get_cached(key: str) -> Optional[Any]:
    """
    Restituisce il valore Python deserializzato se presente in cache, altrimenti None.
    """
    raw = redis_client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def set_cache(key: str, value: Any, expire_seconds: int = 300) -> None:
    """
    Serializza in JSON e salva in Redis con TTL (default 5 minuti).
    """
    redis_client.set(key, json.dumps(value), ex=expire_seconds)

def invalidate_cache(pattern: str) -> None:
    """
    Elimina tutte le chiavi che corrispondono al pattern (glob-style).
    Es: invalidate_cache('screener:*') rimuove tutte le cache dello screener.
    """
    for k in redis_client.scan_iter(match=pattern):
        redis_client.delete(k)
