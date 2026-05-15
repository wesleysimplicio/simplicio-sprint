# PreToolUse hook for git commit on Windows.
# Blocks only when staged Python changes fail the local Python quality gate.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = ''
)

$ErrorActionPreference = 'Continue'

$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($Command) -and -not [string]::IsNullOrWhiteSpace($payload)) {
    try {
        $json = $payload | ConvertFrom-Json
        if ($json.tool_input.command) {
            $Command = [string]$json.tool_input.command
        }
    } catch {
        $Command = ''
    }
}

if (-not [string]::IsNullOrWhiteSpace($Command)) {
    if ($Command -notmatch 'git\s+commit') {
        exit 0
    }
    if ($Command -match '--no-verify|git\s+commit\s+--amend|git\s+commit\s+-m\s+"Merge') {
        exit 0
    }
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
    exit 0
}
Set-Location -LiteralPath $repoRoot

$stagedPythonFiles = @(
    & git diff --cached --name-only --diff-filter=ACMR |
        Where-Object { $_.ToLowerInvariant().EndsWith('.py') -and (Test-Path -LiteralPath $_ -PathType Leaf) }
)

if ($stagedPythonFiles.Count -eq 0) {
    exit 0
}

function Invoke-PythonTool {
    param(
        [string]$Executable,
        [string]$Module,
        [string[]]$Arguments
    )

    $tool = Get-Command $Executable -ErrorAction SilentlyContinue
    if ($tool) {
        $process = Start-Process -FilePath $tool.Source -ArgumentList $Arguments -NoNewWindow -Wait -PassThru
        return $process.ExitCode
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $python) {
        return $null
    }

    $pythonArgs = @('-m', $Module) + $Arguments
    $process = Start-Process -FilePath $python.Source -ArgumentList $pythonArgs -NoNewWindow -Wait -PassThru
    return $process.ExitCode
}

$failed = New-Object System.Collections.Generic.List[string]

$ruffArgs = @('check') + $stagedPythonFiles + @('--select', 'E9,F63,F7,F82', '--output-format=concise')
$ruffExit = Invoke-PythonTool -Executable 'ruff' -Module 'ruff' -Arguments $ruffArgs
if ($null -eq $ruffExit) {
    Write-Error '[pre-commit] ruff nao encontrado; lint Python pulado.'
} elseif ($ruffExit -ne 0) {
    $failed.Add('ruff critical check')
}

$pytestExit = Invoke-PythonTool -Executable 'pytest' -Module 'pytest' -Arguments @('tests', '-q')
if ($null -eq $pytestExit) {
    Write-Error '[pre-commit] pytest nao encontrado; testes Python pulados.'
} elseif ($pytestExit -ne 0) {
    $failed.Add('pytest tests -q')
}

if ($failed.Count -gt 0) {
    $reason = 'pre-commit bloqueado: ' + ($failed -join ', ') + ' falhou. Corrija antes do commit ou use --no-verify conscientemente.'
    @{ decision = 'block'; reason = $reason } | ConvertTo-Json -Compress
    exit 0
}

exit 0
