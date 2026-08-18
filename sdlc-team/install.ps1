<#
.SYNOPSIS
  Install the sdlc-team Claude Code plugin into a project.

.DESCRIPTION
  Copies the plugin into <Target>\.claude\skills\sdlc-team so Claude Code
  auto-discovers it — no --plugin-dir flag needed.

.PARAMETER Target
  Project to install into. Defaults to the current directory.

.PARAMETER Force
  Overwrite an existing install.

.PARAMETER Dev
  Don't copy anything; just print the --plugin-dir command.

.EXAMPLE
  .\install.ps1 C:\code\my-project

.EXAMPLE
  .\install.ps1 -Dev
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)] [string] $Target = (Get-Location).Path,
  [switch] $Force,
  [switch] $Dev
)

$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot

Write-Host "sdlc-team installer" -ForegroundColor Blue
Write-Host "  source: $src"

# --- sanity ------------------------------------------------------------------
if (-not (Test-Path (Join-Path $src '.claude-plugin\plugin.json'))) {
  Write-Host "X $src is not an sdlc-team plugin (no .claude-plugin\plugin.json)" -ForegroundColor Red
  exit 1
}

if ($Dev) {
  Write-Host ""
  Write-Host "Session-only load - no files copied. Run:" -ForegroundColor Green
  Write-Host ""
  Write-Host "  claude --plugin-dir `"$src`""
  Write-Host ""
  exit 0
}

if (-not (Test-Path $Target)) {
  Write-Host "X target directory does not exist: $Target" -ForegroundColor Red
  exit 1
}
$Target = (Resolve-Path $Target).Path
$dest   = Join-Path $Target '.claude\skills\sdlc-team'

Write-Host "  target: $Target"
Write-Host ""

if ($src -eq $dest) {
  Write-Host "- Already installed at this exact path; nothing to do." -ForegroundColor Yellow
  exit 0
}

if ((Test-Path $dest) -and (-not $Force)) {
  Write-Host "! Already installed at $dest" -ForegroundColor Yellow
  Write-Host "  Re-run with -Force to overwrite."
  exit 1
}

# --- install -----------------------------------------------------------------
New-Item -ItemType Directory -Force -Path (Join-Path $Target '.claude\skills') | Out-Null
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force -Path $dest | Out-Null

foreach ($item in @('.claude-plugin', 'agents', 'commands', 'skills', 'README.md', 'TESTING.md')) {
  $p = Join-Path $src $item
  if (Test-Path $p) { Copy-Item -Recurse -Force $p $dest }
}
Write-Host "OK Installed -> $dest" -ForegroundColor Green

# --- verify ------------------------------------------------------------------
$a = @(Get-ChildItem (Join-Path $dest 'agents')   -Filter *.md     -ErrorAction SilentlyContinue).Count
$s = @(Get-ChildItem (Join-Path $dest 'skills')   -Filter SKILL.md -Recurse -ErrorAction SilentlyContinue).Count
$c = @(Get-ChildItem (Join-Path $dest 'commands') -Filter *.md     -ErrorAction SilentlyContinue).Count
Write-Host "   $a agents - $s skills - $c commands"

if ($a -eq 0 -or $s -eq 0) {
  Write-Host "X Install looks incomplete - agents or skills are missing." -ForegroundColor Red
  exit 1
}

if (Get-Command claude -ErrorAction SilentlyContinue) {
  $out = & claude plugin validate $dest 2>&1 | Out-String
  if ($out -match 'passed') {
    Write-Host "OK claude plugin validate: passed" -ForegroundColor Green
  } else {
    Write-Host "! claude plugin validate did not report success - run it manually." -ForegroundColor Yellow
  }
}

# --- gitignore warning -------------------------------------------------------
if ((Test-Path (Join-Path $Target '.gitignore')) -and (Get-Command git -ErrorAction SilentlyContinue)) {
  & git -C $Target check-ignore -q $dest 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "! .gitignore excludes .claude\skills\sdlc-team" -ForegroundColor Yellow
    Write-Host "  The plugin still works for you, but teammates won't get it."
    Write-Host "  To share it, add to .gitignore:  !/.claude/skills/sdlc-team/"
  }
}

# --- next steps --------------------------------------------------------------
Write-Host ""
Write-Host "1. RESTART Claude Code." -ForegroundColor Yellow
Write-Host "   It only picks up .claude\skills\ that existed when the session"
Write-Host "   started. A mid-session install looks broken but is not."
Write-Host ""
Write-Host "2. Try it:   /prd add CSV export"
Write-Host "   If not found, try the namespaced form:  /sdlc-team:prd"
Write-Host ""
Write-Host "3. Full pipeline:  /new-feature add CSV export"
Write-Host "   Verification prompts:  $dest\TESTING.md"
Write-Host ""
