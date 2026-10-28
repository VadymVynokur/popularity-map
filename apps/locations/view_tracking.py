import hashlib
import logging
from functools import lru_cache

import redis
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.locations.models import Location, LocationView, LocationViewThrottle

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _redis_client():
    return redis.Redis.from_url(
        settings.REDIS_VIEW_COOLDOWN_URL,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )


def _redis_key(location_id: int, identity_hash: str) -> str:
    return f"popularity-map:views:v1:{location_id}:{identity_hash}"


def _claim_redis(key: str) -> bool | None:
    try:
        return bool(
            _redis_client().set(
                key,
                "1",
                nx=True,
                ex=settings.VIEW_COOLDOWN_SECONDS,
            )
        )
    except Exception:
        logger.warning("Redis view cooldown pre-check failed; using database", exc_info=True)
        return None


def _set_redis(key: str, ttl: int) -> None:
    try:
        _redis_client().set(key, "1", ex=max(1, ttl))
    except Exception:
        logger.warning("Redis view cooldown write failed", exc_info=True)


def _delete_redis(key: str) -> None:
    try:
        _redis_client().delete(key)
    except Exception:
        logger.warning("Redis view cooldown cleanup failed", exc_info=True)


def identity_for_request(request) -> str:
    if request.user and request.user.is_authenticated:
        return f"user:{request.user.pk}"
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key
        # Ensure SessionMiddleware sends the newly created session cookie.
        request.session.modified = True
    return f"session:{session_key}"


def track_location_view(location: Location, identity: str) -> bool:
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    key = _redis_key(location.pk, identity_hash)
    claimed = _claim_redis(key)
    if claimed is False:
        return False

    now = timezone.now()
    cooldown = settings.VIEW_COOLDOWN_SECONDS
    try:
        with transaction.atomic():
            created = False
            try:
                throttle = LocationViewThrottle.objects.select_for_update().get(
                    location=location,
                    identity_hash=identity_hash,
                )
            except LocationViewThrottle.DoesNotExist:
                try:
                    with transaction.atomic():
                        throttle = LocationViewThrottle.objects.create(
                            location=location,
                            identity_hash=identity_hash,
                            last_counted_at=now,
                        )
                    created = True
                except IntegrityError:
                    throttle = LocationViewThrottle.objects.select_for_update().get(
                        location=location,
                        identity_hash=identity_hash,
                    )

            if not created:
                elapsed = (now - throttle.last_counted_at).total_seconds()
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    transaction.on_commit(
                        lambda: _set_redis(key, remaining) if remaining > 0 else _delete_redis(key)
                    )
                    return False

            LocationView.objects.create(
                location=location,
                identity_hash=identity_hash,
                viewed_at=now,
            )
            throttle.last_counted_at = now
            throttle.save(update_fields=["last_counted_at"])
            transaction.on_commit(lambda: _set_redis(key, cooldown))
            return True
    except Exception:
        _delete_redis(key)
        raise
