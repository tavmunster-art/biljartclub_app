@echo off
setlocal

cd /d "%~dp0"

python -m PyInstaller --version >nul 2>&1 || (
    echo PyInstaller is required in the active Python environment. Install it with: python -m pip install pyinstaller
    exit /b 1
)

set "ISCC_CMD=iscc"
where iscc >nul 2>&1 || (
    if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
        set "ISCC_CMD=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
    ) else (
        echo Inno Setup Compiler is required.
        exit /b 1
    )
)

if not exist "app\templates" (
    echo Application source was not found.
    exit /b 1
)

python -m PyInstaller --clean --noconfirm BiljartclubApp.spec || exit /b 1
copy /y setup_windows.ps1 dist\BiljartClubApp\setup_windows.ps1 >nul || exit /b 1
"%ISCC_CMD%" installer.iss || exit /b 1

echo Windows installer created in installer\BiljartClubSetup.exe
endlocal