#!/usr/bin/env bash
exec ./backend/venv/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
