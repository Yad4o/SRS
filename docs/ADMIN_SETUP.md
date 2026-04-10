# Admin Account Setup Guide

## Overview

Complete guide for configuring and managing admin accounts in the SRS system.

---

## Default Admin Account

The system includes a pre-configured admin account:

| Field | Value | Action Required |
|--------|--------|-----------------|
| **Email** | `admin@example.com` | Change immediately |
| **Password** | `admin123` | Change immediately |
| **Role** | `admin` | Correct |
| **User ID** | `2` | Reference |

---

## Security Actions Required

### 1. Change Default Password
```bash
# Login to get token
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'

# Use token to update password (via frontend or API)
```

### 2. Update Email Address
Change from `admin@example.com` to your actual admin email.

### 3. Use Strong Password
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character

---

## Access Methods

### Method 1: API Login
```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'
```

### Method 2: Frontend Login
1. Navigate to frontend application
2. Click "Login" 
3. Enter credentials:
   - Email: `admin@example.com`
   - Password: `admin123`
4. Click "Sign In"

### Method 3: Admin Endpoints
Once authenticated, access admin-only endpoints:

```bash
# Get system metrics
curl -X GET "http://127.0.0.1:8000/admin/metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List all tickets (admin view)
curl -X GET "http://127.0.0.1:8000/admin/tickets" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Admin Privileges

| Feature | Description | Access Level |
|----------|-------------|--------------|
| **View All Tickets** | See tickets from all users | Admin Only |
| **System Metrics** | Access statistics and analytics | Admin Only |
| **Ticket Assignment** | Assign escalated tickets to agents | Admin Only |
| **Ticket Closure** | Close escalated tickets | Admin Only |
| **Feedback Management** | View all ticket feedback | Admin Only |
| **Admin Endpoints** | Access admin-only API routes | Admin Only |

---

## User Role Hierarchy

| Role | Purpose | Permissions |
|-------|----------|--------------|
| **`user`** | Regular customers | Create/view own tickets, submit feedback |
| **`agent`** | Support agents | All user privileges + assign/close escalated tickets |
| **`admin`** | System administrators | Full system access |

---

## Creating Additional Admins

### Option A: Database Script
```python
from app.db.session import SessionLocal, init_db
from app.models.user import User
from app.core.security import hash_password

def create_admin():
    db = SessionLocal()
    admin = User(
        email="new-admin@example.com",
        hashed_password=hash_password("secure_password"),
        role="admin"
    )
    db.add(admin)
    db.commit()
    print("Admin created successfully!")

create_admin()
```

### Option B: Direct SQL
```sql
INSERT INTO users (email, hashed_password, role) 
VALUES ('new-admin@example.com', '$2b$12$...', 'admin');
```

### Option C: API Registration
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@company.com",
    "password": "SecureAdmin123!",
    "role": "admin"
  }'
```

---

## Verification Checklist

### Initial Setup Verification
- [ ] Login with default credentials
- [ ] Receive JWT token
- [ ] Access admin-only endpoints
- [ ] View system metrics
- [ ] List all tickets

### Security Verification
- [ ] Change default password
- [ ] Update email address
- [ ] Test new credentials
- [ ] Verify role permissions

### Functionality Verification
- [ ] Create test tickets as regular user
- [ ] View tickets as admin
- [ ] Assign tickets to agents
- [ ] Close escalated tickets
- [ ] View feedback reports

---

## Ongoing Administration

### Daily Tasks
- Monitor system metrics
- Review escalated tickets
- Check agent performance

### Weekly Tasks
- Review user feedback
- Update agent assignments
- System health checks

### Monthly Tasks
- Security audit
- Performance review
- Backup verification

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|--------|--------|----------|
| **Login Failed** | Wrong password | Reset password via database |
| **403 Forbidden** | Insufficient permissions | Verify user role is 'admin' |
| **Token Expired** | JWT timeout | Login again for new token |
| **Missing Endpoints** | Wrong URL | Verify API base URL |

### Recovery Commands
```bash
# Check user role
curl -X GET "http://127.0.0.1:8000/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test admin access
curl -X GET "http://127.0.0.1:8000/admin/metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Support

For additional admin setup assistance:
1. Check [Technical Specification](../specification/TECHNICAL_SPEC.md)
2. Review [Role Registration Guide](./ROLE_REGISTRATION_GUIDE.md)
3. Consult API documentation for endpoint details

---

**Your admin account is ready to use!**
