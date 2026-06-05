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
$distExe = Join-Path $distDir "$exeName.exe"
$releaseZip = Join-Path $distDir "${exeName}_v${version}.zip"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path $specDir | Out-Null

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
Compress-Archive -LiteralPath $distExe -DestinationPath $releaseZip -Force

Write-Host ""
Write-Host "Build completed."
Write-Host "Build work directory: $buildDir"
Write-Host "Single-file executable: $distExe"
Write-Host "Release zip: $releaseZip"
