# Frontend Role Selection Implementation Guide

## 🎯 Overview

Your frontend needs to be updated to support role selection during user registration. Currently, users can only register as regular "users" because there's no role selection option in the frontend.

## 📋 What Needs to Be Done

### 1. **Update Registration Form**
- Add role selection dropdown/cards
- Show role descriptions to help users choose
- Only show role selection during registration (not login)

### 2. **Update API Calls**
- Include role in registration requests
- Keep login requests unchanged (no role needed)

### 3. **User Experience**
- Clear role descriptions
- Visual role indicators (icons/colors)
- Help users understand the differences

## 🚀 Implementation Examples

### React Implementation

#### Basic Registration Form
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
    
    // Include role in registration request
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
      <input
        name="email"
        type="email"
        value={formData.email}
        onChange={(e) => setFormData(prev => ({...prev, email: e.target.value}))}
        placeholder="Email"
        required
      />
      
      <input
        name="password"
        type="password"
        value={formData.password}
        onChange={(e) => setFormData(prev => ({...prev, password: e.target.value}))}
        placeholder="Password"
        required
      />
      
      {/* NEW: Role Selection */}
      <select
        name="role"
        value={formData.role}
        onChange={(e) => setFormData(prev => ({...prev, role: e.target.value}))}
      >
        <option value="user">👤 Customer</option>
        <option value="agent">🎧 Support Agent</option>
        <option value="admin">👑 Administrator</option>
      </select>
      
      <button type="submit">Register</button>
    </form>
  );
}
```

#### Enhanced Role Cards
```jsx
export function RoleSelector({ selectedRole, onRoleChange }) {
  const roles = [
    {
      value: 'user',
      title: 'Customer',
      description: 'Get help with your support tickets',
      icon: '👤',
      color: '#3b82f6'
    },
    {
      value: 'agent',
      title: 'Support Agent',
      description: 'Help customers resolve their issues',
      icon: '🎧',
      color: '#10b981'
    },
    {
      value: 'admin',
      title: 'Administrator',
      description: 'Manage the entire support system',
      icon: '👑',
      color: '#8b5cf6'
    }
  ];

  return (
    <div className="role-selector">
      <h3>Choose Your Account Type</h3>
      <div className="role-grid">
        {roles.map(role => (
          <div
            key={role.value}
            className={`role-card ${selectedRole === role.value ? 'selected' : ''}`}
            onClick={() => onRoleChange(role.value)}
            style={{ borderColor: selectedRole === role.value ? role.color : '#e5e7eb' }}
          >
            <div className="role-icon">{role.icon}</div>
            <h4>{role.title}</h4>
            <p>{role.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Vue.js Implementation

#### Registration Component
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

### API Integration

#### Auth Service
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

#### React Hook Example
```javascript
// useAuth.js
import { useState } from 'react';
import authService from './authService';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);

  const login = async (credentials) => {
    setLoading(true);
    try {
      const result = await authService.login(credentials);
      setUser(result.user);
      localStorage.setItem('token', result.access_token);
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const register = async (userData) => {
    setLoading(true);
    try {
      const result = await authService.register(userData);
      setUser(result.user);
      localStorage.setItem('token', result.access_token);
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  };

  return { user, login, register, loading };
}
```

## 🎨 UI/UX Best Practices

### 1. **Clear Role Descriptions**
```jsx
const roleDescriptions = {
  user: "I'm a customer who needs help with support tickets",
  agent: "I'm a support agent who helps resolve customer issues", 
  admin: "I'm an administrator who manages the support system"
};
```

### 2. **Visual Indicators**
- Use icons: 👤 user, 🎧 agent, 👑 admin
- Use colors: blue for user, green for agent, purple for admin
- Show selected state clearly

### 3. **Progressive Disclosure**
- Start with simple registration
- Explain roles when user selects them
- Don't overwhelm new users

### 4. **Mobile-Friendly**
- Use large touch targets
- Clear typography
- Responsive layout

## 📱 Mobile Component Example

```jsx
export function MobileRoleSelector() {
  const [selectedRole, setSelectedRole] = useState('user');
  
  return (
    <div className="mobile-role-selector">
      <h3>What type of account do you need?</h3>
      
      <div className="role-options">
        <button
          className={`role-btn ${selectedRole === 'user' ? 'active' : ''}`}
          onClick={() => setSelectedRole('user')}
        >
          <span className="role-emoji">👤</span>
          <div className="role-info">
            <strong>Customer</strong>
            <small>I need help with tickets</small>
          </div>
        </button>
        
        <button
          className={`role-btn ${selectedRole === 'agent' ? 'active' : ''}`}
          onClick={() => setSelectedRole('agent')}
        >
          <span className="role-emoji">🎧</span>
          <div className="role-info">
            <strong>Agent</strong>
            <small>I help customers</small>
          </div>
        </button>
        
        <button
          className={`role-btn ${selectedRole === 'admin' ? 'active' : ''}`}
          onClick={() => setSelectedRole('admin')}
        >
          <span className="role-emoji">👑</span>
          <div className="role-info">
            <strong>Admin</strong>
            <small>I manage the system</small>
          </div>
        </button>
      </div>
    </div>
  );
}
```

## 🧪 Testing

### Test Registration with Different Roles
```javascript
// Test file
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
      // No role specified
    };
    
    const result = await authService.register(userData);
    expect(result.role).toBe('user');
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

You now have everything needed to add role selection to your frontend:

1. ✅ **React examples** - Components and hooks
2. ✅ **Vue.js examples** - Templates and scripts  
3. ✅ **API integration** - Service layer
4. ✅ **UI/UX guidance** - Best practices
5. ✅ **Testing strategies** - How to verify

Pick the framework you're using and follow the examples. Your users will now be able to register with the appropriate role! 🚀
