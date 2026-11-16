#!/usr/bin/env bash

# AKSHARA VAULT - Unified Runner Script
# Sets up environment, starts FastAPI backend on http://127.0.0.1:8000,
# and automatically opens frontend/index.html in the default browser.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================================="
echo "   AKSHARA VAULT — SOVEREIGN SECURE DOCUMENT PLATFORM     "
echo "=========================================================="

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo "[!] Error: python3 is required but not installed."
    exit 1
fi

# Ensure virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "[*] Initializing Python virtual environment in backend/venv..."
    python3 -m venv backend/venv
    ./backend/venv/bin/pip install --upgrade pip
    ./backend/venv/bin/pip install -r backend/requirements.txt
fi

# Clear any existing process holding port 8000
EXISTING_PID=$(fuser 8000/tcp 2>/dev/null | awk '{print $1}' || true)
if [ -n "$EXISTING_PID" ]; then
    echo "[*] Clearing existing process on port 8000 (PID: $EXISTING_PID)..."
    kill -9 "$EXISTING_PID" 2>/dev/null || true
    sleep 0.5
fi

# Start FastAPI backend server in background
echo "[*] Launching Akshara Vault Backend API on http://127.0.0.1:8000..."
./backend/venv/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Trap signals to cleanly shut down backend when exiting
cleanup() {
    echo ""
    echo "[*] Shutting down Akshara Vault backend (PID: $BACKEND_PID)..."
    kill -TERM "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for backend to be fully responsive
echo "[*] Checking backend health..."
MAX_RETRIES=15
COUNTER=0
while [ $COUNTER -lt $MAX_RETRIES ]; do
    if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
        echo "[+] Backend is ONLINE and healthy!"
        break
    fi
    sleep 0.5
    COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq $MAX_RETRIES ]; then
    echo "[!] Warning: Backend took longer than expected to report healthy, continuing..."
fi

# Open frontend/index.html in default browser
echo "[*] Launching frontend in default browser..."
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open "$PROJECT_DIR/frontend/index.html" >/dev/null 2>&1 &
    elif command -v open &> /dev/null; then
        open "$PROJECT_DIR/frontend/index.html" >/dev/null 2>&1 &
    fi
fi
echo "[+] Frontend accessible at: http://127.0.0.1:8000/index.html (or file://$PROJECT_DIR/frontend/index.html)"

echo "=========================================================="
echo "   AKSHARA VAULT RUNNING. Press Ctrl+C to terminate.      "
echo "=========================================================="

wait $BACKEND_PID
