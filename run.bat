@echo off
REM GitMax - Ultra-Fast Parallel GitHub Pusher
REM Usage: run.bat <directory> [workers]

set DIR=%1
set WORKERS=%2

if "%DIR%"=="" (
    echo Usage: run.bat ^<directory^> [workers]
    echo Example: run.bat F:\study 30
    exit /b 1
)

if "%WORKERS%"=="" set WORKERS=30

python "%~dp0gitmax.py" -d "%DIR%" -w %WORKERS%
