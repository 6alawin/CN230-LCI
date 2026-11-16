param(
    [switch]$Reset,
    [int]$BatchSize = 1000
)

$projectPath = (Resolve-Path ".").Path -replace '\\', '/'
$neo4jPassword = "cn230lci2026"

if (Test-Path ".env") {
    $passwordLine = Get-Content ".env" | Where-Object { $_ -match '^\s*NEO4J_PASSWORD\s*=' } | Select-Object -First 1
    if ($passwordLine) {
        $neo4jPassword = ($passwordLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
    }
}

$scriptArgs = "python graph/sync_neo4j.py --batch-size $BatchSize"
if ($Reset) {
    $scriptArgs += " --reset"
}

$dockerArgs = @(
    "run", "--rm",
    "--network", "cn230_lci-project_default",
    "-v", "${projectPath}:/workspace",
    "-w", "/workspace",
    "-e", "PGHOST=db",
    "-e", "PGPORT=5432",
    "-e", "PGDATABASE=cn230lci",
    "-e", "PGUSER=cn230lci",
    "-e", "PGPASSWORD=portugalsql",
    "-e", "NEO4J_URI=bolt://neo4j:7687",
    "-e", "NEO4J_USER=neo4j",
    "-e", "NEO4J_PASSWORD=$neo4jPassword",
    "python:3.12-slim",
    "sh", "-c",
    "python -m pip install --disable-pip-version-check --no-cache-dir -r graph/requirements.txt && $scriptArgs"
)

& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Neo4j sync failed (docker exit code $LASTEXITCODE). Check that docker compose services are running."
}
