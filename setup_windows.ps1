$ErrorActionPreference = "Stop"

$dataDir = $PSScriptRoot
$userDataDir = Join-Path $env:USERPROFILE "BiljartClup"
$passwordFile = Join-Path $userDataDir "coordinator.password"
$secretFile = Join-Path $userDataDir "session.secret"

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "instance") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $userDataDir "Backups") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $userDataDir "Rapporten") | Out-Null

$instanceDir = Join-Path $dataDir "instance"
& icacls $instanceDir /grant "*S-1-5-32-545:(OI)(CI)M" /T /C | Out-Null

if (-not (Test-Path $passwordFile)) {
    $password = -join ((33..126) | Get-Random -Count 16 | ForEach-Object {[char]$_})
    Set-Content -Path $passwordFile -Value $password -Encoding UTF8
    $message = "Coordinator wachtwoord:`n`n$password`n`nBewaar dit wachtwoord."
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, "BiljartClubApp") | Out-Null
}

$currentPassword = (Get-Content -Path $passwordFile -Raw).Trim()
Write-Host ""
Write-Host "Coordinator wachtwoord: $currentPassword" -ForegroundColor Yellow
Write-Host "Opgeslagen in: $passwordFile" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $secretFile)) {
    $secret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
    Set-Content -Path $secretFile -Value $secret -Encoding UTF8
}

Read-Host "Druk op Enter om af te sluiten"