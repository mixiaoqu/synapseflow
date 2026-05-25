param(
    [string]$OutputDir,
    [switch]$UseWorkspaceRuntime
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[SynapseFlow MCP Build] $Message"
}

function New-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Remove-Directory {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Copy-Tree {
    param(
        [string]$Source,
        [string]$Target
    )

    New-Directory -Path $Target
    $null = robocopy $Source $Target /MIR /NFL /NDL /NJH /NJS /NP
    $exitCode = $LASTEXITCODE
    if ($exitCode -gt 7) {
        throw "复制目录失败，robocopy exit code: $exitCode"
    }
}

function Set-TextFile {
    param(
        [string]$Path,
        [string]$Content
    )

    $utf8WithBom = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8WithBom)
}

$rootDir = Split-Path -Parent $PSScriptRoot
$installerDir = Join-Path $rootDir "installer\windows"
$artifactsRoot = Join-Path $rootDir ".artifacts"
$releaseRoot = if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    Join-Path $artifactsRoot "release\windows\SynapseFlowMCP"
} else {
    [System.IO.Path]::GetFullPath($OutputDir)
}
$stageRoot = Join-Path $artifactsRoot "installer-stage"
$deployDir = Join-Path $stageRoot "app"
$bundleEntry = Join-Path $deployDir "dist\index.js"

Write-Step "Building Windows installer package."

Remove-Directory -Path $stageRoot
Remove-Directory -Path $releaseRoot
New-Directory -Path $stageRoot

Write-Step "Compiling TypeScript sources."
& (Join-Path $rootDir "node_modules\.bin\tsc.CMD") -p (Join-Path $rootDir "tsconfig.json")
if ($LASTEXITCODE -ne 0) {
    throw "TypeScript compilation failed."
}

New-Directory -Path (Join-Path $deployDir "dist")

$esbuildBin = Join-Path $rootDir "node_modules\.pnpm\esbuild@0.28.0\node_modules\esbuild\bin\esbuild"
if (-not (Test-Path -LiteralPath $esbuildBin)) {
    throw "esbuild binary was not found in the workspace."
}

if ($UseWorkspaceRuntime) {
    Write-Step "Bundling runtime from local workspace dependencies."
} else {
    Write-Step "Bundling runtime into a single installer payload."
}

& node $esbuildBin (Join-Path $rootDir "src\index.ts") --bundle --platform=node --format=esm --target=node20 --outfile=$bundleEntry
if ($LASTEXITCODE -ne 0) {
    throw "esbuild bundling failed."
}

if (-not (Test-Path -LiteralPath $bundleEntry)) {
    throw "Bundled installer payload is missing dist/index.js."
}

$packageJson = Get-Content -LiteralPath (Join-Path $rootDir "package.json") -Raw | ConvertFrom-Json
$version = [string]$packageJson.version
$versionNotes = @"
版本：
$version

知识库 MCP 提示词模板：

1. 确认作用域
请调用 kb_scope_resolve，确认当前知识库作用域。

2. 检索知识库
请调用 kb_search，检索以下内容的知识库资料：XXX

3. 基于知识库回答
请调用 kb_answer，基于知识库回答以下问题：XXX

4. 自然语言触发
请使用知识库 MCP 回答以下问题：XXX

5. 先检索后总结
请先搜索知识库，再总结结果并回答：XXX
"@
$runtimePackageJson = @"
{
  "name": "synapseflow-mcp-installer-app",
  "version": "$version",
  "private": true,
  "type": "module"
}
"@
Set-TextFile -Path (Join-Path $deployDir "package.json") -Content $runtimePackageJson

Write-Step "Creating installer directory."
New-Directory -Path $releaseRoot
Write-Step "Copying app payload..."
Copy-Tree -Source $deployDir -Target (Join-Path $releaseRoot "app")
Write-Step "Copying installer scripts..."
Copy-Item -LiteralPath (Join-Path $installerDir "install-synapseflow-mcp.cmd") -Destination (Join-Path $releaseRoot "install-synapseflow-mcp.cmd") -Force
Copy-Item -LiteralPath (Join-Path $installerDir "install-synapseflow-mcp.ps1") -Destination (Join-Path $releaseRoot "install-synapseflow-mcp.ps1") -Force
Copy-Item -LiteralPath (Join-Path $installerDir "start-synapseflow-mcp.cmd") -Destination (Join-Path $releaseRoot "start-synapseflow-mcp.cmd") -Force
Copy-Item -LiteralPath (Join-Path $installerDir "uninstall-synapseflow-mcp.cmd") -Destination (Join-Path $releaseRoot "uninstall-synapseflow-mcp.cmd") -Force
Copy-Item -LiteralPath (Join-Path $installerDir "uninstall-synapseflow-mcp.ps1") -Destination (Join-Path $releaseRoot "uninstall-synapseflow-mcp.ps1") -Force

Write-Step "Writing version metadata."
Set-TextFile -Path (Join-Path $releaseRoot "VERSION.txt") -Content $versionNotes

Write-Host ""
Write-Step "Installer package created at: $releaseRoot"
Write-Step "Share this directory with teammates and ask them to run install-synapseflow-mcp.cmd"

$zipPath = "$releaseRoot.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $releaseRoot "*") -DestinationPath $zipPath -Force
Write-Step "Zip package created at: $zipPath"
