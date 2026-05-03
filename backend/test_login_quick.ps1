# Quick Login Testing Script (PowerShell)
# Usage: .\test_login_quick.ps1

$baseUrl = "http://localhost:8000"

# Generate test credentials
$timestamp = [int](Get-Date -UFormat %s)
$testEmail = "quicktest_$timestamp@example.com"
$testPassword = "TestPass123!"

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         QUICK LOGIN TEST                                  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# Step 1: Register
Write-Host "`n[1/3] Registering user..." -ForegroundColor Yellow
$registerPayload = @{
    name = "Quick Test User"
    email = $testEmail
    password = $testPassword
    role = "Student"
    phone_number = "1234567890"
} | ConvertTo-Json

try {
    $registerResp = Invoke-RestMethod -Uri "$baseUrl/users/register" -Method POST -Body $registerPayload -ContentType "application/json"
    Write-Host "✅ Registration successful: $($registerResp.message)" -ForegroundColor Green
} catch {
    Write-Host "❌ Registration failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Login
Write-Host "`n[2/3] Logging in..." -ForegroundColor Yellow
$loginData = "username=$([System.Net.WebUtility]::UrlEncode($testEmail))&password=$([System.Net.WebUtility]::UrlEncode($testPassword))"

try {
    $loginResp = Invoke-RestMethod -Uri "$baseUrl/login" -Method POST -Body $loginData -ContentType "application/x-www-form-urlencoded"
    $token = $loginResp.access_token
    Write-Host "✅ Login successful!" -ForegroundColor Green
    Write-Host "   Token: $($token.substring(0, 40))..." -ForegroundColor Gray
} catch {
    Write-Host "❌ Login failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: Get Profile
Write-Host "`n[3/3] Fetching profile..." -ForegroundColor Yellow
$headers = @{Authorization = "Bearer $token"}

try {
    $profileResp = Invoke-RestMethod -Uri "$baseUrl/users/profile" -Method GET -Headers $headers
    Write-Host "✅ Profile retrieved successfully!" -ForegroundColor Green
    Write-Host "   Name:  $($profileResp.name)" -ForegroundColor Gray
    Write-Host "   Email: $($profileResp.email)" -ForegroundColor Gray
    Write-Host "   Role:  $($profileResp.role)" -ForegroundColor Gray
    Write-Host "   Phone: $($profileResp.phone_number)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Profile fetch failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n" 
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ ALL TESTS PASSED!                                     ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
