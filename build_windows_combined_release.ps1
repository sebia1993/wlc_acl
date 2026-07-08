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

$version = (& $PythonExe -c "from wlc_role_acl_collector import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Failed to read project version."
}

$distDir = Join-Path $PSScriptRoot "dist"
$buildRoot = Join-Path $PSScriptRoot ".combined_release_build"
$buildDir = Join-Path $buildRoot ([DateTime]::Now.ToString("yyyyMMdd_HHmmss"))
$guiExtractDir = Join-Path $buildDir "gui_source"
$webExtractDir = Join-Path $buildDir "web_source"
$releaseRoot = Join-Path $buildDir "release"
$combinedZip = Join-Path $distDir "WlcRoleAclCollectorWindows_v${version}.zip"
$readmeTemplate = Join-Path $PSScriptRoot "packaging\combined_release\README_START_HERE_KO.txt"

$guiZip = Get-ChildItem -Path $distDir -Filter "WlcRoleAclCollectorGUI_*.zip" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $guiZip) {
    throw "No Windows GUI/CLI ZIP was found in dist."
}

$webZip = Get-ChildItem -Path $distDir -Filter "WlcRoleAclCollectorWeb_*.zip" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $webZip) {
    throw "No Streamlit portable ZIP was found in dist."
}

New-Item -ItemType Directory -Force -Path $guiExtractDir | Out-Null
New-Item -ItemType Directory -Force -Path $webExtractDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $releaseRoot "gui") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $releaseRoot "web") | Out-Null

Write-Host "Extracting GUI/CLI ZIP: $($guiZip.FullName)"
Expand-Archive -LiteralPath $guiZip.FullName -DestinationPath $guiExtractDir -Force

Write-Host "Extracting Streamlit portable ZIP: $($webZip.FullName)"
Expand-Archive -LiteralPath $webZip.FullName -DestinationPath $webExtractDir -Force

Copy-Item -LiteralPath $readmeTemplate -Destination (Join-Path $releaseRoot "README_START_HERE_KO.txt") -Force
Copy-Item -Path (Join-Path $guiExtractDir "*") -Destination (Join-Path $releaseRoot "gui") -Recurse -Force
Copy-Item -Path (Join-Path $webExtractDir "*") -Destination (Join-Path $releaseRoot "web") -Recurse -Force

Write-Host "Creating combined Windows release ZIP..."
Get-ChildItem -Path $releaseRoot -Recurse -File | ForEach-Object {
    Wait-ForReadableFile -Path $_.FullName
}
Compress-ArchiveWithRetry -Path (Join-Path $releaseRoot "*") -DestinationPath $combinedZip

Write-Host ""
Write-Host "Combined release build completed."
Write-Host "Build work directory: $buildDir"
Write-Host "Combined release ZIP: $combinedZip"
