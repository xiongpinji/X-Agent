@echo off
REM Git Flow Setup Script for X-Agent Project
REM This script initializes the Git repository and sets up the branch structure

cd /d "D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划"

echo Running Git Flow Setup...
python git_normalization.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Git setup completed successfully!
    pause
) else (
    echo.
    echo Git setup failed with error code %ERRORLEVEL%
    pause
)
