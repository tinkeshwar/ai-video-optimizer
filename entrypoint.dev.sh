#!/bin/bash
set -e

# Verify dependencies
command -v ffmpeg >/dev/null 2>&1 || { echo "Error: ffmpeg not found"; exit 1; }
command -v nginx >/dev/null 2>&1 || { echo "Error: nginx not found"; exit 1; }
command -v uvicorn >/dev/null 2>&1 || { echo "Error: uvicorn not found"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Error: node not found"; exit 1; }

# Verify worker scripts
for script in scanner.py prepare.py processor.py mover.py; do
    if [ ! -f "workers/$script" ]; then
        echo "Error: workers/$script not found!"
        exit 1
    fi
done

# Handle shutdown
trap 'echo "Shutting down..."; kill $(jobs -p) 2>/dev/null; wait' SIGTERM SIGINT

# Install frontend dependencies if needed
if [ ! -d "/app/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd /app/frontend && npm install)
fi

# Start backend with hot-reload
echo "Starting backend (dev mode with reload)..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/backend &
sleep 3

# Start virtual X server
echo "Starting virtual X server on DISPLAY $DISPLAY..."
Xvfb :99 -screen 0 1280x720x24 &
sleep 2

# Start workers
echo "Starting workers..."
python workers/scanner.py &
python workers/prepare.py &
python workers/processor.py &
python workers/mover.py &
python workers/approver.py &

# Start React dev server
echo "Starting frontend dev server on port 3000..."
(cd /app/frontend && PORT=3000 npm start) &

# Start nginx (proxies to both backend and frontend)
echo "Starting nginx..."
nginx -g "daemon off;" &

echo ""
echo "========================================="
echo "  App:      http://localhost:8088"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "========================================="
echo ""

wait
