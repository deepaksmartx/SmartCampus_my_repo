"""
Test script for authentication endpoints (register, login, profile)
Run this script to test the login/register/profile functionality
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = f"test_user_{int(datetime.now().timestamp())}@example.com"
TEST_PASSWORD = "TestPassword123!"
TEST_NAME = "Test User"
TEST_PHONE = "9876543210"

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")

def test_register():
    """Test user registration"""
    print_header("TEST 1: REGISTER NEW USER")
    
    payload = {
        "name": TEST_NAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "role": "Student",
        "phone_number": TEST_PHONE
    }
    
    print_info(f"Registering user with email: {TEST_EMAIL}")
    
    try:
        response = requests.post(f"{BASE_URL}/users/register", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Registration successful: {data.get('message')}")
            return True
        else:
            print_error(f"Registration failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Could not connect to server. Is it running on http://localhost:8000?")
        return False
    except Exception as e:
        print_error(f"Error during registration: {str(e)}")
        return False

def test_login():
    """Test user login"""
    print_header("TEST 2: LOGIN USER")
    
    print_info(f"Attempting login with email: {TEST_EMAIL}")
    
    try:
        # Using form data as per OAuth2PasswordRequestForm
        data = {
            "username": TEST_EMAIL,  # OAuth2 uses 'username' field for email
            "password": TEST_PASSWORD
        }
        
        response = requests.post(f"{BASE_URL}/login", data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get("access_token")
            token_type = token_data.get("token_type")
            
            print_success(f"Login successful!")
            print(f"  Token Type: {token_type}")
            print(f"  Token (first 50 chars): {token[:50]}...")
            
            return token
        else:
            print_error(f"Login failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Error during login: {str(e)}")
        return None

def test_profile(token):
    """Test getting user profile"""
    print_header("TEST 3: GET USER PROFILE")
    
    print_info("Fetching user profile with token...")
    
    try:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(f"{BASE_URL}/users/profile", headers=headers)
        
        if response.status_code == 200:
            profile = response.json()
            print_success("Profile retrieved successfully!")
            print(f"\n  Profile Details:")
            print(f"    ID: {profile.get('id')}")
            print(f"    Name: {profile.get('name')}")
            print(f"    Email: {profile.get('email')}")
            print(f"    Phone: {profile.get('phone_number')}")
            print(f"    Role: {profile.get('role')}")
            print(f"    Created: {profile.get('created_at')}")
            
            return True
        else:
            print_error(f"Profile fetch failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error fetching profile: {str(e)}")
        return False

def test_invalid_login():
    """Test login with invalid credentials"""
    print_header("TEST 4: LOGIN WITH INVALID CREDENTIALS (Should Fail)")
    
    print_info("Attempting login with wrong password...")
    
    try:
        data = {
            "username": TEST_EMAIL,
            "password": "WrongPassword123!"  # Wrong password
        }
        
        response = requests.post(f"{BASE_URL}/login", data=data)
        
        if response.status_code == 401:
            print_success("Correctly rejected invalid credentials (401 Unauthorized)")
            error_detail = response.json().get("detail", "Unknown error")
            print_info(f"Error message: {error_detail}")
            return True
        else:
            print_error(f"Expected 401 status, got {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error during invalid login test: {str(e)}")
        return False

def run_all_tests():
    """Run all tests in sequence"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "SMARTCAMPUS AUTH TEST SUITE" + " "*15 + "║")
    print("╚" + "="*58 + "╝")
    
    results = {}
    
    # Test 1: Register
    results["Register"] = test_register()
    
    if not results["Register"]:
        print_error("Cannot proceed without successful registration")
        return
    
    # Test 2: Login
    token = test_login()
    results["Login"] = token is not None
    
    if not token:
        print_error("Cannot proceed without successful login")
        return
    
    # Test 3: Profile
    results["Profile"] = test_profile(token)
    
    # Test 4: Invalid Login
    results["Invalid Login"] = test_invalid_login()
    
    # Summary
    print_header("TEST SUMMARY")
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print("\n")
    if all_passed:
        print_success("ALL TESTS PASSED! 🎉")
    else:
        print_error("SOME TESTS FAILED")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    run_all_tests()
