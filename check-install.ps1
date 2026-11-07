#Requires -Version 5.1
# algosec-agent-spec Windows check-install
param([string]$Workspace = "")

$CursorSkills = Join-Path $env:USERPROFILE ".cursor\skills"
$Projects = Join-Path $CursorSkills ".algosec-agent-spec-projects"
$missing = 0

Write-Host "Checking $CursorSkills"
if (-not (Test-Path $CursorSkills)) { Write-Host "MISSING skills dir"; $missing = 1 }

Get-ChildItem -Directory (Join-Path $PSScriptRoot "skills") -ErrorAction SilentlyContinue | ForEach-Object {
  $p = Join-Path $CursorSkills $_.Name
  if (Test-Path (Join-Path $p "SKILL.md")) { Write-Host "OK $($_.Name)" }
  else { Write-Host "MISSING $($_.Name)"; $missing = 1 }
}

if (Test-Path $Projects) {
  Write-Host "Registered:"
  Get-Content $Projects | ForEach-Object {
    if ($_ -and (Test-Path $_)) {
      $rule = Join-Path $_ ".cursor\rules\agent-spec.mdc"
      if (Test-Path $rule) { Write-Host "  OK $_" } else { Write-Host "  WARN no rule $_"; $missing = 1 }
    }
  }
}

if ($Workspace) {
  $root = (Resolve-Path $Workspace).Path
  if (-not (Test-Path (Join-Path $root ".cursor\rules\agent-spec.mdc"))) {
    Write-Host "MISSING mdc in $root"
    $missing = 1
  }
}

Write-Host "Health check for a workspace: python .agent-spec\bin\agent-spec-doctor.py --project <workspace>"
Write-Host "Customize → Rules → agent-spec (Always Apply)"
if ($missing -ne 0) { exit 1 }
Write-Host "All checks passed."
