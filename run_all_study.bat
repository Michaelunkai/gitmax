@echo off
REM GitMax - Process ALL F:\study directories (15,854 dirs)
REM Uses the pre-extracted paths file

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  GitMax - Processing F:\study (15,854 directories)           ║
echo ║  Estimated time: ~2-3 hours with 30 workers                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo Press Ctrl+C to cancel, or any key to continue...
pause >nul

python "%~dp0gitmax.py" -f "%~dp0study_paths.txt" -w 30
