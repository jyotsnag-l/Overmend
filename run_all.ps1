$projectRoot = "C:\Users\sreej\OneDrive\Desktop\agent_sdk"
$python = "$projectRoot\venv\Scripts\python.exe"

# Build frontend for production
Write-Host "Building frontend..."
Push-Location "$projectRoot\frontend"
npm run build
Pop-Location
Write-Host "Frontend build complete."

# Set environment port
$port = $env:PORT
if (-not $port) {
    $port = "8000"
}

# Kill any existing process on this port to prevent binding errors
Write-Host "Stopping any existing process on port $port..."
$existingProcess = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existingProcess) {
    Stop-Process -Id $existingProcess.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Configure PYTHONPATH so python/uvicorn/celery can resolve all modules
$workerPythonPath = "$projectRoot\apps\recovery-worker;$projectRoot\apps\api;$projectRoot\packages\shared;$projectRoot\packages\core;$projectRoot\packages\fault-localizer;$projectRoot\packages\patch-engine;$projectRoot\packages\sandbox-manager;$projectRoot\packages\trust-engine-core;$projectRoot\packages\github-client"
$env:PYTHONPATH = "$projectRoot;$projectRoot\apps\api;$projectRoot\packages\shared;$workerPythonPath"

# Launch Celery Worker in a separate window
Write-Host "Launching Celery recovery worker..."
Start-Process -FilePath $python -ArgumentList "-m celery -A tasks worker --loglevel=info -P solo" -WorkingDirectory "$projectRoot\apps\recovery-worker" -Environment @{ PYTHONPATH = $workerPythonPath }

# Launch FastAPI backend in a separate window
Write-Host "Launching unified server on port $port..."
Start-Process -FilePath $python -ArgumentList "-m uvicorn apps.api.main:app --reload --port $port" -WorkingDirectory $projectRoot

Write-Host "Backend, frontend, and Celery recovery worker are running."
