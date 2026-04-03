# 🎬 Automated Video Optimization System

This project automatically scans a directory for videos, extracts their metadata, allows users to approve them for optimization, uses AI to generate `ffmpeg` commands, and optimizes the video files — all inside Docker containers.

---

## 🧩 Features

- 🎞 Scan directories for video files
- 🧠 Use AI to generate ffmpeg compression commands
- ⚙️ ffmpeg optimization pipeline
- 📊 SQLite database to store video data
- 🌐 React dashboard for approvals
- 🐳 Fully containerized using Docker Compose
- 🖥️ Virtual display (Xvfb) for headless video processing
- 🔄 CI/CD with GitHub Actions and Docker Hub publishing

---

## 🏗️ Architecture

```
/video-input/              => Input videos directory
/video-output/             => Optimized output videos
/data/video_db.sqlite      => SQLite database

📦 Project Root
├── app/
│   ├── backend/              => FastAPI server
│   │   ├── db.py             => Core database connection handling
│   │   ├── db_operations.py  => High-level database operations
│   │   ├── main.py           => Main entry point
│   │   ├── routes.py         => API routes
│   │   └── utils.py          => Logging utilities
│   ├── workers/
│   │   ├── scanner.py        => Scans videos directory
│   │   ├── prepare.py        => Calls AI API
│   │   ├── processor.py      => Runs ffmpeg
│   │   ├── approver.py       => Auto approve if set in ENV
│   │   └── mover.py          => Handles file replacement
│   ├── frontend/             => React + Vite UI
│   └── nginx/
│       ├── default.conf      => Production nginx config
│       └── dev.conf          => Development nginx config (proxies to React dev server)
├── .github/workflows/
│   ├── docker-publish.yml       => Build & push on main (versioned + latest)
│   └── docker-publish-alpha.yml => Build & push on alpha branch
├── Dockerfile                => Production multi-stage build
├── Dockerfile.dev            => Development build (hot-reload)
├── docker-compose.dev.yml    => Dev compose with volume mounts
├── entrypoint.sh             => Production entrypoint
├── entrypoint.dev.sh         => Development entrypoint
└── requirements.txt          => Python dependencies
```

---

## ⚙️ Environment Variables (`.env`)

```env
VIDEO_DIR=/video-input
OUTPUT_DIR=/video-output
DB_PATH=/data/video_db.sqlite
SCAN_INTERVAL=30
OPENAI_API_KEY=<your_api_key>
AUTO_CONFIRMED=true/false
AUTO_ACCEPT=true/false
DB_TIMEOUT=30
DB_MAX_RETRIES=3
DB_RETRY_DELAY=0.1
PROCESS_RETRY_DELAY=30
```

---

## 🚀 Getting Started

### 1. Clone the Repo

```bash
git clone https://github.com/tinkeshwar/ai-video-optimizer.git
cd ai-video-optimizer
```

### 2. Add Videos

Place your video files (`.mp4`, `.mov`, `.avi`, etc.) in the input directory mapped to `/video-input`.

### 3. Using Docker Hub Image (Recommended)

The image is published to Docker Hub automatically. Create a `docker-compose.yml`:

```yaml
services:
  ai-video-optimizer-app:
    image: tinkeshwar/video-optimizer-ai:latest
    container_name: ai-video-optimizer
    env_file:
      - .env
    volumes:
      - <path-to-config>:/data
      - <path-to-video-directory>:/video-input
      - <path-to-video-output>:/video-output
    environment:
      - SCAN_INTERVAL=30
    ports:
      - "<PORT>:8088"
```

### 4. Building Locally

```yaml
services:
  ai-video-optimizer-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ai-video-optimizer
    env_file:
      - .env
    volumes:
      - <path-to-config>:/data
      - <path-to-video-directory>:/video-input
      - <path-to-video-output>:/video-output
    environment:
      - SCAN_INTERVAL=30
    ports:
      - "<PORT>:8088"
```

---

## 🛠️ Development Setup

A full development environment with hot-reload is available:

```bash
docker compose -f docker-compose.dev.yml up --build
```

This mounts source code as volumes so changes to backend, workers, and frontend are reflected immediately without rebuilding.

| Service   | URL                     |
|-----------|-------------------------|
| App (nginx) | http://localhost:8088 |
| Backend   | http://localhost:8000   |
| Frontend  | http://localhost:3000   |

---

## 🌐 Access the App

- **Frontend UI:** [http://localhost:8088](http://localhost:8088)
- **Custom Port:** Modify the port mapping in your `docker-compose.yml`:
  ```yaml
  ports:
    - "your_port:8088"
  ```

---

## 👨‍💻 How It Works

1. **Scanner Worker** — Scans `VIDEO_DIR`, extracts metadata via `ffprobe`, adds to SQLite as `pending`
2. **React UI** — Lists all videos, user can accept/reject
3. **AI Optimizer Worker** — Sends accepted videos to OpenAI API, saves generated `ffmpeg` command, status becomes `ready`
4. **Processor Worker** — Executes `ffmpeg` command, stores optimized file in `OUTPUT_DIR`, marks as `optimized`
5. **React UI** — User accepts/rejects optimized file (accept → replace original, reject → delete)
6. **Mover Worker** — Replaces original file with optimized version

---

## ✅ Video Status Flow

```text
pending → confirmed → ready → optimized → accepted → replaced/failed
            ↑    ↓       ↓         ↓          ↓
         rejected   (AI)   (ffmpeg)  (User)   (Mover)
```

---

## 🧠 Sample AI Response

```text
ffmpeg -i input.mp4 -vcodec libx265 -crf 28 output.mp4
```

---

## 🗄️ Database Concurrency Handling

The system uses SQLite with WAL mode and enhanced concurrency support for multiple workers:

- 📝 Write-Ahead Logging (WAL) mode
- 🔄 Connection pooling with configurable timeouts
- 🔒 Thread-safe operations with automatic retry on locks
- 🔁 Exponential backoff for retries

---

## 🔄 CI/CD

GitHub Actions workflows automatically build and push Docker images:

- **main branch** → `tinkeshwar/video-optimizer-ai:latest` + auto-versioned tag (e.g., `1.0.42`)
- **alpha branch** → `tinkeshwar/video-optimizer-ai:alpha`

Releases are auto-created on the main branch with incremented patch versions.

---

## 📦 Build Notes

- Multi-stage Docker build (Python base → Node frontend build → final image)
- Xvfb virtual display included for headless video processing
- ffmpeg, ffprobe, vainfo, and GPU tools (pciutils, rocm-smi) available in container
- Nginx reverse proxy serves frontend and proxies `/api/` to FastAPI backend

---

## 📜 License

MIT — free to use and modify.

---

## 🙌 Credits

Built by Tinkeshwar Singh & ChatGPT 💡
