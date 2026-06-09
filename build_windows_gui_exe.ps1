param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing runtime and build dependencies..."
& $PythonExe -m pip install -e ".[dev]"

$version = & $PythonExe -c "from wlc_role_acl_collector import __version__; print(__version__)"
$exeName = "WlcRoleAclCollectorGUI"
$distDir = Join-Path $PSScriptRoot "dist"
$buildRoot = Join-Path $PSScriptRoot ".pyinstaller_build"
$buildDir = Join-Path $buildRoot ([DateTime]::Now.ToString("yyyyMMdd_HHmmss"))
$specDir = Join-Path $buildDir "spec"
$releaseRoot = Join-Path $buildDir "release"
$distExe = Join-Path $distDir "$exeName.exe"
$releaseZip = Join-Path $distDir "${exeName}_v${version}.zip"
$roleNetworkTemplate = Join-Path $PSScriptRoot "config\role_networks.example.xlsx"
$userGuide = Join-Path $PSScriptRoot "docs\USER_GUIDE_KO.md"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path $specDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

if (Test-Path $distExe) {
    Remove-Item -LiteralPath $distExe -Force
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
    --name $exeName `
    --distpath $distDir `
    --workpath $buildDir `
    --specpath $specDir `
    --paths ".\src" `
    ".\gui_launcher.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Creating release zip..."
Copy-Item -LiteralPath $distExe -Destination $releaseRoot -Force
Copy-Item -LiteralPath $userGuide -Destination (Join-Path $releaseRoot "USER_GUIDE_KO.md") -Force
New-Item -ItemType Directory -Force -Path (Join-Path $releaseRoot "config") | Out-Null
Copy-Item -LiteralPath $roleNetworkTemplate -Destination (Join-Path $releaseRoot "config") -Force
Compress-Archive -Path (Join-Path $releaseRoot "*") -DestinationPath $releaseZip -Force

Write-Host ""
Write-Host "Build completed."
Write-Host "Build work directory: $buildDir"
Write-Host "Single-file executable: $distExe"
Write-Host "Release zip: $releaseZip"
