<#
.SYNOPSIS
  Shorts Factory (astras-gif-maker-v0.1.0-shorts-factory-v0.1.0), a tool of Astra's GIF Maker. By Astra.
  Checks for Python 3.10+ and ffmpeg, then runs the pipeline. Safe to run again: it changes nothing that is
  already in place.

.EXAMPLE
  # What is installed, and which providers "auto" would pick
  .\run-shorts-factory-20261026.ps1 check

.EXAMPLE
  # Free, offline sample (placeholder art, Windows voice). Opens the video when done.
  .\run-shorts-factory-20261026.ps1 -Sample

.EXAMPLE
  # Your own Fuzzboi PNGs with a script you wrote, no network
  .\run-shorts-factory-20261026.ps1 make --offline --script .\my-script.json --images "$HOME\Pictures\Fuzzbois"

.EXAMPLE
  # A model writes the script (needs ANTHROPIC_API_KEY or OPENAI_API_KEY in the environment)
  .\run-shorts-factory-20261026.ps1 make --topic "Mommy's Friday dance class" --preset mommys --images .\captures

.PARAMETER Install
  Install what is missing with winget (Python 3.12 and/or Gyan.FFmpeg). Without it, the script only tells you.

.PARAMETER Sample
  Render examples\fuzzbois-dry-run.json offline and open the result.
#>
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Sample,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Find-Python {
    foreach ($cand in @(@('py', '-3'), @('python'), @('python3'))) {
        $exe = Get-Command $cand[0] -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        # The Microsoft Store "python" alias opens the Store instead of running; skip it.
        if ($exe.Source -like '*WindowsApps*') { continue }
        $probeArgs = @($cand | Select-Object -Skip 1) + @('-c', 'import sys; print("%d.%d" % sys.version_info[:2])')
        try { $v = & $exe.Source @probeArgs 2>$null } catch { continue }
        if ($v -match '^(\d+)\.(\d+)$' -and ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 10))) {
            return ,(@($exe.Source) + @($cand | Select-Object -Skip 1))
        }
    }
    return $null
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

$py = Find-Python
if (-not $py) {
    if ($Install) {
        Write-Host 'Installing Python 3.12 with winget...'
        winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
        Refresh-Path
        $py = Find-Python
    }
    if (-not $py) {
        Write-Host 'Python 3.10 or newer was not found. Run again with -Install, or: winget install Python.Python.3.12' -ForegroundColor Yellow
        exit 1
    }
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    if ($Install) {
        Write-Host 'Installing ffmpeg with winget...'
        winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
        Refresh-Path
    }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Host 'ffmpeg was not found. Run again with -Install, or: winget install Gyan.FFmpeg (then open a new window).' -ForegroundColor Yellow
        exit 1
    }
}

$pyExe = $py[0]
$pyArgs = @($py | Select-Object -Skip 1)

Push-Location $here
try {
    if ($Sample) {
        $out = Join-Path $env:LOCALAPPDATA 'astras-pet-os\astras-gif-maker\shorts-factory\videos\sample-fuzzbois.mp4'
        & $pyExe @pyArgs -m shorts_factory make --offline --script (Join-Path $here 'examples\fuzzbois-dry-run.json') --out $out
        if ($LASTEXITCODE -eq 0) { Start-Process $out }
        exit $LASTEXITCODE
    }
    if (-not $Rest -or $Rest.Count -eq 0) { $Rest = @('--help') }
    & $pyExe @pyArgs -m shorts_factory @Rest
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
