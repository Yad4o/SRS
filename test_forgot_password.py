#!/usr/bin/env python3
"""
Test script for forgot password functionality

This script tests the complete forgot password flow:
1. Request OTP for email
2. Verify OTP
3. Reset password

Usage:
python test_forgot_password.py

Requirements:
- Running backend server
- Test user in database
"""

import requests
import json
import time
import sys

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust if your backend runs on different port
TEST_EMAIL = "test@example.com"    # Replace with existing user email
TEST_PASSWORD = "NewPassword123!"  # New password to set

def test_forgot_password_flow():
    """Test the complete forgot password flow."""
    
    print("🧪 Testing Forgot Password Flow")
    print("=" * 50)
    
    # Step 1: Request OTP
    print("\n1. Requesting OTP...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/forgot-password",
            json={"email": TEST_EMAIL}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ OTP sent successfully!")
            print(f"   Message: {data.get('message')}")
            print(f"   Expires in: {data.get('otp_expires_in')} minutes")
        else:
            print(f"❌ Failed to send OTP: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    
    # Get OTP from user input (for testing)
    otp = input("\nEnter the 6-digit OTP you received: ").strip()
    
    if not otp or len(otp) != 6 or not otp.isdigit():
        print("❌ Invalid OTP format")
        return False
    
    # Step 2: Verify OTP
    print("\n2. Verifying OTP...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/verify-otp",
            json={"email": TEST_EMAIL, "otp": otp}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ OTP verified successfully!")
            print(f"   Message: {data.get('message')}")
            print(f"   Valid: {data.get('is_valid')}")
        else:
            print(f"❌ Failed to verify OTP: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    
    # Step 3: Reset Password
    print("\n3. Resetting password...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                "email": TEST_EMAIL,
                "otp": otp,
                "new_password": TEST_PASSWORD
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Password reset successfully!")
            print(f"   Message: {data.get('message')}")
        else:
            print(f"❌ Failed to reset password: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    
    # Step 4: Test login with new password
    print("\n4. Testing login with new password...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Login successful with new password!")
            print(f"   Token type: {data.get('token_type')}")
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    
    print("\n🎉 All tests passed! Forgot password flow is working correctly.")
    return True

def test_server_health():
    """Check if the server is running."""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

if __name__ == "__main__":
    print("Forgot Password Test Script")
    print("=" * 30)
    
    # Check if server is running
    if not test_server_health():
        print(f"❌ Server is not running at {BASE_URL}")
        print("Please start the backend server first.")
        sys.exit(1)
    
    print(f"✅ Server is running at {BASE_URL}")
    
    # Check if test email is provided
    if TEST_EMAIL == "test@example.com":
        print("\n⚠️  Please update TEST_EMAIL in the script with an existing user email")
        email = input("Enter existing user email: ").strip()
        if not email:
            print("❌ Email is required")
            sys.exit(1)
        globals()['TEST_EMAIL'] = email
    
    # Run the test
    success = test_forgot_password_flow()
    
    if success:
        print("\n✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Test failed!")
        sys.exit(1)
