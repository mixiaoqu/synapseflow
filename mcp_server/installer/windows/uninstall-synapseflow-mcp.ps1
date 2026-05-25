param(
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[SynapseFlow MCP] $Message"
}

function Read-InstallDir {
    param([string]$DefaultDir)
    $inputValue = Read-Host "Enter install directory to remove, or press Enter to use [$DefaultDir]"
    if ([string]::IsNullOrWhiteSpace($inputValue)) {
        return $DefaultDir
    }
    return $inputValue.Trim()
}

function Confirm-Remove {
    param([string]$TargetDir)
    $answer = Read-Host "Remove installation directory $TargetDir ? Type Y to continue"
    if ([string]::IsNullOrWhiteSpace($answer)) {
        return $false
    }
    return $answer.Trim().ToUpperInvariant() -eq "Y"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultInstallDir = "C:\SynapseFlowMCP"
$targetDir = if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    Read-InstallDir -DefaultDir $defaultInstallDir
} else {
    $InstallDir.Trim()
}

$resolvedTargetDir = [System.IO.Path]::GetFullPath($targetDir)
if (-not (Test-Path -LiteralPath $resolvedTargetDir)) {
    Write-Step "Installation directory not found: $resolvedTargetDir"
    exit 0
}

if (-not (Confirm-Remove -TargetDir $resolvedTargetDir)) {
    Write-Step "Uninstall cancelled."
    exit 1
}

Write-Step "Removing: $resolvedTargetDir"
Remove-Item -LiteralPath $resolvedTargetDir -Recurse -Force
Write-Step "Uninstall complete."
