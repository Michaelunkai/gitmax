@echo off
REM GitMax - Process entire F:\study folder
REM This will push ~15,000 directories to GitHub!

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  WARNING: This will push ~15,000 directories to GitHub!      ║
echo ║  Make sure you're ready for this!                            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo Press Ctrl+C to cancel, or any key to continue...
pause >nul

python "%~dp0gitmax.py" -d "F:\study" -w 30 --depth 20
