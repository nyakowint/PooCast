$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $buildPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $buildPython)) {
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            $env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '..\.build-tools\python'
            $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '..\.build-tools\cache'
            uv venv --python 3.13 --managed-python .venv
        } else {
            py -3.13 -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 or uv, then rerun this script.' }
    }

    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '..\.build-tools\cache'
        uv pip install --python $buildPython --only-binary :all: -r requirements-build.txt
    } else {
        & $buildPython -m pip install --only-binary :all: -r requirements-build.txt
    }
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

    & $buildPython -m PyInstaller --noconfirm --onefile --windowed `
        --name FlooCast --icon FlooCastApp.ico `
        --add-data 'FlooCastApp.ico:.' --add-data 'FlooCastApp.gif:.' `
        --add-data 'FlooCastHeader.png:.' --add-data 'onS.png:.' `
        --add-data 'offS.png:.' --add-data 'locales:locales' `
        --add-data 'LICENSE:.' main.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    Copy-Item -LiteralPath LICENSE -Destination dist\LICENSE.txt
    Copy-Item -LiteralPath README.md -Destination dist\README.md
    Write-Host "Built $PSScriptRoot\dist\FlooCast.exe"
} finally {
    Pop-Location
}
