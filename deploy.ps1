<#!
.SYNOPSIS
  Скрипт автоматизирует сборку, пуш и деплой бота на удалённый сервер через SSH.

.PARAMETER Repo
  Полное имя репозитория Docker Hub (например: mylogin/versavija-bot)

.PARAMETER Tag
  Тег образа (по умолчанию latest)

.PARAMETER BotToken
  Токен Telegram бота (если не передан – запрос интерактивно / скрыто)

.PARAMETER AdminIds
  Список ID админов (через запятую)

.PARAMETER RemoteUser
  Пользователь SSH (default: admin)

.PARAMETER RemoteHost
  Хост / IP сервера

.PARAMETER RemoteDir
  Директория на сервере для деплоя

Пример:
  ./deploy.ps1 -Repo mylogin/versavija-bot -RemoteHost 176.108.245.116 -BotToken '123:ABC' -AdminIds '5607311019,669501992'
!#>
param(
  [Parameter(Mandatory=$true)] [string]$Repo,
  [string]$Tag = 'latest',
  [string]$BotToken,
  [string]$AdminIds = '5607311019,669501992',
  [string]$RemoteUser = 'admin',
  [Parameter(Mandatory=$true)] [string]$RemoteHost,
  [string]$RemoteDir = '~/versavija-bot'
)

if (-not $BotToken) {
  # Try to read from .env file first
  if (Test-Path '.env') {
    $envContent = Get-Content '.env' -Raw
    if ($envContent -match 'BOT_TOKEN=(.+)') {
      $BotToken = $matches[1].Trim()
      Write-Host "Токен найден в .env файле" -ForegroundColor Green
    }
  }
  
  # If still not found, ask interactively
  if (-not $BotToken) {
    $BotToken = Read-Host -AsSecureString -Prompt 'Введите BOT_TOKEN';
    $BotToken = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($BotToken))
  }
}

$Image = [string]::Format('{0}:{1}', $Repo, $Tag)
Write-Host "[1/8] Сборка образа $Image" -ForegroundColor Cyan
docker build -t $Image . || throw 'Сборка не удалась'

Write-Host "[2/8] Docker login (если требуется)" -ForegroundColor Cyan
try { docker login } catch { Write-Host 'Login пропущен (ошибка / отменено)'; }

Write-Host "[3/8] Push $Image" -ForegroundColor Cyan
docker push $Image || throw 'Push не удался'

Write-Host "[4/8] Подготовка временных файлов" -ForegroundColor Cyan
$envContent = @(
  "BOT_TOKEN=$BotToken",
  "ADMIN_IDS=$AdminIds",
  "DOCKER_HUB_IMAGE=$Image"
) -join "`n"
$tmpEnv = Join-Path $env:TEMP "versavija.env"
Set-Content -Path $tmpEnv -Value $envContent -Encoding UTF8 -NoNewline

Write-Host "[5/8] Копирование docker-compose.yml и .env на сервер" -ForegroundColor Cyan
$sshTarget = [string]::Format('{0}@{1}', $RemoteUser, $RemoteHost)
ssh $sshTarget "mkdir -p $RemoteDir" || throw 'Не удалось создать директорию'
$composeDest = [string]::Format('{0}:{1}/docker-compose.yml', $sshTarget, $RemoteDir)
scp docker-compose.yml $composeDest || throw 'Не удалось скопировать docker-compose.yml'
$envDest = [string]::Format('{0}:{1}/.env', $sshTarget, $RemoteDir)
scp $tmpEnv $envDest || throw 'Не удалось скопировать .env'

Write-Host "[6/8] Запуск / обновление compose на сервере" -ForegroundColor Cyan
ssh $RemoteUser@$RemoteHost "cd $RemoteDir && docker pull $Image && docker-compose up -d"

Write-Host "[7/8] Проверка логов (10 строк)" -ForegroundColor Cyan
ssh $RemoteUser@$RemoteHost "docker logs --tail 10 versavija-bot 2>/dev/null || true"

Write-Host "[8/8] Готово" -ForegroundColor Green

Remove-Item $tmpEnv -ErrorAction SilentlyContinue