param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

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

Write-Host "Installing runtime and build dependencies..."
& $PythonExe -m pip install -e ".[dev]"

Write-Host "Generating HTML guide documents..."
& $PythonExe ".\tools\generate_doc_html.py"

$version = & $PythonExe -c "from wlc_role_acl_collector import __version__; print(__version__)"
$guiExeName = "WlcRoleAclCollectorGUI"
$cliExeName = "WlcRoleAclCollectorCLI"
$distDir = Join-Path $PSScriptRoot "dist"
$buildRoot = Join-Path $PSScriptRoot ".pyinstaller_build"
$buildDir = Join-Path $buildRoot ([DateTime]::Now.ToString("yyyyMMdd_HHmmss"))
$specDir = Join-Path $buildDir "spec"
$releaseRoot = Join-Path $buildDir "release"
$distGuiExe = Join-Path $distDir "$guiExeName.exe"
$distCliExe = Join-Path $distDir "$cliExeName.exe"
$releaseZip = Join-Path $distDir "${guiExeName}_v${version}.zip"
$roleNetworkTemplate = Join-Path $PSScriptRoot "config\role_networks.example.xlsx"
$userGuide = Join-Path $PSScriptRoot "docs\USER_GUIDE_KO.md"
$userGuideHtml = Join-Path $PSScriptRoot "docs\USER_GUIDE_KO.html"
$developerGuide = Join-Path $PSScriptRoot "docs\DEVELOPER_GUIDE_KO.md"
$developerGuideHtml = Join-Path $PSScriptRoot "docs\DEVELOPER_GUIDE_KO.html"
$errorCodesGuide = Join-Path $PSScriptRoot "docs\ERROR_CODES_KO.md"
$errorCodesGuideHtml = Join-Path $PSScriptRoot "docs\ERROR_CODES_KO.html"
$diagnosticModeGuide = Join-Path $PSScriptRoot "docs\DIAGNOSTIC_MODE_KO.md"
$diagnosticModeGuideHtml = Join-Path $PSScriptRoot "docs\DIAGNOSTIC_MODE_KO.html"
$securityModelGuide = Join-Path $PSScriptRoot "docs\SECURITY_MODEL_KO.md"
$securityModelGuideHtml = Join-Path $PSScriptRoot "docs\SECURITY_MODEL_KO.html"
$mockScenarioDir = Join-Path $PSScriptRoot "config\mock_scenarios"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path $specDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

if (Test-Path $distGuiExe) {
    Remove-Item -LiteralPath $distGuiExe -Force
}
if (Test-Path $distCliExe) {
    Remove-Item -LiteralPath $distCliExe -Force
}
if (Test-Path $releaseZip) {
    Remove-Item -LiteralPath $releaseZip -Force
}

Write-Host "Building Windows GUI executable..."
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $guiExeName `
    --distpath $distDir `
    --workpath $buildDir `
    --specpath $specDir `
    --paths ".\src" `
    ".\gui_launcher.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Building Windows CLI executable..."
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name $cliExeName `
    --distpath $distDir `
    --workpath $buildDir `
    --specpath $specDir `
    --paths ".\src" `
    ".\cli_launcher.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller CLI build failed with exit code $LASTEXITCODE"
}

Write-Host "Creating release zip..."
Copy-Item -LiteralPath $distGuiExe -Destination $releaseRoot -Force
Copy-Item -LiteralPath $distCliExe -Destination $releaseRoot -Force
Copy-Item -LiteralPath $userGuide -Destination (Join-Path $releaseRoot "USER_GUIDE_KO.md") -Force
Copy-Item -LiteralPath $userGuideHtml -Destination (Join-Path $releaseRoot "USER_GUIDE_KO.html") -Force
Copy-Item -LiteralPath $developerGuide -Destination (Join-Path $releaseRoot "DEVELOPER_GUIDE_KO.md") -Force
Copy-Item -LiteralPath $developerGuideHtml -Destination (Join-Path $releaseRoot "DEVELOPER_GUIDE_KO.html") -Force
Copy-Item -LiteralPath $errorCodesGuide -Destination (Join-Path $releaseRoot "ERROR_CODES_KO.md") -Force
Copy-Item -LiteralPath $errorCodesGuideHtml -Destination (Join-Path $releaseRoot "ERROR_CODES_KO.html") -Force
Copy-Item -LiteralPath $diagnosticModeGuide -Destination (Join-Path $releaseRoot "DIAGNOSTIC_MODE_KO.md") -Force
Copy-Item -LiteralPath $diagnosticModeGuideHtml -Destination (Join-Path $releaseRoot "DIAGNOSTIC_MODE_KO.html") -Force
Copy-Item -LiteralPath $securityModelGuide -Destination (Join-Path $releaseRoot "SECURITY_MODEL_KO.md") -Force
Copy-Item -LiteralPath $securityModelGuideHtml -Destination (Join-Path $releaseRoot "SECURITY_MODEL_KO.html") -Force
New-Item -ItemType Directory -Force -Path (Join-Path $releaseRoot "config") | Out-Null
Copy-Item -LiteralPath $roleNetworkTemplate -Destination (Join-Path $releaseRoot "config") -Force
Copy-Item -LiteralPath $mockScenarioDir -Destination (Join-Path $releaseRoot "config") -Recurse -Force
Get-ChildItem -Path $releaseRoot -Recurse -File | ForEach-Object {
    Wait-ForReadableFile -Path $_.FullName
}
Compress-ArchiveWithRetry -Path (Join-Path $releaseRoot "*") -DestinationPath $releaseZip

Write-Host ""
Write-Host "Build completed."
Write-Host "Build work directory: $buildDir"
Write-Host "GUI executable: $distGuiExe"
Write-Host "CLI executable: $distCliExe"
Write-Host "Release zip: $releaseZip"
