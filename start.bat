@echo off
cd /d %~dp0
uv sync
uv run uvicorn app.main:app --port 8765 --host 127.0.0.1
pause
