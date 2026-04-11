"""
Application-wide rate limiter (slowapi / limits).

IMPORTANT — worker limitation:
  With multiple Gunicorn workers, each worker has its own in-memory counter.
  The effective per-IP limit is:  configured_limit × worker_count.
  Example: "10/minute" with 4 workers → ~40 requests/minute reach the app.

  For strict per-IP enforcement across workers, switch to the Redis backend:

      from slowapi import Limiter
      from slowapi.util import get_remote_address

      limiter = Limiter(
          key_func=get_remote_address,
          storage_uri="redis://localhost:6379",
      )

  Until Redis is available, the current limits are intentionally set low enough
  that even 4× overshoot still provides meaningful protection.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
