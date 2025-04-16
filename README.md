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

---

## 🏗️ Architecture

```
/video-input/           => Input videos directory
/video-output/          => Optimized output videos
/data/video_db.sqlite   => SQLite database

📦 docker-compose.yml
├── backend/           => FastAPI server
│   ├── db.py          => DB setup
│   ├── main.py        => main entry point
│   └── routes.py      => API routes
├── workers/
│   ├── scanner.py     => Scans videos directory
│   ├── prepare.py     => Calls AI API
│   ├── processor.py   => Runs ffmpeg
│   ├── approver.py    => Auto approve to process and replace if set in ENV
│   └── mover.py       => Handles file replacement
├── frontend/          => React + Vite UI
├── nginx/             => Nginx configuration
│   └── default.conf   => Default nginx site config
└── entrypoint.sh/     => Entrypoint for docker container start
```

---

## ⚙️ Environment Variables (`.env`)

```env
VIDEO_DIR=/video-input
OUTPUT_DIR=/video-output
DB_PATH=/data/video_db.sqlite
SCAN_INTERVAL=30
FRONTEND_PORT=3000
OPENAI_API_KEY=your_api_key
AUTO_CONFIRMED=true/false
AUTO_ACCEPT=true/false
HOST_CPU_MODEL="$(lscpu | grep 'Model name' | awk -F ':' '{print $2}' | xargs)"
HOST_TOTAL_RAM="$(grep MemTotal /proc/meminfo | awk '{print $2}')"
HOST_GPU_MODEL="$(lspci | grep -E 'VGA|3D' | xargs)"
HOST_OS="$(uname -s)"
HOST_OS_VERSION="$(uname -r)"
```

---

## 🚀 Getting Started

### 1. Clone the Repo

```bash
git clone https://github.com/your/repo.git
cd video-optimizer
```

### 2. Add Videos

Place some `.mp4`, `.mov`, etc. files in the `videos/` folder.

### 3. Docker Compose YML File

```bash
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
      - <path-to-video-other-directory>:/video-input/other-directory
      - <path-to-video-output>:/video-output
    environment:
      - SCAN_INTERVAL=30 // in seconds
    ports:
      - "<PORT>:8088"

```

---

## 🌐 Access the App

- **Frontend UI:** By default, access the application at [http://localhost:8088](http://localhost:8088)
- **Custom Port:** To use a different port, modify the port mapping in your docker-compose.yml:
  ```yaml
  ports:
    - "your_port:8088"
  ```

---

## 👨‍💻 How It Works

1. **Scanner Worker**
   - Scans `VIDEO_DIR`
   - Adds file to SQLite with metadata (via `ffprobe`)
   - Sets status as `pending`

2. **React UI**
   - Lists all videos
   - User can accept/reject videos

3. **AI Optimizer Worker**
   - Sends accepted videos to AI API
   - Saves `ffmpeg` command
   - Status becomes `ready`

4. **Processor Worker**
   - Executes `ffmpeg` using saved command
   - Stores optimized file in `OUTPUT_DIR`
   - Marks status as `optimized`

5. **React UI (again)**
   - User can accept/reject optimized file
   - Accept → replace original
   - Reject → delete new file

---

## ✅ Video Status Flow

```text
pending → confirmed → ready → optimized → accepted → replaced/failed
         ↑    ↓          ↓           ↓           ↓
      rejected     (AI)   (ffmpeg)  (User)    (Mover)
```

---

## 🧠 Sample AI Response

```text
ffmpeg -i input.mp4 -vcodec libx265 -crf 28 output.mp4
```

---

## 🧪 Testing

- Add videos to `/videos`
- Accept from UI
- AI worker will provide command
- Processor will optimize and update UI
- Accept/reject final optimized file

---

## 🐛 Debugging

- Logs are available in each container
- Backend has Swagger API for manual testing
- DB stored at `/data/video_db.sqlite`

---

## 📦 Build Notes

- All code is modular and environment-driven
- Each component is Dockerized
- ffmpeg and ffprobe must be available in worker containers

---

## 📜 License

MIT — free to use and modify.

---

## 🙌 Credits

Built by Tinkeshwar Singh & ChatGPT 💡
