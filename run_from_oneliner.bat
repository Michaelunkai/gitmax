@echo off
REM GitMax - Process from the gitit one-liner file
REM This processes all paths from the one-liner file

set ONELINER_FILE=C:\Users\micha\.openclaw\workspace\gitit_oneliner.txt

if not exist "%ONELINER_FILE%" (
    echo One-liner file not found: %ONELINER_FILE%
    exit /b 1
)

echo.
echo Processing directories from one-liner file...
echo.

python "%~dp0gitmax.py" -f "%ONELINER_FILE%" -w 30
