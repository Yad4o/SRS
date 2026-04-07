# Environment Variables Setup Guide

## Vercel (Frontend) Deployment

### 1. Go to Vercel Dashboard
- Visit: https://vercel.com/dashboard
- Select your `srs-frontend` project

### 2. Set Environment Variables
In your Vercel project settings, add these environment variables:

```
VITE_API_URL=https://your-backend-url.onrender.com
```

### 3. Redeploy
- Push changes to trigger automatic deployment
- Vercel will pick up environment variables automatically

---

## Render (Backend) Deployment

### 1. Go to Render Dashboard
- Visit: https://dashboard.render.com
- Select your `support-resolution-system` service

### 2. Set Environment Variables
In your Render service settings, add these environment variables:

```
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-character-app-password
DATABASE_URL=your-production-database-url
SECRET_KEY=your-production-secret-key
OPENAI_API_KEY=your-openai-api-key
```

### 3. Redeploy
- Push changes to trigger automatic deployment
- Render will pick up environment variables and restart the service

---

## Quick Setup Commands

### Frontend (Vercel):
```bash
cd srs-frontend
git add .
git commit -m "configure for production deployment"
git push origin main
```

### Backend (Render):
```bash
cd support-resolution-system
git add .
git commit -m "configure for production deployment"  
git push origin main
```

---

## Environment Variables Reference

### For Frontend (.env):
```bash
VITE_API_URL=https://your-backend-url.onrender.com
```

### For Backend (.env):
```bash
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-character-app-password
DATABASE_URL=postgresql://user:password@host:5432/dbname
SECRET_KEY=your-secret-key
OPENAI_API_KEY=your-openai-key
ENVIRONMENT=production
```

---

## Testing After Deployment

1. **Frontend**: Visit your Vercel URL
2. **Backend**: Check Render dashboard for service status
3. **Forgot Password**: Test the complete flow
4. **Email Delivery**: Verify OTP emails are sent
5. **Login**: Test new password functionality

---

## Security Notes

- ✅ **Never commit** `.env` files to version control
- ✅ **Use different** credentials for production vs development
- ✅ **Generate new** App Passwords for production
- ✅ **Monitor** deployment logs for issues
