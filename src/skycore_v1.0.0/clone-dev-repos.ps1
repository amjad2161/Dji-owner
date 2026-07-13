# Drone Mastery Hub — clone the major drone open-source repos for development
#
# Pulls about 15 GB of source into ~/dji-dev/ using shallow clones.
# Skips repos that are already cloned.
#
# Run from a regular PowerShell prompt:
#   pwsh -File clone-dev-repos.ps1
# Or via web one-liner:
#   iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/clone-dev-repos.ps1 -UseBasicParsing | iex

$ErrorActionPreference = "Continue"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: git is not installed. Run install-toolkit.ps1 first." -ForegroundColor Red
    exit 1
}

$root = Join-Path $env:USERPROFILE "dji-dev"
New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "Cloning into: $root" -ForegroundColor Cyan
Write-Host ""

$repos = @(
    # Official DJI SDKs
    "https://github.com/dji-sdk/Mobile-SDK-Android.git",
    "https://github.com/dji-sdk/Mobile-SDK-iOS.git",
    "https://github.com/dji-sdk/Mobile-UXSDK-Open-Android.git",
    "https://github.com/dji-sdk/Mobile-UXSDK-Open-iOS.git",
    "https://github.com/dji-sdk/Onboard-SDK.git",
    "https://github.com/dji-sdk/Onboard-SDK-ROS.git",
    "https://github.com/dji-sdk/Payload-SDK.git",
    "https://github.com/dji-sdk/Tello-Python.git",

    # Open flight stacks
    "https://github.com/PX4/PX4-Autopilot.git",
    "https://github.com/ArduPilot/ardupilot.git",

    # Ground stations / SDK
    "https://github.com/mavlink/qgroundcontrol.git",
    "https://github.com/mavlink/MAVSDK.git",
    "https://github.com/mavlink/mavlink.git",

    # Video / post
    "https://github.com/gyroflow/gyroflow.git",
    "https://github.com/gyroflow/gyroflow-camera-presets.git",

    # Computer vision / tracking
    "https://github.com/ultralytics/ultralytics.git",
    "https://github.com/mikel-brostrom/boxmot.git",
    "https://github.com/roboflow/supervision.git",

    # Mapping
    "https://github.com/OpenDroneMap/ODM.git",
    "https://github.com/OpenDroneMap/WebODM.git",

    # Education / Tello
    "https://github.com/damiafuentes/DJITelloPy.git"
)

$cloned = 0
$skipped = 0
$failed = @()

foreach ($url in $repos) {
    $name = ($url -replace "\.git$","" -split "/")[-1]
    $target = Join-Path $root $name

    if (Test-Path $target) {
        Write-Host "[skip] $name (already exists)" -ForegroundColor DarkGray
        $skipped++
        continue
    }

    Write-Host "[clone] $name" -ForegroundColor Yellow
    git clone --depth 1 --quiet $url $target
    if ($LASTEXITCODE -eq 0) {
        $cloned++
    } else {
        Write-Host "   failed" -ForegroundColor Red
        $failed += $name
    }
}

Write-Host ""
Write-Host "Summary: $cloned cloned, $skipped skipped, $($failed.Count) failed" -ForegroundColor Cyan
if ($failed.Count -gt 0) {
    Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
}
Write-Host ""
Write-Host "Reference catalog: docs/en/awesome-drone-repos.md" -ForegroundColor Cyan
