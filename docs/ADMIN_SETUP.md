# Admin Account Setup Guide

## 🎯 Admin Account Created Successfully!

Your admin account has been created and is working. Here are the details:

### 🔐 Admin Credentials
- **Email**: `admin@example.com`
- **Password**: `admin123`
- **Role**: `admin`
- **User ID**: `2`

### ⚠️ IMPORTANT SECURITY NOTES

1. **Change Default Password**: The password `admin123` is a default. Change it immediately after first login.
2. **Use Secure Password**: Choose a strong password with at least 8 characters.
3. **Update Email**: Change the email from `admin@example.com` to your actual admin email.

## 🚀 How to Use Admin Account

### Method 1: Login via API
```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'
```

### Method 2: Login via Frontend
1. Navigate to your frontend application
2. Click "Login" 
3. Enter credentials:
   - Email: `admin@example.com`
   - Password: `admin123`
4. Click "Sign In"

### Method 3: Use Admin Endpoints
Once logged in, you can access admin-only endpoints:

```bash
# Get system metrics
curl -X GET "http://127.0.0.1:8000/admin/metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List all tickets (admin view)
curl -X GET "http://127.0.0.1:8000/admin/tickets" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🛡️ Admin Privileges

With admin role, you can:
- ✅ View all tickets (not just your own)
- ✅ Access system metrics and statistics
- ✅ Assign escalated tickets to agents
- ✅ Close escalated tickets
- ✅ View feedback for all tickets
- ✅ Access admin-only endpoints

## 🔧 Creating Additional Admin Users

To create more admin users, you can use the same pattern:

### Option A: Database Script
Create a script similar to what was used:
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
    print("Admin created!")
```

### Option B: Direct Database Insert
```sql
INSERT INTO users (email, hashed_password, role) 
VALUES ('new-admin@example.com', '$2b$12$...', 'admin');
```

## 🔍 Verifying Admin Access

To verify your admin account works:

1. **Login Test**: Use the login endpoint
2. **Token Test**: Use the returned JWT token
3. **Endpoint Test**: Access admin-only endpoints
4. **Permission Test**: Confirm admin privileges work

## 📋 Role Hierarchy

The system has three user roles:
- **`user`**: Regular customers, can only see their own tickets
- **`agent`**: Support agents, can assign/close escalated tickets
- **`admin`**: System administrators, full access to all features

## 🔄 Next Steps

1. **Change Password**: Update from default immediately
2. **Update Email**: Set to your actual email
3. **Test Features**: Explore admin endpoints and features
4. **Monitor System**: Check metrics and system health

---

**✅ Your admin account is ready to use!**
