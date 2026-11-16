$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$composeDir = if (Test-Path (Join-Path $PSScriptRoot 'docker-compose.yml')) { $PSScriptRoot } else { Split-Path $PSScriptRoot -Parent }
try {
    if (!(Test-Path $python)) { throw 'Python environment not found. Create .venv first.' }
    & $python -c 'import fastapi, uvicorn, psycopg, neo4j, sentence_transformers, ipykernel' 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installing Python packages (first run may take a while)...'
        & $python -m pip install -r requirements-local.txt
        if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
    }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        $dockerApp = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
        if (!(Test-Path $dockerApp)) { throw 'Docker Desktop not found.' }
        Write-Host 'Starting Docker Desktop...'
        Start-Process -FilePath $dockerApp -WindowStyle Hidden
        $ready = $false
        for ($i = 0; $i -lt 90; $i++) {
            Start-Sleep -Seconds 2
            docker info *> $null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        }
        if (!$ready) { throw 'Docker did not start. Open Docker Desktop and try again.' }
    }
    docker compose --project-directory $composeDir -f (Join-Path $composeDir 'docker-compose.yml') up -d db
    if ($LASTEXITCODE -ne 0) { throw 'Could not start PostgreSQL.' }
    $dbReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        docker compose --project-directory $composeDir -f (Join-Path $composeDir 'docker-compose.yml') exec -T db pg_isready -U cn230lci -d cn230lci *> $null
        if ($LASTEXITCODE -eq 0) { $dbReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if (!$dbReady) { throw 'PostgreSQL did not become ready.' }
    try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null }
    catch {
        $ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
        if (!(Test-Path $ollama)) { throw 'Ollama app not found.' }
        Start-Process -FilePath $ollama -WindowStyle Hidden
        $ready = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 2
            try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null; $ready = $true; break } catch {}
        }
        if (!$ready) { throw 'Ollama did not start.' }
    }
    $models = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
    if ('gemma4:e2b' -notin $models.models.name) { throw 'Ollama model gemma4:e2b not found.' }
    if (!(Test-Path '.\local_lci_index.npz')) {
        Write-Host 'Creating local search index. First run may take a long time...'
        & $python -c 'from local_demo import build_index; build_index()'
        if ($LASTEXITCODE -ne 0 -or !(Test-Path '.\local_lci_index.npz')) { throw 'Could not create search index.' }
    }
    Write-Host 'Starting web app at http://127.0.0.1:8000 ...'
    $server = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','local_demo:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    $webReady = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        if ($server.HasExited) { throw 'Web server stopped. Check whether port 8000 is in use.' }
        try { Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 3 | Out-Null; $webReady = $true; break } catch {}
    }
    if (!$webReady) { throw 'Web app did not become ready.' }
    Start-Process 'http://127.0.0.1:8000'
    Write-Host 'Ready. Keep this window open while presenting.'
    Wait-Process -Id $server.Id
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    exit 1
}
