# Deployment Guide for SRS Support System

## Environment Variables Setup

The forgot password feature now requires Gmail credentials to be set as environment variables for security.

### Method 1: Docker Compose (Recommended)

1. **Create a .env file** in the project root:
```bash
GMAIL_EMAIL=your-actual-email@gmail.com
GMAIL_APP_PASSWORD=your-16-character-app-password
```

2. **Deploy with Docker Compose**:
```bash
docker-compose up -d
```

The docker-compose.yml will automatically pick up these environment variables.

### Method 2: Manual Environment Variables

Set environment variables before starting the application:

#### Linux/macOS:
```bash
export GMAIL_EMAIL=your-email@gmail.com
export GMAIL_APP_PASSWORD=your-app-password
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Windows (PowerShell):
```powershell
$env:GMAIL_EMAIL="your-email@gmail.com"
$env:GMAIL_APP_PASSWORD="your-app-password"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Windows (Command Prompt):
```cmd
set GMAIL_EMAIL=your-email@gmail.com
set GMAIL_APP_PASSWORD=your-app-password
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Method 3: Production Deployment (Vercel, Railway, etc.)

Add these environment variables in your deployment platform's dashboard:

- **GMAIL_EMAIL**: Your Gmail address
- **GMAIL_APP_PASSWORD**: Your 16-character Gmail App Password

## Gmail App Password Setup

1. **Enable 2-Factor Authentication**:
   - Go to: https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Generate App Password**:
   - Go to: https://myaccount.google.com/apppasswords
   - Select app: "Mail" or "Other (Custom name)"
   - Enter app name: "SRS Support System"
   - Generate and copy the 16-character password

3. **Configure Environment**:
   - Use the App Password (not your regular Gmail password)
   - Never commit the .env file to version control

## Security Notes

- ✅ **Never commit** credentials to version control
- ✅ **Use App Passwords**, not regular passwords
- ✅ **Keep .env file** private and secure
- ✅ **Rotate App Passwords** regularly for security
- ✅ **Use different passwords** for different environments

## Testing

After setting up environment variables, test the forgot password feature:

1. Go to: http://localhost:8000/forgot-password
2. Enter your email
3. Check your Gmail inbox for OTP
4. Enter OTP and reset password
5. Verify login works with new password

## Troubleshooting

If emails aren't sending:
1. Check environment variables are set correctly
2. Verify Gmail App Password is valid
3. Ensure 2FA is enabled on Gmail account
4. Check deployment logs for authentication errors

## Deployment Checklist

- [ ] Gmail 2FA enabled
- [ ] App Password generated
- [ ] Environment variables set
- [ ] .env file created (if using Docker)
- [ ] Forgot password flow tested
- [ ] Email delivery verified
