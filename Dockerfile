# Base stage for Python dependencies
FROM python:3.13-slim AS python-base

WORKDIR /app
ENV PYTHONPATH=/app

COPY ./app/backend ./backend
COPY ./app/workers ./workers
COPY requirements.txt .

# Build stage for React frontend
FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY ./app/frontend/package*.json ./
RUN npm install
COPY ./app/frontend ./
RUN npm run build

# Final stage
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Install dependencies (including Xvfb and necessary fonts/libs)
RUN apt-get update && \
    apt-get install -y \
        ffmpeg \
        pciutils \
        rocm-smi \
        nginx \
        vainfo \
        xvfb \
        x11-utils \
        x11-xserver-utils \
        xauth \
        libx11-6 \
        libgl1 \
        fonts-dejavu-core \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=python-base /app/backend ./backend
COPY --from=python-base /app/workers ./workers
COPY --from=python-base /app/requirements.txt .
COPY --from=frontend-build /frontend/build ./frontend/build
COPY ./app/nginx/default.conf /etc/nginx/sites-available/default
COPY entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir -r requirements.txt && \
    chmod +x /entrypoint.sh

EXPOSE 8088

# Set DISPLAY so apps know where the fake X server is
ENV DISPLAY=:99

ENTRYPOINT ["/entrypoint.sh"]
