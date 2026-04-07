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
- Send OTP emails using Gmail SMTP
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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional

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
    Send OTP to user's email address using Gmail SMTP.
    
    Args:
        email: Recipient email address
        otp: 6-digit OTP code
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Gmail SMTP configuration
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "kurukuruom@gmail.com"  # Replace with your Gmail
        sender_password = "pass@1706"   # Replace with your Gmail app password
        
        # Create message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = email
        message["Subject"] = "Password Reset OTP - SRS Support"
        
        # Email body
        body = f"""
        Hello,
        
        You requested a password reset for your SRS Support account.
        
        Your OTP code is: {otp}
        
        This OTP will expire in 10 minutes.
        
        If you didn't request this password reset, please ignore this email.
        
        Thanks,
        SRS Support Team
        """
        
        message.attach(MIMEText(body, "plain"))
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = message.as_string()
        server.sendmail(sender_email, email, text)
        server.quit()
        
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
    return datetime.utcnow() + timedelta(minutes=minutes)


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
