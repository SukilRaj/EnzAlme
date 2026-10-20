param([switch]$Restart)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$python = Join-Path $taskRoot '.venv-1\Scripts\python.exe'
$logs = Join-Path $taskRoot 'outputs\runtime'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python environment is missing. Install backend/requirements-neural.txt in .venv-1 first.' }
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'frontend\dist\index.html'))) {
    Push-Location (Join-Path $taskRoot 'frontend')
    try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' } } finally { Pop-Location }
}
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 } catch {
    $ollamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path -LiteralPath $ollamaExe) {
        Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden -WorkingDirectory $taskRoot -RedirectStandardOutput (Join-Path $logs 'ollama.log') -RedirectStandardError (Join-Path $logs 'ollama-error.log') | Out-Null
    } else { Write-Warning 'Ollama executable not found. Neural scoring remains available.' }
}
$listener = Get-NetTCPConnection -State Listen -LocalPort 8001 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener -and $Restart) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    $matchesProject = $process.CommandLine -like "*$taskRoot*" -and $process.CommandLine -match 'uvicorn\s+backend\.app\.(main|neural_main|workspace_app):app'
    if (-not $matchesProject) { throw 'Port 8001 belongs to a process not identified as this project. It was not stopped.' }
    Stop-Process -Id $listener.OwningProcess
    Start-Sleep -Seconds 1
    $listener = $null
}
if (-not $listener) {
    Start-Process -FilePath $python -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8001' -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'backend.log') -RedirectStandardError (Join-Path $logs 'backend-error.log') | Out-Null
}
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8001/api/health' -TimeoutSec 2
        if ($health.version -eq '2.0.0') { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw "Workspace did not become ready. See $logs\backend-error.log" }
Write-Output 'EnzAIme is ready: http://127.0.0.1:8001'
Write-Output "Logs: $logs"
