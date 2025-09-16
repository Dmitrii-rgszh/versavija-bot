# Production environment script
# Restores production .env

$prodToken = "8347910187:AAH6AKCN7EP5DgO_6ZMPglzMD5Q"
$adminIds = "5607311019,669501992"

@"
BOT_TOKEN=$prodToken
ADMIN_IDS=$adminIds
"@ | Set-Content ".env" -Encoding UTF8

Write-Host "Switched to production environment" -ForegroundColor Green
Write-Host "Bot Token: 8347910187:AAH6..." -ForegroundColor Yellow