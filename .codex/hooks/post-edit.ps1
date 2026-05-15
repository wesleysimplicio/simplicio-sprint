# PostToolUse hook for Python edits on Windows.
# Best effort: format/check only the edited file and never blocks the agent flow.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$FilePath = ''
)

$ErrorActionPreference = 'Continue'

$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($FilePath) -and -not [string]::IsNullOrWhiteSpace($payload)) {
    try {
        $json = $payload | ConvertFrom-Json
        if ($json.tool_input.file_path) {
            $FilePath = [string]$json.tool_input.file_path
        } elseif ($json.tool_input.path) {
            $FilePath = [string]$json.tool_input.path
        }
        if ($json.tool_response.success -eq $false) {
            exit 0
        }
    } catch {
        $FilePath = ''
    }
}

if ([string]::IsNullOrWhiteSpace($FilePath)) {
    exit 0
}
if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
    exit 0
}
if ([System.IO.Path]::GetExtension($FilePath).ToLowerInvariant() -ne '.py') {
    exit 0
}
if ($FilePath -match '(^|[\\/])(\.venv|venv|node_modules|dist|build|\.tox)([\\/]|$)') {
    exit 0
}

function Invoke-Ruff {
    param([string[]]$Arguments)

    $ruff = Get-Command ruff -ErrorAction SilentlyContinue
    if ($ruff) {
        & $ruff.Source @Arguments *> $null
        return
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command py -ErrorAction SilentlyContinue
    }
    if ($python) {
        & $python.Source -m ruff @Arguments *> $null
    }
}

Invoke-Ruff -Arguments @('format', $FilePath)
Invoke-Ruff -Arguments @('check', $FilePath, '--output-format=concise')

exit 0
