# Frontend Role Selection Implementation Guide

## 🎯 Overview

Guide for implementing role-based registration in frontend applications. Users can register as different roles instead of defaulting to "user".

## 📋 Available Roles

| Role | Icon | Description | Permissions |
|------|------|-------------|--------------|
| **user** | 👤 | Regular customers | Create/view own tickets, submit feedback |
| **agent** | 🎧 | Support agents | All user privileges + assign/close escalated tickets |
| **admin** | 👑 | System administrators | Full system access |

## 🚀 Quick Implementation

### React Example

```jsx
import React, { useState } from 'react';

export function RegisterForm() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'user' // Default role
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const response = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData) // Includes role!
    });
    
    const result = await response.json();
    console.log('Registered:', result);
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="email" type="email" value={formData.email} 
             onChange={(e) => setFormData(prev => ({...prev, email: e.target.value}))} 
             placeholder="Email" required />
      
      <input name="password" type="password" value={formData.password} 
             onChange={(e) => setFormData(prev => ({...prev, password: e.target.value}))} 
             placeholder="Password" required />
      
      <select name="role" value={formData.role} 
              onChange={(e) => setFormData(prev => ({...prev, role: e.target.value}))}>
        <option value="user">👤 Customer</option>
        <option value="agent">🎧 Support Agent</option>
        <option value="admin">👑 Administrator</option>
      </select>
      
      <button type="submit">Register</button>
    </form>
  );
}
```

### Vue.js Example

```vue
<template>
  <div class="register-form">
    <form @submit.prevent="handleSubmit">
      <input v-model="form.email" type="email" placeholder="Email" required />
      <input v-model="form.password" type="password" placeholder="Password" required />
      
      <!-- Role Selection -->
      <select v-model="form.role" required>
        <option value="user">👤 Customer</option>
        <option value="agent">🎧 Support Agent</option>
        <option value="admin">👑 Administrator</option>
      </select>
      
      <button type="submit" :disabled="loading">Register</button>
    </form>
  </div>
</template>

<script>
export default {
  data() {
    return {
      loading: false,
      form: {
        email: '',
        password: '',
        role: 'user' // Default role
      }
    }
  },
  methods: {
    async handleSubmit() {
      this.loading = true;
      
      try {
        // Include role in registration request
        const response = await fetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.form) // Includes role!
        });
        
        const result = await response.json();
        console.log('Registered:', result);
        
        // Redirect or show success
      } catch (error) {
        console.error('Registration failed:', error);
      } finally {
        this.loading = false;
      }
    }
  }
}
</script>
```

## 🔧 API Integration

### Auth Service

```javascript
// authService.js
class AuthService {
  async login(credentials) {
    // Login - NO role needed
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: credentials.email,
        password: credentials.password
        // No role field for login
      })
    });
    return response.json();
  }

  async register(userData) {
    // Registration - INCLUDE role
    const response = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: userData.email,
        password: userData.password,
        role: userData.role // This is the key addition!
      })
    });
    return response.json();
  }
}

export default new AuthService();
```

## 🎨 UI Best Practices

### Visual Design
- **Icons**: 👤 user, 🎧 agent, 👑 admin
- **Colors**: Blue (user), Green (agent), Purple (admin)
- **Typography**: Clear role descriptions, avoid technical jargon
- **Layout**: Responsive design, mobile-friendly touch targets

### User Experience
- **Progressive Disclosure**: Start simple, explain roles on selection
- **Clear Feedback**: Show selected state, loading states
- **Error Handling**: Validate roles before submission
- **Accessibility**: Proper labels, keyboard navigation

### Mobile Optimization

```jsx
export function MobileRoleSelector() {
  const [selectedRole, setSelectedRole] = useState('user');
  
  return (
    <div className="mobile-role-selector">
      <h3>Choose your account type</h3>
      
      <div className="role-options">
        {[/* ... */].map(role => (
          <button
            key={role.value}
            className={`role-btn ${selectedRole === role.value ? 'active' : ''}`}
            onClick={() => setSelectedRole(role.value)}
          >
            <span className="role-emoji">{role.icon}</span>
            <div className="role-info">
              <strong>{role.title}</strong>
              <small>{role.desc}</small>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

## 🧪 Testing

### Unit Tests

```javascript
describe('Role Registration', () => {
  test('should register as agent', async () => {
    const userData = {
      email: 'agent@test.com',
      password: 'AgentPass123!',
      role: 'agent'
    };
    
    const result = await authService.register(userData);
    expect(result.role).toBe('agent');
  });

  test('should default to user role', async () => {
    const userData = {
      email: 'user@test.com',
      password: 'UserPass123!'
    };
    
    const result = await authService.register(userData);
    expect(result.role).toBe('user');
  });
});
```

### Integration Tests

```javascript
// Test role-based permissions after login
describe('Role Permissions', () => {
  test('agent can access agent endpoints', async () => {
    const agent = await loginAsAgent();
    const response = await fetch('/tickets/assign', {
      headers: { 'Authorization': `Bearer ${agent.token}` }
    });
    expect(response.status).not.toBe(403);
  });
});
```

## 🔄 Migration Steps

### 1. **Update Registration Form**
- Add role selection component
- Update form state to include role
- Add role validation

### 2. **Update API Integration**
- Include role in registration requests
- Keep login requests unchanged
- Handle role-specific UI after login

### 3. **Test Thoroughly**
- Test all role combinations
- Verify role-based permissions
- Test error handling

### 4. **Deploy Gradually**
- Start with role selection in registration
- Add role-based UI features
- Monitor for issues

## 🚨 Common Pitfalls

### 1. **Including Role in Login**
```javascript
// ❌ WRONG - Don't send role in login
const loginData = { email, password, role }; // Wrong!

// ✅ CORRECT - Login only needs email/password
const loginData = { email, password }; // Correct!
```

### 2. **Not Validating Role**
```javascript
// ❌ WRONG - Any role could be sent
const role = formData.role; // Could be anything!

// ✅ CORRECT - Validate role before sending
const validRoles = ['user', 'agent', 'admin'];
if (!validRoles.includes(formData.role)) {
  throw new Error('Invalid role');
}
```

### 3. **Poor UX**
- Don't show technical role names
- Explain what each role can do
- Use clear visual indicators

---

## 🎯 Ready to Implement!

You have everything needed:

1. ✅ **React & Vue examples** - Complete components
2. ✅ **API integration** - Service layer patterns
3. ✅ **UI/UX guidance** - Best practices
4. ✅ **Testing strategies** - How to verify

Start implementing and your users will be able to register with appropriate roles! 🚀
