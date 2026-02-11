@echo off
:: Script to clean the log file runserver_silent.log
:: Must be run from the Windows/ directory

:: Navigate to project root
cd /d "%~dp0.."

:: Clear the log file
type nul > runserver_silent.log

echo Log file runserver_silent.log has been cleaned.
pause
