"""
app/core/otp.py

Purpose:
OTP generation and email sending utilities for password reset.

Responsibilities:
- Generate secure 6-digit OTPs
- Send OTP emails using Resend API
- Validate OTP format and expiration
- Handle OTP-related security measures

DO NOT:
- Store OTPs in plain text for extended periods
- Send sensitive information via email
- Allow unlimited OTP attempts

"""

import logging
import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_otp() -> str:
    """
    Generate a secure 6-digit OTP.
    
    Returns:
        6-digit numeric OTP string
    """
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def send_otp_email(email: str, otp: str) -> bool:
    """
    Send OTP to user's email address using Resend API.
    
    Args:
        email: Recipient email address
        otp: 6-digit OTP code
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        resend.api_key = settings.RESEND_API_KEY

        if not resend.api_key:
            logger.warning("RESEND_API_KEY not configured — using development fallback")
            return False  # This will trigger log_otp_for_dev fallback

        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": email,
            "subject": "Your SRS OTP Code",
            "html": f"<p>Your OTP is: <strong>{otp}</strong>. It expires in 10 minutes.</p>"
        })
        return True

    except Exception as e:
        logger.error("Error sending OTP email: %s", e)
        return False


def is_otp_expired(expires_at: datetime) -> bool:
    """
    Check if OTP has expired.
    
    Args:
        expires_at: OTP expiration timestamp
        
    Returns:
        True if expired, False otherwise
    """
    now = datetime.now(timezone.utc)
    return now > expires_at


def validate_otp_format(otp: str) -> bool:
    """
    Validate OTP format (6 digits).
    
    Args:
        otp: OTP string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    return len(otp) == 6 and otp.isdigit()


def get_otp_expiration_time(minutes: int = 10) -> datetime:
    """
    Get OTP expiration time.
    
    Args:
        minutes: Number of minutes until expiration
        
    Returns:
        Datetime when OTP should expire
    """
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def log_otp_for_dev(email: str, otp: str) -> None:
    """
    Log OTP for development purposes.

    Args:
        email: User email
        otp: Generated OTP
    """
    logger.debug("DEV LOG — OTP for %s: %s (expires in 10 minutes)", email, otp)

