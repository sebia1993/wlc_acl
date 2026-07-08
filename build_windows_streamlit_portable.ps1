param(
    [string]$PythonExe = "python",
    [string]$EmbeddedPythonVersion = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$ErrorMessage = ""
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        if ($ErrorMessage) {
            throw "$ErrorMessage Exit code: $LASTEXITCODE"
        }
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

function Wait-ForReadableFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$Attempts = 20,
        [int]$DelayMilliseconds = 500
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
            $stream.Close()
            return
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw "File is not ready for reading: $Path`n$($_.Exception.Message)"
            }
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
}

function Compress-ArchiveWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath,
        [int]$Attempts = 5
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            if (Test-Path $DestinationPath) {
                Remove-Item -LiteralPath $DestinationPath -Force
            }
            Compress-Archive -Path $Path -DestinationPath $DestinationPath -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw
            }
            Start-Sleep -Seconds 1
        }
    }
}

Write-Host "Installing host build dependencies..."
Invoke-External -FilePath $PythonExe -Arguments @("-m", "pip", "install", "--upgrade", "pip") -ErrorMessage "pip upgrade failed."
Invoke-External -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-e", ".[web]") -ErrorMessage "Project web dependency install failed."

$version = (& $PythonExe -c "from wlc_role_acl_collector import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Failed to read project version."
}

if (-not $EmbeddedPythonVersion) {
    $EmbeddedPythonVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $EmbeddedPythonVersion) {
        throw "Failed to read host Python version."
    }
}

$pythonVersionParts = $EmbeddedPythonVersion.Split(".")
if ($pythonVersionParts.Count -lt 2) {
    throw "EmbeddedPythonVersion must look like 3.11.9. Value: $EmbeddedPythonVersion"
}
$pythonTag = "{0}{1}" -f $pythonVersionParts[0], $pythonVersionParts[1]

$distDir = Join-Path $PSScriptRoot "dist"
$buildRoot = Join-Path $PSScriptRoot ".streamlit_portable_build"
$cacheDir = Join-Path $buildRoot "cache"
$buildDir = Join-Path $buildRoot ([DateTime]::Now.ToString("yyyyMMdd_HHmmss"))
$releaseRoot = Join-Path $buildDir "WlcRoleAclCollectorWeb"
$pythonDir = Join-Path $releaseRoot "python"
$sitePackages = Join-Path $pythonDir "Lib\site-packages"
$templateDir = Join-Path $PSScriptRoot "packaging\streamlit_portable"
$releaseZip = Join-Path $distDir "WlcRoleAclCollectorWeb_v${version}.zip"
$embeddedZip = Join-Path $cacheDir "python-$EmbeddedPythonVersion-embed-amd64.zip"
$embeddedUrl = "https://www.python.org/ftp/python/$EmbeddedPythonVersion/python-$EmbeddedPythonVersion-embed-amd64.zip"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

if (Test-Path $releaseZip) {
    Remove-Item -LiteralPath $releaseZip -Force
}

if (-not (Test-Path $embeddedZip)) {
    Write-Host "Downloading Python embeddable runtime: $embeddedUrl"
    Invoke-WebRequest -Uri $embeddedUrl -OutFile $embeddedZip
}

Write-Host "Extracting Python embeddable runtime..."
Expand-Archive -LiteralPath $embeddedZip -DestinationPath $pythonDir -Force
New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null

$pthPath = Join-Path $pythonDir "python${pythonTag}._pth"
$pthLines = @(
    "python${pythonTag}.zip",
    ".",
    "Lib\site-packages",
    "import site"
)
$pthLines | Set-Content -LiteralPath $pthPath -Encoding ASCII

Write-Host "Installing web app dependencies into portable runtime..."
Invoke-External `
    -FilePath $PythonExe `
    -Arguments @("-m", "pip", "install", "--upgrade", "--no-warn-script-location", "--target", $sitePackages, ".[web]") `
    -ErrorMessage "Portable dependency install failed."

New-Item -ItemType Directory -Force -Path (Join-Path $releaseRoot "app") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $releaseRoot "config") | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "app.py") -Destination (Join-Path $releaseRoot "app\app.py") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "config\role_networks.example.xlsx") -Destination (Join-Path $releaseRoot "config\role_networks.example.xlsx") -Force
Copy-Item -LiteralPath (Join-Path $templateDir "start_webapp.cmd") -Destination (Join-Path $releaseRoot "start_webapp.cmd") -Force
Copy-Item -LiteralPath (Join-Path $templateDir "webapp_settings.cmd") -Destination (Join-Path $releaseRoot "webapp_settings.cmd") -Force
Copy-Item -LiteralPath (Join-Path $templateDir "README_WEBAPP_KO.txt") -Destination (Join-Path $releaseRoot "README_WEBAPP_KO.txt") -Force

Write-Host "Precompiling portable web app modules..."
$portablePython = Join-Path $pythonDir "python.exe"
$precompileTargets = @(
    (Join-Path $releaseRoot "app"),
    (Join-Path $sitePackages "wlc_role_acl_collector"),
    (Join-Path $sitePackages "streamlit"),
    (Join-Path $sitePackages "pandas"),
    (Join-Path $sitePackages "openpyxl"),
    (Join-Path $sitePackages "netmiko"),
    (Join-Path $sitePackages "paramiko")
) | Where-Object { Test-Path $_ }

if ($precompileTargets.Count -gt 0) {
    $compileArgs = @("-m", "compileall", "-q") + @($precompileTargets)
    Invoke-External `
        -FilePath $portablePython `
        -Arguments $compileArgs `
        -ErrorMessage "Portable module precompile failed."
}

Write-Host "Running portable web app smoke test..."
Push-Location $releaseRoot
try {
    & cmd.exe /c ".\start_webapp.cmd --smoke"
    if ($LASTEXITCODE -ne 0) {
        throw "Portable Streamlit smoke test failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Host "Creating Streamlit portable release zip..."
Get-ChildItem -Path $releaseRoot -Recurse -File | ForEach-Object {
    Wait-ForReadableFile -Path $_.FullName
}
Compress-ArchiveWithRetry -Path (Join-Path $releaseRoot "*") -DestinationPath $releaseZip

Write-Host ""
Write-Host "Streamlit portable build completed."
Write-Host "Build work directory: $buildDir"
Write-Host "Embedded Python version: $EmbeddedPythonVersion"
Write-Host "Release zip: $releaseZip"
