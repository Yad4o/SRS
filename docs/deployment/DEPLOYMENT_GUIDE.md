# 🚀 Deployment Guide

## 🌐 Frontend Deployment (GitHub Pages)

### ✅ Automatic Deployment Setup
The frontend is configured for automatic deployment to GitHub Pages:

1. **GitHub Actions**: `.github/workflows/deploy.yml` 
2. **Vite Config**: Configured with base path for GitHub Pages
3. **Auto-Deploy**: Triggers on push to `main` branch

### 🔄 Manual Deployment Steps
```bash
# 1. Merge your feature branches to main
git checkout main
git merge feature/role-based-registration
git merge feature/frontend-improvements

# 2. Push to main (triggers auto-deployment)
git push origin main

# 3. Check Actions tab for deployment status
# 4. Visit GitHub Pages settings once deployed
```

### 🌍 Frontend URL
```
https://yad4o.github.io/srs-frontend/
```

---

## 🐳 Backend Deployment (Docker)

### Option 1: Local Docker Deployment
```bash
# 1. Clone backend repository
git clone https://github.com/Yad4o/support-resolution-system.git
cd support-resolution-system

# 2. Copy environment file
cp .env.example .env
# Edit .env with your settings

# 3. Deploy with Docker Compose
docker-compose up -d

# 4. Check deployment
curl http://localhost:8000/health
```

### Option 2: Cloud Deployment Options

#### **A) Railway (Easiest)**
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and deploy
railway login
railway up
```

#### **B) Render (Free Tier)**
1. Connect your GitHub repo to Render
2. Select "Web Service"
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env.example`

#### **C) Heroku (Paid)**
```bash
# 1. Install Heroku CLI
# 2. Create app
heroku create your-app-name

# 3. Set environment variables
heroku config:set DATABASE_URL=your-db-url
heroku config:set SECRET_KEY=your-secret-key
heroku config:set OPENAI_API_KEY=your-openai-key

# 4. Deploy
git push heroku main
```

#### **D) DigitalOcean App Platform**
1. Connect GitHub repo
2. Configure as Python app
3. Set environment variables
4. Deploy automatically

---

## 🔧 Environment Configuration

### Required Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@host/dbname

# Security
SECRET_KEY=your-super-secret-key

# AI
OPENAI_API_KEY=your-openai-api-key

# Optional
REDIS_URL=redis://localhost:6379
```

### Frontend Configuration
The frontend needs to point to your backend API. Update the API client:

```typescript
// client/src/api/client.ts
const baseURL = 'https://your-backend-url.com'
```

---

## 🌐 Connecting Frontend & Backend

### Update Frontend API URL
```typescript
// client/src/api/client.ts
const baseURL = process.env.NODE_ENV === 'production' 
  ? 'https://your-backend-domain.com' 
  : 'http://localhost:8000'
```

### CORS Configuration
In your backend `.env`:
```bash
ALLOWED_ORIGINS=https://yad4o.github.io/srs-frontend,https://your-custom-domain.com
```

---

## 🔄 CI/CD Pipeline

### Frontend (GitHub Pages)
- ✅ Auto-deploy on main branch push
- ✅ No configuration needed
- ✅ Free hosting

### Backend (GitHub Actions)
- 🔄 Docker-based deployment
- 🔄 Needs server setup
- 🔄 Manual configuration required

---

## 📱 Quick Start Deployment

### 1. Deploy Frontend (5 minutes)
```bash
# Push to main branch - auto-deploys to GitHub Pages
git checkout main
git merge feature/role-based-registration
git push origin main
```

### 2. Deploy Backend (10 minutes)
```bash
# Option A: Railway (easiest)
cd support-resolution-system
railway up

# Option B: Local Docker
docker-compose up -d
```

### 3. Test Integration
```bash
# Test frontend
curl https://yad4o.github.io/srs-frontend/

# Test backend
curl https://your-backend-url.com/health
```

---

## 🔍 Troubleshooting

### Frontend Issues
- **404 Errors**: Check GitHub Pages build logs
- **API Errors**: Verify backend URL and CORS settings
- **Routing**: Ensure Vite base path is correct

### Backend Issues
- **Database**: Check DATABASE_URL format
- **Environment**: Verify all required variables
- **Docker**: Check container logs: `docker-compose logs`

---

## 🎯 Production Checklist

### Security
- [ ] Change default SECRET_KEY
- [ ] Use HTTPS URLs
- [ ] Set up proper CORS
- [ ] Enable rate limiting

### Performance
- [ ] Configure Redis for caching
- [ ] Set up database connection pooling
- [ ] Enable CDN for static assets

### Monitoring
- [ ] Set up health checks
- [ ] Configure error logging
- [ ] Monitor API usage

---

**🚀 Your SRS application is ready for production deployment!**
