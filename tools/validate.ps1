param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Push-Location $repoRoot

try {
    $srcPath = Join-Path $repoRoot "src"
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH"
    } else {
        $env:PYTHONPATH = "$srcPath"
    }

    Write-Host "[1/3] pytest"
    python -m pytest -q

    Write-Host "[2/3] compileall"
    python -m compileall -q app.py src tests tools

    Write-Host "[3/3] Access Check JavaScript syntax"
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        $tempScript = Join-Path ([System.IO.Path]::GetTempPath()) "wlc_access_check_script.js"
        try {
            python -c "from wlc_role_acl_collector.report import _access_check_script; print(_access_check_script())" |
                Set-Content -LiteralPath $tempScript -Encoding UTF8
            node --check $tempScript
        } finally {
            if (Test-Path -LiteralPath $tempScript) {
                Remove-Item -LiteralPath $tempScript -Force
            }
        }
    } else {
        Write-Warning "Node.js was not found. Skipping JavaScript syntax check."
    }

    Write-Host "Validation completed."
} finally {
    Pop-Location
}
