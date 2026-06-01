param(
    [string]$InstallDir,
    [switch]$NoGui
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[LangChain RAG 知识库 MCP] $Message"
}

function Load-WinForms {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
}

function Show-ErrorDialog {
    param([string]$Message)

    $owner = New-DialogOwner
    [System.Windows.Forms.MessageBox]::Show(
        $owner,
        $Message,
        "LangChain RAG 知识库 MCP 安装失败",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    Close-DialogOwner -Owner $owner
}

function Show-InfoDialog {
    param(
        [string]$Message,
        [string]$Title = "LangChain RAG 知识库 MCP"
    )

    $owner = New-DialogOwner
    [System.Windows.Forms.MessageBox]::Show(
        $owner,
        $Message,
        $Title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
    Close-DialogOwner -Owner $owner
}

function New-DialogOwner {
    $owner = New-Object System.Windows.Forms.Form
    $owner.StartPosition = "CenterScreen"
    $owner.Size = New-Object System.Drawing.Size(1, 1)
    $owner.ShowInTaskbar = $false
    $owner.TopMost = $true
    $owner.Opacity = 0
    $owner.Show()
    $owner.Activate()
    $owner.BringToFront()
    [System.Windows.Forms.Application]::DoEvents()
    return $owner
}

function Close-DialogOwner {
    param([System.Windows.Forms.Form]$Owner)

    if (-not $Owner) {
        return
    }

    $Owner.Close()
    $Owner.Dispose()
}

function Show-ForegroundForm {
    param([System.Windows.Forms.Form]$Form)

    if (-not $Form) {
        return
    }

    $Form.Show()
    $Form.WindowState = [System.Windows.Forms.FormWindowState]::Normal
    $Form.Activate()
    $Form.BringToFront()
    $null = $Form.Focus()
    [System.Windows.Forms.Application]::DoEvents()
}

function Copy-TextToClipboard {
    param([string]$Text)

    [System.Windows.Forms.Clipboard]::SetText($Text)
}

function Open-InstallDirectory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Start-Process -FilePath "explorer.exe" -ArgumentList "`"$Path`"" | Out-Null
}

function Show-CompletionDialog {
    param(
        [string]$InstallDir,
        [string]$StartScriptPath,
        [string]$TraeTemplatePath
    )

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "LangChain RAG 知识库 MCP 安装完成"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(620, 320)
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $true

    $titleLabel = New-Object System.Windows.Forms.Label
    $titleLabel.Text = "LangChain RAG 知识库 MCP 已安装完成"
    $titleLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 12, [System.Drawing.FontStyle]::Bold)
    $titleLabel.AutoSize = $true
    $titleLabel.Location = New-Object System.Drawing.Point(18, 18)
    $form.Controls.Add($titleLabel)

    $summaryBox = New-Object System.Windows.Forms.TextBox
    $summaryBox.Multiline = $true
    $summaryBox.ReadOnly = $true
    $summaryBox.ScrollBars = "Vertical"
    $summaryBox.Location = New-Object System.Drawing.Point(18, 56)
    $summaryBox.Size = New-Object System.Drawing.Size(566, 150)
    $summaryBox.Text = @"
安装目录：
$InstallDir

启动脚本：
$StartScriptPath

Trae 配置模板：
$TraeTemplatePath
"@
    $form.Controls.Add($summaryBox)

    $hintLabel = New-Object System.Windows.Forms.Label
    $hintLabel.Text = "你现在可以直接复制 Trae 配置，或打开安装目录查看全部文件。"
    $hintLabel.AutoSize = $true
    $hintLabel.Location = New-Object System.Drawing.Point(18, 220)
    $form.Controls.Add($hintLabel)

    $copyButton = New-Object System.Windows.Forms.Button
    $copyButton.Text = "复制 Trae 配置"
    $copyButton.Size = New-Object System.Drawing.Size(130, 32)
    $copyButton.Location = New-Object System.Drawing.Point(18, 246)
    $copyButton.Add_Click({
        try {
            $templateContent = Get-Content -LiteralPath $TraeTemplatePath -Raw -Encoding utf8
            Copy-TextToClipboard -Text $templateContent
            Show-InfoDialog -Message "Trae MCP 配置已复制到剪贴板。"
        } catch {
            Show-ErrorDialog -Message "复制 Trae 配置失败：$($_.Exception.Message)"
        }
    })
    $form.Controls.Add($copyButton)

    $openDirButton = New-Object System.Windows.Forms.Button
    $openDirButton.Text = "打开安装目录"
    $openDirButton.Size = New-Object System.Drawing.Size(130, 32)
    $openDirButton.Location = New-Object System.Drawing.Point(162, 246)
    $openDirButton.Add_Click({
        try {
            Open-InstallDirectory -Path $InstallDir
        } catch {
            Show-ErrorDialog -Message "打开安装目录失败：$($_.Exception.Message)"
        }
    })
    $form.Controls.Add($openDirButton)

    $closeButton = New-Object System.Windows.Forms.Button
    $closeButton.Text = "完成"
    $closeButton.Size = New-Object System.Drawing.Size(96, 32)
    $closeButton.Location = New-Object System.Drawing.Point(488, 246)
    $closeButton.Add_Click({ $form.Close() })
    $form.Controls.Add($closeButton)

    $form.AcceptButton = $closeButton
    $form.Add_Shown({
        $this.Activate()
        $this.BringToFront()
        $null = $this.Focus()
    })
    $form.ShowDialog() | Out-Null
    $form.Dispose()
}

function Confirm-OverwriteGui {
    param([string]$TargetDir)

    $owner = New-DialogOwner
    $result = [System.Windows.Forms.MessageBox]::Show(
        $owner,
        "目标目录已存在文件，是否继续覆盖？`n`n$TargetDir",
        "LangChain RAG 知识库 MCP",
        [System.Windows.Forms.MessageBoxButtons]::OKCancel,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    )
    Close-DialogOwner -Owner $owner

    return $result -eq [System.Windows.Forms.DialogResult]::OK
}

function Select-InstallDir {
    param([string]$DefaultDir)

    $owner = New-DialogOwner
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "请选择 LangChain RAG 知识库 MCP 的安装目录"
    $dialog.ShowNewFolderButton = $true
    $dialog.SelectedPath = $DefaultDir

    $result = $dialog.ShowDialog($owner)
    Close-DialogOwner -Owner $owner
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
        return $null
    }

    return $dialog.SelectedPath
}

function New-ProgressWindow {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "LangChain RAG 知识库 MCP 安装中"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(560, 360)
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $true

    $titleLabel = New-Object System.Windows.Forms.Label
    $titleLabel.Text = "正在安装 LangChain RAG 知识库 MCP"
    $titleLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 12, [System.Drawing.FontStyle]::Bold)
    $titleLabel.AutoSize = $true
    $titleLabel.Location = New-Object System.Drawing.Point(18, 18)
    $form.Controls.Add($titleLabel)

    $statusLabel = New-Object System.Windows.Forms.Label
    $statusLabel.Text = "准备开始..."
    $statusLabel.AutoSize = $false
    $statusLabel.Size = New-Object System.Drawing.Size(500, 24)
    $statusLabel.Location = New-Object System.Drawing.Point(18, 56)
    $form.Controls.Add($statusLabel)

    $progressBar = New-Object System.Windows.Forms.ProgressBar
    $progressBar.Location = New-Object System.Drawing.Point(18, 90)
    $progressBar.Size = New-Object System.Drawing.Size(510, 20)
    $progressBar.Minimum = 0
    $progressBar.Maximum = 100
    $form.Controls.Add($progressBar)

    $listBox = New-Object System.Windows.Forms.ListBox
    $listBox.Location = New-Object System.Drawing.Point(18, 126)
    $listBox.Size = New-Object System.Drawing.Size(510, 172)
    $form.Controls.Add($listBox)

    Show-ForegroundForm -Form $form

    return [PSCustomObject]@{
        Form = $form
        StatusLabel = $statusLabel
        ProgressBar = $progressBar
        ListBox = $listBox
    }
}

function Update-ProgressWindow {
    param(
        [object]$Window,
        [int]$Percent,
        [string]$Message
    )

    if (-not $Window) {
        return
    }

    $Window.StatusLabel.Text = $Message
    $Window.ProgressBar.Value = [Math]::Max($Window.ProgressBar.Minimum, [Math]::Min($Percent, $Window.ProgressBar.Maximum))
    $null = $Window.ListBox.Items.Add($Message)
    $Window.ListBox.TopIndex = [Math]::Max(0, $Window.ListBox.Items.Count - 1)
    [System.Windows.Forms.Application]::DoEvents()
}

function Close-ProgressWindow {
    param([object]$Window)

    if (-not $Window) {
        return
    }

    $Window.Form.Close()
    $Window.Form.Dispose()
}

function New-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
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
        throw "Failed to copy installer files. robocopy exit code: $exitCode"
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

function Escape-JsonPath {
    param([string]$Value)
    return $Value.Replace("\", "\\")
}

function Resolve-InstallDir {
    param(
        [string]$RequestedDir,
        [string]$DefaultDir,
        [bool]$UseGui
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedDir)) {
        return $RequestedDir.Trim()
    }

    if ($UseGui) {
        return Select-InstallDir -DefaultDir $DefaultDir
    }

    return $DefaultDir
}

function Confirm-Overwrite {
    param(
        [string]$TargetDir,
        [bool]$UseGui
    )

    if (-not (Test-Path -LiteralPath $TargetDir)) {
        return $true
    }

    $items = Get-ChildItem -LiteralPath $TargetDir -Force -ErrorAction SilentlyContinue
    if (-not $items) {
        return $true
    }

    if ($UseGui) {
        return Confirm-OverwriteGui -TargetDir $TargetDir
    }

    return $true
}

function Assert-NodeInstalled {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "未检测到 Node.js。请先安装 Node.js 20+ 后重新运行安装器。"
    }
}

function Get-ReadmeContent {
    param(
        [string]$ResolvedTargetDir,
        [string]$McpCommandPath
    )

    return @"
LangChain RAG 知识库 MCP has been installed successfully.

Install directory:
$ResolvedTargetDir

Start command:
$McpCommandPath

Open one of these files and copy it into your editor MCP settings:

1. trae-mcp-config.json
2. codex-mcp-config.json

Then replace these environment variables:

1. SYNAPSEFLOW_BASE_URL
2. SYNAPSEFLOW_SERVICE_TOKEN
3. SYNAPSEFLOW_DEFAULT_PRODUCT
4. SYNAPSEFLOW_DEFAULT_PROJECT
5. SYNAPSEFLOW_DEFAULT_APP

Optional audit fields:

1. SYNAPSEFLOW_CLIENT_USER_ID
2. SYNAPSEFLOW_CLIENT_USER_NAME
3. SYNAPSEFLOW_CLIENT_HOST

To uninstall later, run:

1. uninstall-synapseflow-mcp.cmd
"@
}

function Get-VersionContent {
    param([string]$PackageVersion)

    return @"
版本：
$PackageVersion

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
}

function Get-EditorTemplate {
    param(
        [string]$CommandJsonPath,
        [string]$Editor
    )

    return @"
{
  "mcpServers": {
    "synapseflow-kb": {
      "command": "$CommandJsonPath",
      "env": {
        "SYNAPSEFLOW_BASE_URL": "http://101.96.207.83",
        "SYNAPSEFLOW_SERVICE_TOKEN": "replace-with-your-service-token",
        "SYNAPSEFLOW_DEFAULT_PRODUCT": "test",
        "SYNAPSEFLOW_DEFAULT_PROJECT": "test",
        "SYNAPSEFLOW_DEFAULT_APP": "test",
        "MCP_EDITOR": "$Editor"
      }
    }
  }
}
"@
}

function Invoke-Install {
    param(
        [string]$ScriptDir,
        [string]$ResolvedTargetDir,
        [object]$ProgressWindow,
        [bool]$UseGui
    )

    $sourceAppDir = Join-Path $ScriptDir "app"
    if (-not (Test-Path -LiteralPath $sourceAppDir)) {
        throw "Installer package is missing the app directory: $sourceAppDir"
    }

    $updateStep = {
        param([int]$Percent, [string]$Message)
        if ($UseGui) {
            Update-ProgressWindow -Window $ProgressWindow -Percent $Percent -Message $Message
        } else {
            Write-Step $Message
        }
    }

    & $updateStep 8 "正在检查 Node.js 运行环境..."
    Assert-NodeInstalled

    & $updateStep 18 "正在准备安装目录..."
    New-Directory -Path $ResolvedTargetDir

    $targetAppDir = Join-Path $ResolvedTargetDir "app"
    & $updateStep 38 "正在复制 app 文件..."
    Copy-Tree -Source $sourceAppDir -Target $targetAppDir

    & $updateStep 56 "正在复制启动与卸载脚本..."
    Copy-Item -LiteralPath (Join-Path $ScriptDir "start-synapseflow-mcp.cmd") -Destination (Join-Path $ResolvedTargetDir "start-synapseflow-mcp.cmd") -Force
    Copy-Item -LiteralPath (Join-Path $ScriptDir "uninstall-synapseflow-mcp.cmd") -Destination (Join-Path $ResolvedTargetDir "uninstall-synapseflow-mcp.cmd") -Force
    Copy-Item -LiteralPath (Join-Path $ScriptDir "uninstall-synapseflow-mcp.ps1") -Destination (Join-Path $ResolvedTargetDir "uninstall-synapseflow-mcp.ps1") -Force

    $mcpCommandPath = Join-Path $ResolvedTargetDir "start-synapseflow-mcp.cmd"
    $mcpCommandJsonPath = Escape-JsonPath -Value $mcpCommandPath

    & $updateStep 74 "正在生成编辑器配置模板..."
    Set-TextFile -Path (Join-Path $ResolvedTargetDir "trae-mcp-config.json") -Content (Get-EditorTemplate -CommandJsonPath $mcpCommandJsonPath -Editor "trae")
    Set-TextFile -Path (Join-Path $ResolvedTargetDir "codex-mcp-config.json") -Content (Get-EditorTemplate -CommandJsonPath $mcpCommandJsonPath -Editor "codex")
    Set-TextFile -Path (Join-Path $ResolvedTargetDir "README.txt") -Content (Get-ReadmeContent -ResolvedTargetDir $ResolvedTargetDir -McpCommandPath $mcpCommandPath)

    $packageVersion = ""
    $packageJsonPath = Join-Path $targetAppDir "package.json"
    if (Test-Path -LiteralPath $packageJsonPath) {
        $packageJson = Get-Content -LiteralPath $packageJsonPath -Raw | ConvertFrom-Json
        $packageVersion = [string]$packageJson.version
    }

    if (-not [string]::IsNullOrWhiteSpace($packageVersion)) {
        & $updateStep 88 "正在写入版本与提示词模板..."
        Set-TextFile -Path (Join-Path $ResolvedTargetDir "VERSION.txt") -Content (Get-VersionContent -PackageVersion $packageVersion)
    }

    $traeTemplatePath = Join-Path $ResolvedTargetDir "trae-mcp-config.json"
    & $updateStep 100 "安装完成。"

    return [PSCustomObject]@{
        InstallDir = $ResolvedTargetDir
        StartScriptPath = $mcpCommandPath
        TraeTemplatePath = $traeTemplatePath
        CodexTemplatePath = Join-Path $ResolvedTargetDir "codex-mcp-config.json"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultInstallDir = "C:\SynapseFlowMCP"
$useGui = -not $NoGui
$progressWindow = $null

try {
    if ($useGui) {
        Load-WinForms
    }

    $targetDir = Resolve-InstallDir -RequestedDir $InstallDir -DefaultDir $defaultInstallDir -UseGui $useGui
    if ([string]::IsNullOrWhiteSpace($targetDir)) {
        if (-not $useGui) {
            Write-Step "Installation cancelled."
        }
        exit 1
    }

    $resolvedTargetDir = [System.IO.Path]::GetFullPath($targetDir)
    if (-not (Confirm-Overwrite -TargetDir $resolvedTargetDir -UseGui $useGui)) {
        if (-not $useGui) {
            Write-Step "Installation cancelled."
        }
        exit 1
    }

    if ($useGui) {
        $progressWindow = New-ProgressWindow
    } else {
        Write-Step "Installing to: $resolvedTargetDir"
    }

    $result = Invoke-Install -ScriptDir $scriptDir -ResolvedTargetDir $resolvedTargetDir -ProgressWindow $progressWindow -UseGui $useGui

    if ($useGui) {
        Close-ProgressWindow -Window $progressWindow
        Show-CompletionDialog -InstallDir $result.InstallDir -StartScriptPath $result.StartScriptPath -TraeTemplatePath $result.TraeTemplatePath
    } else {
        Write-Host ""
        Write-Step "Installation complete."
        Write-Step "Start script: $($result.StartScriptPath)"
        Write-Step "Trae template: $($result.TraeTemplatePath)"
        Write-Step "Codex template: $($result.CodexTemplatePath)"
    }
} catch {
    if ($useGui -and $progressWindow) {
        Close-ProgressWindow -Window $progressWindow
    }

    if ($useGui) {
        Show-ErrorDialog -Message $_.Exception.Message
    } else {
        throw
    }

    exit 1
}
