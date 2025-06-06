@echo off
echo ============================================
echo    IT Helper - Build Launcher
echo ============================================
echo.
echo Launching build process...
echo.

cd build_tools
call build.bat
cd ..

echo.
echo Build process completed.
pause 