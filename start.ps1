$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.python'
    $env:UV_PYTHON_BIN_DIR = Join-Path $PSScriptRoot '.python-bin'
    $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.uv-cache'
    & .\.venv\Scripts\python.exe app.py
    $appExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $appExitCode
