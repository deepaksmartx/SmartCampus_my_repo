# SmartCampus Auth Testing Guide

## Overview
This guide shows you how to test the authentication endpoints (register, login, and profile).

---

## 🐍 Option 1: Python Test Script (Recommended)

### Run Full Test Suite
```bash
cd backend
python test_auth.py
```

This will:
- Create a new user
- Test login with correct credentials
- Fetch user profile with token
- Test login with invalid credentials (should fail)
- Display all results in a formatted table

**Output Example:**
```
✅ Registration successful: User registered successfully
✅ Login successful!
  Token Type: bearer
  Token (first 50 chars): eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
✅ Profile retrieved successfully!
  ID: 5
  Name: Test User
  Email: test_user_1773673459@example.com
✅ ALL TESTS PASSED! 🎉
```

---

## 🔵 Option 2: PowerShell Quick Test

### Run Quick Test
```powershell
cd backend
.\test_login_quick.ps1
```

This will register, login, and fetch profile in one go.

---

## 📋 Option 3: Manual Testing with cURL/PowerShell

### 1. Register a User
```bash
# Using PowerShell
$body = @{
    name = "John Doe"
    email = "john@example.com"
    password = "Password123!"
    role = "Student"
    phone_number = "1234567890"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/users/register" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"
```

### 2. Login
```bash
# Using PowerShell
$credentials = "username=john@example.com&password=Password123!"

$response = Invoke-RestMethod -Uri "http://localhost:8000/login" `
    -Method POST `
    -Body $credentials `
    -ContentType "application/x-www-form-urlencoded"

$token = $response.access_token
Write-Host "Token: $token"
```

### 3. Get Profile (Requires Token)
```bash
# Using PowerShell
$headers = @{Authorization = "Bearer $token"}

Invoke-RestMethod -Uri "http://localhost:8000/users/profile" `
    -Method GET `
    -Headers $headers
```

---

## 🔍 Test Data

Use these credentials for manual testing:

**Valid User:**
- Email: `test@example.com`
- Password: `password123`

**Invalid Test:**
- Email: `test@example.com`
- Password: `wrongpassword`

---

## 📊 Expected Results

### ✅ Successful Registration
Status: `200 OK`
```json
{
    "message": "User registered successfully"
}
```

### ✅ Successful Login
Status: `200 OK`
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

### ✅ Successful Profile Fetch
Status: `200 OK`
```json
{
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "phone_number": "1234567890",
    "role": "Student",
    "profile_photo": null,
    "created_at": "2026-03-16T15:04:23.006305Z",
    "updated_at": null
}
```

### ❌ Invalid Credentials
Status: `401 Unauthorized`
```json
{
    "detail": "Incorrect email or password"
}
```

### ❌ Invalid Token
Status: `401 Unauthorized`
```json
{
    "detail": "Invalid or expired token"
}
```

---

## 🚀 Quick API Endpoints

| Endpoint | Method | Auth Required | Purpose |
|----------|--------|---------------|---------|
| `/users/register` | POST | ❌ No | Create new user |
| `/login` | POST | ❌ No | Get JWT token |
| `/users/profile` | GET | ✅ Yes | Get logged-in user's profile |
| `/users/{user_id}` | GET | ✅ Yes | Get user profile by ID |
| `/users/email/{email}` | GET | ✅ Yes | Get user profile by email |

---

## 📝 Notes

- Ensure the backend server is running: `python main.py`
- Default port: `http://localhost:8000`
- Check API docs at: `http://localhost:8000/docs`
- All passwords are hashed using SHA256
- JWT tokens expire after 24 hours
