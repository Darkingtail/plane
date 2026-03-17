"""
Plane Webhook signature verification

Plane uses HMAC-SHA256 for webhook signature verification.
Header: X-Plane-Signature
"""

import hashlib
import hmac
import logging

from app.core.config import settings


logger = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, signature: str, secret: str = None) -> bool:
    """
    Verify Plane webhook signature

    Args:
        raw_body: Raw request body bytes
        signature: Value of X-Plane-Signature header
        secret: Webhook secret (defaults to settings.plane_webhook_secret)

    Returns:
        True if signature is valid
    """
    if not secret:
        secret = settings.plane_webhook_secret

    if not secret:
        logger.warning("Webhook secret not configured, skipping signature verification")
        return True

    if not signature:
        logger.warning("No signature provided in request")
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected, signature)

    if not is_valid:
        logger.warning("Webhook signature verification failed")

    return is_valid
