@echo off
cd /d %~dp0

set PYTHONW="%cd%\.venv\Scripts\pythonw.exe"

start "" %PYTHONW% "%cd%\runserver.py"

