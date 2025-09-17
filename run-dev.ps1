# Development run script
# Copies .env.dev to .env and runs the bot

Copy-Item ".env.dev" ".env" -Force
Write-Host "Switched to development environment" -ForegroundColor Green
Write-Host "Bot Token: 7815199281:AAHI..." -ForegroundColor Yellow
Write-Host "Starting development bot..." -ForegroundColor Cyan
python run.py