# Role-Based Registration Guide

## 🎯 Overview

Complete guide for role-based user registration in the SRS system. Users can register with different roles instead of automatically defaulting to "user".

> **📖 For frontend implementation details, see [FRONTEND_ROLE_GUIDE.md](./FRONTEND_ROLE_GUIDE.md)**

---

## 📋 Available Roles

| Role | Icon | Description | Permissions |
|------|------|-------------|--------------|
| **user** | 👤 | Regular customers | Create/view own tickets, submit feedback |
| **agent** | 🎧 | Support agents | All user privileges + assign/close escalated tickets |
| **admin** | 👑 | System administrators | Full system access |

---

## 🚀 API Registration Examples

### Register as Regular User (Default)
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "CustomerPass123!"
  }'
```

### Register as Agent
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "agent@example.com", 
    "password": "AgentPass123!",
    "role": "agent"
  }'
```

### Register as Admin
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "AdminPass123!", 
    "role": "admin"
  }'
```

---

## ✅ Validation & Security

### Role Validation
- Only allowed roles: `user`, `agent`, `admin`
- Invalid roles are rejected with clear error messages
- Default role is `user` if not specified

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter  
- At least one digit
- At least one special character

### Email Validation
- Valid email format required
- Emails normalized to lowercase
- Duplicate emails rejected

---

## 🧪 Testing

### Test Agent Registration
```python
import requests

# Register agent
agent_data = {
    'email': 'agent@example.com',
    'password': 'AgentPass123!',
    'role': 'agent'
}

response = requests.post('http://127.0.0.1:8000/auth/register', json=agent_data)
print(f"Status: {response.status_code}")
print(f"Result: {response.json()}")
```

### Test Agent Privileges
```python
# Login as agent
login_data = {'email': 'agent@example.com', 'password': 'AgentPass123!'}
response = requests.post('http://127.0.0.1:8000/auth/login', json=login_data)

if response.status_code == 200:
    token = response.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    
    # Test agent-only endpoint
    assign_response = requests.post('http://127.0.0.1:8000/tickets/1/assign', headers=headers)
    print(f"Can assign tickets: {assign_response.status_code != 403}")
```

---

## 🔧 Implementation Details

### Schema Changes
- `UserCreate` schema includes optional `role` field
- Role validation ensures only allowed roles are accepted
- Default role fallback to "user" for backward compatibility

### API Changes
- Registration endpoint accepts role in request body
- Role is validated against `ALLOWED_ROLES` configuration
- Maintains backward compatibility

### Database Impact
- No database schema changes needed
- Role field already existed in users table
- Simply uses role from request instead of hardcoded default

---

## 📝 Example Responses

### Successful Registration
```json
{
  "id": 5,
  "email": "agent@example.com", 
  "role": "agent"
}
```

### Invalid Role Error
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "status_code": 400,
    "details": {
      "validation_errors": [
        {
          "field": "body.role",
          "message": "Value error, Role must be one of: agent, admin, user",
          "type": "value_error"
        }
      ]
    }
  }
}
```

---

## 🔄 Backward Compatibility

✅ **Fully Backward Compatible**
- Existing registration code continues to work
- Default role is still "user" when role not specified
- No breaking changes to existing API

---

## 🎯 Use Cases

### Customer Support Team Setup
```bash
# Register multiple agents
for agent in agent1@company.com agent2@company.com; do
  curl -X POST "http://127.0.0.1:8000/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$agent\",\"password\":\"AgentPass123!\",\"role\":\"agent\"}"
done
```

### System Administrator Setup
```bash
# Register admin during initial setup
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@company.com","password":"SecureAdmin123!","role":"admin"}'
```

---

## 🔗 Related Documentation

- **[FRONTEND_ROLE_GUIDE.md](./FRONTEND_ROLE_GUIDE.md)** - Frontend implementation details
- **[ADMIN_SETUP.md](./ADMIN_SETUP.md)** - Admin account configuration
- **[../specification/TECHNICAL_SPEC.md](../specification/TECHNICAL_SPEC.md)** - Complete API documentation

---

**🎉 Role-based registration is now live and ready to use!**
