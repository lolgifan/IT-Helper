@echo off
echo ============================================
echo    IT Helper - Build Script
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

:: Check if we're in the right directory
if not exist "..\src\main.py" (
    echo ERROR: main.py not found in src directory
    echo Please run this script from the build_tools directory
    pause
    exit /b 1
)

:: Install PyInstaller if not already installed
echo Checking for PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install PyInstaller
)

:: Run the build script
echo.
echo Starting build process...
echo.
python build.py

:: Check if build was successful
if exist "..\dist\IT Helper.exe" (
    echo.
    echo ============================================
    echo    BUILD SUCCESSFUL!
    echo ============================================
    echo.
    echo Your executable is ready at: ..\dist\IT Helper.exe
    echo.
    echo Would you like to run it now? (Y/N)
    set /p run_now=
    if /i "%run_now%"=="Y" (
        start "" "..\dist\IT Helper.exe"
    )
) else (
    echo.
    echo ============================================
    echo    BUILD FAILED!
    echo ============================================
    echo Please check the error messages above
)

echo.
echo Press any key to exit...
pause >nul 