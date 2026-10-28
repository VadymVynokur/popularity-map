import hashlib
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_NAMESPACE = "popularity-map:locations:v1"
GENERATION_KEY = f"{CACHE_NAMESPACE}:generation"


def _generation() -> int:
    generation = cache.get(GENERATION_KEY)
    if generation is None:
        cache.add(GENERATION_KEY, 1, timeout=None)
        generation = cache.get(GENERATION_KEY) or 1
    return int(generation)


def _canonical_query(request) -> str:
    pairs = []
    for key in sorted(request.query_params.keys()):
        values = sorted(request.query_params.getlist(key))
        pairs.append((key, values))
    return urlencode(pairs, doseq=True)


def make_list_cache_key(request) -> str:
    canonical = _canonical_query(request)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{CACHE_NAMESPACE}:list:{_generation()}:{digest}"


def get_cached_list(request):
    try:
        return cache.get(make_list_cache_key(request))
    except Exception:
        logger.warning("Location list cache read failed; falling back to database", exc_info=True)
        return None


def set_cached_list(request, data) -> None:
    try:
        cache.set(
            make_list_cache_key(request),
            data,
            timeout=settings.LOCATION_LIST_CACHE_TTL_SECONDS,
        )
    except Exception:
        logger.warning("Location list cache write failed", exc_info=True)


def invalidate_location_lists() -> None:
    try:
        if cache.add(GENERATION_KEY, 1, timeout=None):
            return
        cache.incr(GENERATION_KEY)
    except Exception:
        logger.warning("Location list cache invalidation failed", exc_info=True)
