# Link this skill into Claude Code on Windows so it is available in every project.
# A junction needs neither admin rights nor Developer Mode, unlike a symbolic link.
$ErrorActionPreference = 'Stop'
$claude = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $HOME '.claude' }
$target = Join-Path $claude 'skills'
$link = Join-Path $target 'brand-video-studio'
$skill = Join-Path $PSScriptRoot 'skill'
New-Item -ItemType Directory -Force $target | Out-Null

$existing = Get-Item $link -Force -ErrorAction SilentlyContinue
if ($existing) {
    if (-not $existing.LinkType) {
        Write-Error "$link already exists and is not a link. Move it away and run this again."
    }
    [IO.Directory]::Delete($link)  # Removes the link only, never what it points to.
}
New-Item -ItemType Junction -Path $link -Target $skill | Out-Null
Write-Output "Installed: $link -> $skill"

# python3 is usually a Microsoft Store stub on Windows, so look for one that really runs.
$ErrorActionPreference = 'Continue'
$python = $null
foreach ($name in 'python', 'py', 'python3') {
    if (Get-Command $name -ErrorAction SilentlyContinue) {
        & $name --version *> $null
        if ($LASTEXITCODE -eq 0) { $python = $name; break }
    }
}
if (-not $python) {
    Write-Output 'MISS python  -> winget install Python.Python.3.12'
    exit 1
}
& $python (Join-Path $skill 'scripts\doctor.py')
if ($LASTEXITCODE -ne 0) { Write-Output 'Install what is marked MISS above before making videos.' }
