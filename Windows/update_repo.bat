@echo off
:: Script to update the repository
:: Must be run from the Windows/ directory

cd /d "%~dp0.."

echo Updating repository...
git pull

echo Update complete.
pause
