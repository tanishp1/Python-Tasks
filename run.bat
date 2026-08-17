@echo off
set PYTHON=C:\Users\pawar\AppData\Local\Python\pythoncore-3.14-64\python.exe

if "%1"=="pip" (
    %PYTHON% -m pip %2 %3 %4 %5
) else if "%1"=="run" (
    %PYTHON% %2
) else (
    echo Usage:
    echo   run.bat pip install ^<package^>
    echo   run.bat run ^<script.py^>
)
