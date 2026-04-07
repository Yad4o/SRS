"""
app/core/otp.py

Purpose:
--------
OTP generation and email sending utilities for password reset.

Owner:
------
Om (Backend / Security)

Responsibilities:
-----------------
- Generate secure 6-digit OTPs
- Send OTP emails using Resend API
- Validate OTP format and expiration
- Handle OTP-related security measures

DO NOT:
-------
- Store OTPs in plain text for extended periods
- Send sensitive information via email
- Allow unlimited OTP attempts

"""

import random
import string
from datetime import datetime, timedelta
from typing import Optional
import os

import resend

from app.core.config import settings


def generate_otp() -> str:
    """
    Generate a secure 6-digit OTP.
    
    Returns:
        6-digit numeric OTP string
    """
    return ''.join(random.choices(string.digits, k=6))


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
        resend.api_key = os.getenv("RESEND_API_KEY")
        
        if not resend.api_key:
            print("⚠️  RESEND_API_KEY not configured: Using development fallback")
            print("   Set RESEND_API_KEY environment variable")
            return False  # This will trigger log_otp_for_dev fallback
        
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": email,
            "subject": "Your SRS OTP Code",
            "html": f"<p>Your OTP is: <strong>{otp}</strong>. It expires in 10 minutes.</p>"
        })
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def is_otp_expired(expires_at: datetime) -> bool:
    """
    Check if OTP has expired.
    
    Args:
        expires_at: OTP expiration timestamp
        
    Returns:
        True if expired, False otherwise
    """
    from datetime import timezone
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
    from datetime import timezone
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


# For development/testing - log OTP instead of sending email
def log_otp_for_dev(email: str, otp: str) -> None:
    """
    Log OTP for development purposes.
    
    Args:
        email: User email
        otp: Generated OTP
    """
    print(f"DEV LOG - OTP for {email}: {otp}")
    print(f"This OTP will expire in 10 minutes")
