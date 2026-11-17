$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

& "$PSScriptRoot\.venv\Scripts\python.exe" -m PyInstaller --noconfirm "$PSScriptRoot\WarDogsTools.spec"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Copy-Item "$PSScriptRoot\DISTRIBUTION.txt" "$PSScriptRoot\dist\WarDogsTools\DISTRIBUTION.txt"
Copy-Item "$PSScriptRoot\LICENSE" "$PSScriptRoot\dist\WarDogsTools\LICENSE"
Write-Host "Application folder: $PSScriptRoot\dist\WarDogsTools"
