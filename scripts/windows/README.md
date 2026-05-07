# Windows Scripts

PowerShell helpers that handle the boring parts of setting up a drone development / production machine.

## `install-toolkit.ps1`

Installs the GUI toolset for all six tracks via [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):

- DaVinci Resolve (video editing)
- OBS Studio (live streaming)
- VLC (playback)
- Python 3.12 (log analyzer)
- Git
- scrcpy (mirror Android phone to PC)
- VS Code (optional editor)
- 7-Zip

### Run

One-liner:

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex
```

Or from a local clone:

```powershell
pwsh -File install-toolkit.ps1
```

winget will prompt for UAC elevation when each package needs it.

### What it does NOT install

These have no winget package. Install manually:

| Tool | URL |
|------|-----|
| DJI Assistant 2 for Mavic | https://www.dji.com/downloads |
| Gyroflow | https://gyroflow.xyz |
| DatCon | https://datfile.net |
| Litchi (paid, older Mavic only) | https://flylitchi.com |

## `clone-dev-repos.ps1`

Clones every major open-source drone repo from the [awesome-drone-repos catalog](../../docs/en/awesome-drone-repos.md) into `~/dji-dev/`. About 15 GB after shallow clone.

Useful when you're about to spend a weekend exploring the SDKs.

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/clone-dev-repos.ps1 -UseBasicParsing | iex
```

Idempotent: re-running skips repos that already exist locally.

## Requirements

- Windows 10 1809+ or Windows 11
- PowerShell 5.1 (built-in) or PowerShell 7+
- Internet
- ~50 GB free if you also clone all dev repos

## Troubleshooting

- **"winget not recognized"** — install `App Installer` from the Microsoft Store, restart the terminal.
- **"Execution policy"** — run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **"git not recognized" after install** — close and reopen the terminal so PATH refreshes.
