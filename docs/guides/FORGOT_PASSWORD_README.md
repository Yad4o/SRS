# Forgot Password Feature Documentation

This document describes the forgot password functionality that allows users to reset their password using email OTP verification.

## Overview

The forgot password feature provides a secure way for users to reset their passwords when they forget them. The process involves:

1. User enters their email address
2. System generates a 6-digit OTP and sends it to the user's email
3. User enters the OTP to verify their identity
4. User sets a new password
5. Password is updated and user can login with new credentials

## Security Features

- **OTP Expiration**: OTPs expire after 10 minutes
- **Maximum Attempts**: Maximum 3 OTP verification attempts
- **Secure Password Hashing**: Uses bcrypt for password storage
- **Input Validation**: All inputs are validated on both frontend and backend
- **Rate Limiting**: Failed OTP attempts are tracked

## Backend Implementation

### Database Schema

The `users` table has been updated with the following columns:

```sql
reset_otp VARCHAR(6)              -- 6-digit OTP code
reset_otp_expires_at TIMESTAMP    -- OTP expiration time
reset_otp_attempts INTEGER DEFAULT 0 -- Number of verification attempts
```

### API Endpoints

#### 1. Request OTP
```
POST /auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}

Response:
{
  "message": "OTP sent to your email address",
  "otp_expires_in": 10
}
```

#### 2. Verify OTP
```
POST /auth/verify-otp
Content-Type: application/json

{
  "email": "user@example.com",
  "otp": "123456"
}

Response:
{
  "message": "OTP verified successfully",
  "is_valid": true
}
```

#### 3. Reset Password
```
POST /auth/reset-password
Content-Type: application/json

{
  "email": "user@example.com",
  "otp": "123456",
  "new_password": "NewPassword123!"
}

Response:
{
  "message": "Password reset successfully"
}
```

### Email Configuration

The system uses Gmail SMTP for sending OTP emails. Update the configuration in `app/core/otp.py`:

```python
sender_email = "your-email@gmail.com"      # Your Gmail address
sender_password = "your-app-password"      # Gmail app password (not regular password)
```

**Important**: Use an App Password for Gmail, not your regular password. Enable 2-factor authentication and generate an App Password from Google Account settings.

## Frontend Implementation

### Components

#### ForgotPassword Component
Located at: `client/src/pages/ForgotPassword.tsx`

Features:
- Multi-step form (Email → OTP → Password Reset)
- Progress indicator
- Form validation
- Error handling
- Loading states

### API Integration

The frontend uses the following API functions from `client/src/api/auth.ts`:

```typescript
export const forgotPassword = (email: string) =>
  client.post('/auth/forgot-password', { email })

export const verifyOTP = (email: string, otp: string) =>
  client.post('/auth/verify-otp', { email, otp })

export const resetPassword = (email: string, otp: string, newPassword: string) =>
  client.post('/auth/reset-password', { email, otp, new_password: newPassword })
```

### Authentication Hook

Extended `useAuth` hook in `client/src/hooks/useAuth.ts` with forgot password functions:

```typescript
const { forgotPassword, verifyOTP, resetPassword } = useAuth()
```

## Setup Instructions

### 1. Database Migration

Run the migration to add OTP columns to the users table:

```bash
cd support-resolution-system
python migrations/add_password_reset_otp_columns.py
```

### 2. Email Configuration

Update `app/core/otp.py` with your Gmail credentials:

```python
sender_email = "your-email@gmail.com"
sender_password = "your-app-password"  # Use App Password
```

### 3. Start Backend

```bash
cd support-resolution-system
python -m uvicorn app.main:app --reload
```

### 4. Start Frontend

```bash
cd srs-frontend
npm run dev
```

## Testing

### Automated Testing

Run the test script to verify the functionality:

```bash
cd support-resolution-system
python test_forgot_password.py
```

### Manual Testing

1. Navigate to `/login`
2. Click "Forgot your password?"
3. Enter an existing user email
4. Check email for OTP (or check console logs for development)
5. Enter OTP in the verification step
6. Set a new password
7. Try logging in with the new password

## Development Notes

### OTP Logging

For development, OTPs are logged to the console when email sending fails. Check the backend console for:

```
DEV LOG - OTP for user@example.com: 123456
This OTP will expire in 10 minutes
```

### Password Requirements

New passwords must meet the following requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter  
- At least one digit
- At least one special character

### Error Handling

The system handles various error scenarios:
- Email not found
- Invalid/expired OTP
- Maximum attempts exceeded
- Network errors
- Invalid password format

## Troubleshooting

### Common Issues

1. **Email not sending**
   - Check Gmail credentials
   - Ensure 2-factor authentication is enabled
   - Use App Password (not regular password)

2. **OTP verification failing**
   - Check if OTP is expired (10-minute limit)
   - Verify correct OTP format (6 digits)
   - Check remaining attempts (max 3)

3. **Database errors**
   - Run the migration script
   - Check database connection

4. **Frontend routing issues**
   - Ensure `/forgot-password` route is added to App.tsx
   - Check component imports

### Debug Mode

Enable debug logging by setting environment variable:

```bash
export DEBUG=true
python -m uvicorn app.main:app --reload
```

## Security Considerations

1. **Email Security**: Never send passwords via email
2. **OTP Security**: Use cryptographically secure OTP generation
3. **Rate Limiting**: Implement rate limiting for OTP requests
4. **Password Storage**: Always hash passwords with bcrypt
5. **Input Validation**: Validate all inputs on both frontend and backend

## Future Enhancements

- SMS OTP support
- Multiple email provider support
- Rate limiting middleware
- Password history tracking
- Account lockout after failed attempts
- Email template customization
