# Start the Cifra backend (FastAPI/uvicorn) and frontend (Vite) together with
# one command, for local development. Not a replacement for real packaging
# (see AGENTS.md's Phase 2 plan) -- just removes the "two terminals" step
# from the manual dev workflow documented in README.md.
#
# Usage: powershell -File scripts/dev.ps1 [-BackendPort 8000] [-FrontendPort 5173]

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Starting backend on http://localhost:$BackendPort ..."
$backend = Start-Process -PassThru -NoNewWindow -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "text_as_data.app:app", "--port", "$BackendPort"

Write-Host "Starting frontend on http://localhost:$FrontendPort ..."
$frontend = Start-Process -PassThru -NoNewWindow -FilePath "npm" `
    -ArgumentList "run", "dev", "--", "--port", "$FrontendPort", "--strictPort" `
    -WorkingDirectory (Join-Path $repoRoot "frontend")

Write-Host ""
Write-Host "Cifra is starting up:"
Write-Host "  Backend:  http://localhost:$BackendPort"
Write-Host "  Frontend: http://localhost:$FrontendPort"
Write-Host ""
Write-Host "Press Ctrl+C to stop both."

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Write-Host ""
    Write-Host "Stopping Cifra..."
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
}
