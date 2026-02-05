@echo off
REM GitMax Quick Start - Process ALL F:\study (15,854 directories)
REM Zero exclusions - Every file syncs!

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    GitMax v2.0                               ║
echo ║            ZERO EXCLUSIONS - All Files Sync                  ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  Directories:  15,854                                        ║
echo ║  Workers:      15 (GitHub rate-limit safe)                   ║
echo ║  Est. Time:    3-4 hours                                     ║
echo ║  LFS Files:    65 (auto-handled)                             ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo Press Ctrl+C to cancel, or any key to START...
pause >nul

echo.
echo Starting GitMax...
echo.

python "%~dp0gitmax.py" -f "%~dp0study_paths.txt" -w 15

echo.
echo Done! Check the results above.
pause
