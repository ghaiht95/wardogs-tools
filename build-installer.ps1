$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $isccPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $isccPath) {
        throw 'Inno Setup 6 is required to compile WarDogsTools.iss. Install Inno Setup, then run this script again.'
    }
    $iscc = @{ Source = $isccPath }
}

$runningApps = Get-CimInstance Win32_Process -Filter "Name='WarDogsTools.exe'" |
    Where-Object { $_.ExecutablePath -eq "$PSScriptRoot\dist\WarDogsTools\WarDogsTools.exe" }
if ($runningApps) {
    $pids = ($runningApps | ForEach-Object { $_.ProcessId }) -join ', '
    throw "Close WarDogs Tools (PID $pids) before rebuilding the application."
}

& "$PSScriptRoot\build-release.ps1"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $iscc.Source "$PSScriptRoot\WarDogsTools.iss"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Installer: $PSScriptRoot\dist\WarDogsTools-Setup.exe"
