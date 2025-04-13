#!/bin/bash

# Load environment variables
source .env

# Start backend
echo "Starting backend..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Start workers
echo "Starting scanner..."
python workers/scanner.py &

echo "Starting prepare..."
python workers/prepare.py &

echo "Starting processor..."
python workers/processor.py &

echo "Starting mover..."
python workers/mover.py &

# Start frontend
echo "Serving frontend..."
serve -s frontend/build -l 3000 &

# Wait for all background jobs
wait
