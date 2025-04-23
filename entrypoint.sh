#!/bin/bash

# Exit on error
set -e

# Verify dependencies
command -v ffmpeg >/dev/null 2>&1 || { echo "Error: ffmpeg not found"; exit 1; }
command -v nginx >/dev/null 2>&1 || { echo "Error: nginx not found"; exit 1; }
command -v uvicorn >/dev/null 2>&1 || { echo "Error: uvicorn not found"; exit 1; }

# Verify worker scripts
for script in scanner.py prepare.py processor.py mover.py; do
    if [ ! -f "workers/$script" ]; then
        echo "Error: workers/$script not found!"
        exit 1
    fi
done

# Handle shutdown
trap 'echo "Shutting down..."; kill $(jobs -p); wait' SIGTERM

# Start backend
echo "Starting backend..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 5

# Start virtual X server
echo "Starting virtual X server on DISPLAY $DISPLAY..."
Xvfb :99 -screen 0 1280x720x24 &
# Small sleep to give Xvfb time to initialize
sleep 5

# Start workers
echo "Starting scanner..."
python workers/scanner.py &

echo "Starting prepare..."
python workers/prepare.py &

echo "Starting processor..."
python workers/processor.py &

echo "Starting mover..."
python workers/mover.py &

echo "Starting approver..."
python workers/approver.py &

echo "Starting nginx..."
nginx -g "daemon off;" &

# Wait for all background jobs
wait