# Development run script (UTF-8 BOM)
# Copies .env.dev to .env and runs the bot

chcp 65001 > $null
setx PYTHONUTF8 1 | Out-Null
setx PYTHONIOENCODING utf-8 | Out-Null

Copy-Item ".env.dev" ".env" -Force
Write-Host "Switched to development environment" -ForegroundColor Green
Write-Host "Bot Token: 7815199281:AAHI..." -ForegroundColor Yellow
Write-Host "Starting development bot..." -ForegroundColor Cyan
python run.py