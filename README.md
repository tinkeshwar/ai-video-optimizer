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
├── workers/
│   ├── scanner.py     => Scans videos directory
│   ├── prepare.py     => Calls AI API
│   ├── processor.py   => Runs ffmpeg
│   └── mover.py       => Handles file replacement
├── frontend/          => React + Vite UI
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

### 3. Start Services

```bash
docker-compose up --build
```

---

## 🌐 Access the App

- **Frontend UI:** [http://localhost:3000](http://localhost:3000)

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