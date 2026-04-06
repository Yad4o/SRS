# Role-Based Registration Guide

## 🎯 Overview

The SRS system now supports role selection during user registration! Users can register with different roles instead of automatically defaulting to "user".

## 📋 Available Roles

### 👤 **user** (Default)
- **Purpose**: Regular customers
- **Privileges**: 
  - Create tickets
  - View own tickets only
  - Submit feedback on resolved tickets

### 🎧 **agent** 
- **Purpose**: Support agents
- **Privileges**:
  - All user privileges
  - Assign escalated tickets to themselves
  - Close escalated tickets
  - View all tickets (not just their own)

### 👑 **admin**
- **Purpose**: System administrators  
- **Privileges**:
  - All agent privileges
  - Access system metrics and statistics
  - Admin-only endpoints
  - Full system access

## 🚀 How to Register with Different Roles

### Method 1: API Registration

#### Register as Regular User (Default)
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "CustomerPass123!"
  }'
```

#### Register as Agent
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "agent@example.com", 
    "password": "AgentPass123!",
    "role": "agent"
  }'
```

#### Register as Admin
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "AdminPass123!", 
    "role": "admin"
  }'
```

### Method 2: Frontend Registration

Your frontend can now include a role selection field:

```javascript
const registrationData = {
  email: "user@example.com",
  password: "SecurePass123!",
  role: "agent"  // or "user", or "admin"
};

fetch('/auth/register', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(registrationData)
})
.then(response => response.json())
.then(data => console.log('Registered:', data));
```

## ✅ Validation & Security

### Role Validation
- Only allowed roles are accepted: `user`, `agent`, `admin`
- Invalid roles are rejected with clear error messages
- Default role is `user` if not specified

### Password Requirements
All registrations must meet password complexity requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter  
- At least one digit
- At least one special character

### Email Validation
- Valid email format required
- Emails normalized to lowercase
- Duplicate emails rejected

## 🧪 Testing Examples

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

## 🔧 Implementation Details

### Schema Changes
- `UserCreate` schema now includes optional `role` field
- Role validation ensures only allowed roles are accepted
- Default role fallback to "user" for backward compatibility

### API Changes
- Registration endpoint now accepts role in request body
- Role is validated against `ALLOWED_ROLES` configuration
- Maintains backward compatibility - existing code still works

### Database Impact
- No database schema changes needed
- Role field already existed in users table
- Simply using the role from request instead of hardcoded default

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

## 🔄 Backward Compatibility

✅ **Fully Backward Compatible**
- Existing registration code continues to work
- Default role is still "user" when role not specified
- No breaking changes to existing API

## 🎯 Use Cases

### Customer Support Team
```bash
# Register multiple agents
for agent in agent1@company.com agent2@company.com; do
  curl -X POST "http://127.0.0.1:8000/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$agent\",\"password\":\"AgentPass123!\",\"role\":\"agent\"}"
done
```

### System Setup
```bash
# Register admin during initial setup
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@company.com","password":"SecureAdmin123!","role":"admin"}'
```

---

**🎉 Role-based registration is now live and ready to use!**
