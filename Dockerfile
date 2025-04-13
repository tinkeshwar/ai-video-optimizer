# Base stage for Python dependencies
FROM python:3.11-slim AS python-base

WORKDIR /app

# Copy backend and workers
COPY ./app/backend ./backend
COPY ./app/workers ./workers
COPY requirements.txt .

# Install dependencies
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean && \
    pip install --no-cache-dir -r requirements.txt

# Build stage for React frontend
FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY ./app/frontend/package*.json ./
RUN npm install

COPY ./app/frontend ./
RUN npm run build

# Final stage
FROM python:3.11-slim

# Install ffmpeg and serve
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean && \
    pip install fastapi uvicorn python-dotenv openai && \
    apt-get install -y curl && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && npm install -g serve

# Setup directories
WORKDIR /app
COPY --from=python-base /app /app
COPY --from=frontend-build /frontend/build ./frontend/build
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
EXPOSE 3000

ENTRYPOINT ["/entrypoint.sh"]
