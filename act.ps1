# act.ps1
$VenvPath = ".venv\Scripts\Activate.ps1"

if (-Not (Test-Path $VenvPath)) {
    Write-Host "❌ Virtual environment not found."
    Write-Host "👉 Run: python -m venv .venv"
    exit 1
}

& $VenvPath
Write-Host "✅ Virtual environment activated"