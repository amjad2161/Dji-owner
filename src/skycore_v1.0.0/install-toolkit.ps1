# Drone Mastery Hub — Windows toolkit installer
#
# Installs everything needed for the six capability tracks.
# Requires winget (built into Windows 10 1809+ and Windows 11 22H2+).
#
# Run from a regular PowerShell prompt. winget will prompt for elevation per-package as needed.
#
# One-liner:
#   iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "Drone Mastery Hub — Windows toolkit installer" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Check winget
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: winget is not installed." -ForegroundColor Red
    Write-Host "Install 'App Installer' from the Microsoft Store, then re-run this script."
    exit 1
}

# Toolset — each entry: winget package id, friendly name, which track it serves
$packages = @(
    @{ Id = "BlackmagicDesign.DaVinciResolve";   Name = "DaVinci Resolve";       Track = "Track 3 (cinematic video)" },
    @{ Id = "OBSProject.OBSStudio";                Name = "OBS Studio";            Track = "Track 6 (live streaming)" },
    @{ Id = "VideoLAN.VLC";                        Name = "VLC";                   Track = "Footage playback" },
    @{ Id = "Python.Python.3.12";                  Name = "Python 3.12";           Track = "Track 5 (log analyzer)" },
    @{ Id = "Git.Git";                             Name = "Git";                   Track = "Track 1 / 2 (development)" },
    @{ Id = "Genymobile.Scrcpy";                   Name = "scrcpy";                Track = "Track 6 (phone mirror)" },
    @{ Id = "Microsoft.VisualStudioCode";          Name = "VS Code (optional)";    Track = "Track 1 / 2 (development)" },
    @{ Id = "7zip.7zip";                           Name = "7-Zip";                 Track = "Archive extraction" }
)

$installed = 0
$skipped = 0
$failed = 0

foreach ($pkg in $packages) {
    Write-Host "-> $($pkg.Name)" -ForegroundColor Yellow -NoNewline
    Write-Host "   [$($pkg.Track)]" -ForegroundColor DarkGray

    # Check if already installed
    $check = winget list --id $pkg.Id -e 2>$null | Out-String
    if ($check -match $pkg.Id) {
        Write-Host "   already installed, skipping" -ForegroundColor DarkGreen
        $skipped++
        continue
    }

    # Install
    winget install --id $pkg.Id -e --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ok" -ForegroundColor Green
        $installed++
    } else {
        Write-Host "   failed (exit $LASTEXITCODE)" -ForegroundColor Red
        $failed++
    }
    Write-Host ""
}

Write-Host ""
Write-Host "Summary: $installed installed, $skipped already-installed, $failed failed" -ForegroundColor Cyan
Write-Host ""

Write-Host "Manual downloads (no winget package available):" -ForegroundColor Cyan
Write-Host "  • DJI Assistant 2 for Mavic   https://www.dji.com/downloads"
Write-Host "  • DJI Fly (mobile only)        Google Play / App Store"
Write-Host "  • Gyroflow                     https://gyroflow.xyz"
Write-Host "  • DatCon (DJI .DAT decoder)    https://datfile.net"
Write-Host "  • Litchi (paid, $25)           https://flylitchi.com  (older Mavic models only)"
Write-Host ""
Write-Host "Done. Restart any open terminals so PATH updates take effect." -ForegroundColor Green
Write-Host ""
