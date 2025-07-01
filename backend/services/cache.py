import os
import pickle
import logging

# ==================== VECCHIO IMPLEMENTAZIONE COMMENTATA ====================
# try:
#     import redis
# except ImportError:
#     redis = None
#
# # URL di Redis (usato anche da Celery); in locale punta a localhost:6379
# REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
#
# logger = logging.getLogger(__name__)
#
# # Provo a creare il client. Se fallisce, porto redis_client a None
# if redis:
#     try:
#         redis_client = redis.Redis.from_url(REDIS_URL)
#         # Provo una connessione di salute veloce
#         redis_client.ping()
#     except Exception as e:
#         logger.warning(f"🔶 Non riesco a connettermi a Redis ({REDIS_URL}): {e}")
#         redis_client = None
# else:
#     logger.warning("🔶 Redis non è installato, cache disabilitata")
#     redis_client = None
#
# def get_cache(key: str):
#     """
#     Ritorna l’oggetto dal cache se presente, altrimenti None.
#     In caso di errore di connessione, logga e restituisce None.
#     """
#     if not redis_client:
#         return None
#     try:
#         raw = redis_client.get(key)
#         if not raw:
#             return None
#         return pickle.loads(raw)
#     except Exception as e:
#         logger.warning(f"🔶 Redis GET errore per chiave {key}: {e}")
#         return None
#
# def set_cache(key: str, value, ttl: int = None):
#     """
#     Salva in cache. Se ttl è passato, lo usa come scadenza in secondi.
#     In caso di errore di connessione, logga e silently skip.
#     """
#     if not redis_client:
#         return
#     try:
#         data = pickle.dumps(value)
#         if ttl:
#             redis_client.set(key, data, ex=ttl)
#         else:
#             redis_client.set(key, data)
#     except Exception as e:
#         logger.warning(f"🔶 Redis SET errore per chiave {key}: {e}")
#=============================================================================

logger = logging.getLogger(__name__)

def get_cache(key: str):
    """
    Cache disabilitata: forziamo sempre miss.
    """
    return None

def set_cache(key: str, value, ttl: int = None):
    """
    Cache disabilitata: no-op.
    """
    return
