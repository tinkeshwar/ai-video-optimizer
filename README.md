# 🎬 Automated Video Optimization System

This project automatically scans a directory for videos, extracts their metadata, allows users to approve them for optimization, uses AI to generate `ffmpeg` commands, and optimizes the video files — all inside Docker containers.

---

## 🧩 Features

- 🎞 Scan directories for video files (`.mp4`, `.mkv`, `.avi`, `.mov`)
- 🧠 AI-powered ffmpeg command generation using OpenAI (system + user prompt architecture)
- ⚙️ ffmpeg optimization pipeline with progress tracking and smart abort
- 📊 SQLite database with WAL mode and concurrent worker support
- 🌐 React dashboard for approvals, stream selection, and monitoring
- 🎧 Per-video audio/subtitle stream selection before optimization
- 🔁 Automatic retry with re-optimized commands when output is too large
- 🤖 Optional auto-confirm and auto-accept modes
- 🐳 Fully containerized using Docker Compose
- 🖥️ Virtual display (Xvfb) for headless video processing
- 🔄 CI/CD with GitHub Actions and Docker Hub publishing
- 🔧 Parallel processing workers (configurable)

---

## 🏗️ Architecture

```
/video-input/              => Input videos directory
/video-output/             => Optimized output videos
/data/video_db.sqlite      => SQLite database
/data/system_prompt.txt    => (Optional) AI system prompt override
/data/user_prompt.txt      => (Optional) AI user prompt override
/data/retry_prompt.txt     => (Optional) AI retry prompt override

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
│   │   ├── prepare.py        => AI command generation (system + user prompts)
│   │   ├── processor.py      => Runs ffmpeg with progress tracking
│   │   ├── approver.py       => Auto confirm/accept if enabled
│   │   └── mover.py          => Handles file replacement
│   ├── frontend/             => React + Vite UI
│   └── nginx/
│       ├── default.conf      => Production nginx config
│       └── dev.conf          => Development nginx config
├── .github/workflows/
│   ├── docker-publish.yml       => Build & push on main (versioned + latest)
│   └── docker-publish-alpha.yml => Build & push on alpha (manual trigger)
├── Dockerfile                => Production multi-stage build
├── Dockerfile.dev            => Development build (hot-reload)
├── docker-compose.dev.yml    => Dev compose with volume mounts
├── entrypoint.sh             => Production entrypoint
├── entrypoint.dev.sh         => Development entrypoint
└── requirements.txt          => Python dependencies
```

---

## ⚙️ Environment Variables

### Required

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key for AI command generation |

### Application

| Variable | Default | Description |
|---|---|---|
| `VIDEO_DIR` | `/video-input` | Directory to scan for input videos |
| `OUTPUT_DIR` | `/video-output` | Directory for optimized output files |
| `DB_PATH` | `/data/video_db.sqlite` | SQLite database file path |
| `SCAN_INTERVAL` | `30` | Seconds between directory scans |
| `FILE_STABILITY_DELAY` | `2` | Seconds to wait for file size stability check |

### AI Configuration

| Variable | Default | Description |
|---|---|---|
| `AI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `AI_BATCH_SIZE` | `3` | Number of videos to process per AI batch |
| `AI_INTERVAL` | `10` | Seconds between AI processing cycles |

### Processing

| Variable | Default | Description |
|---|---|---|
| `PARALLEL_WORKERS` | `1` | Number of parallel ffmpeg workers |
| `PROCESS_RETRY_DELAY` | `30` | Seconds to wait after a processing failure |
| `MIN_REDUCTION_RATIO` | `0.2` | Minimum compression ratio (20%) before aborting |
| `SIZE_STABILITY_TOLERANCE` | `0.01` | Size estimation stability tolerance (1%) |
| `SIZE_CHECK_WINDOW` | `10` | Number of progress lines to check for size stability |
| `MAX_CONSECUTIVE_ERRORS` | `3` | Max errors before a worker stops |
| `SLEEP_INTERVAL` | `10` | Seconds between worker polling cycles |
| `MAX_RETRY_DELAY` | `300` | Maximum backoff delay in seconds |

### Automation

| Variable | Default | Description |
|---|---|---|
| `AUTO_CONFIRMED` | `false` | Auto-confirm pending videos with single audio stream |
| `AUTO_ACCEPT` | `false` | Auto-accept optimized videos |
| `CONFIRM_BATCH_SIZE` | `10` | Batch size for auto-confirm/accept |
| `CONFIRM_INTERVAL` | `60` | Seconds between auto-confirm/accept cycles |

### File Replacement

| Variable | Default | Description |
|---|---|---|
| `REPLACE_BATCH_SIZE` | `5` | Batch size for file replacement |
| `REPLACE_INTERVAL` | `10` | Seconds between replacement cycles |

### Database

| Variable | Default | Description |
|---|---|---|
| `DB_TIMEOUT` | `30` | SQLite connection timeout in seconds |
| `DB_MAX_RETRIES` | `3` | Max retries on database lock |
| `DB_RETRY_DELAY` | `0.1` | Base delay between retries in seconds |

### Example `.env`

```env
VIDEO_DIR=/video-input
OUTPUT_DIR=/video-output
DB_PATH=/data/video_db.sqlite
SCAN_INTERVAL=30
OPENAI_API_KEY=<your_api_key>
AI_MODEL=gpt-4o-mini
AUTO_CONFIRMED=false
AUTO_ACCEPT=false
PARALLEL_WORKERS=2
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

Place your video files (`.mp4`, `.mov`, `.avi`, `.mkv`) in the input directory mapped to `/video-input`.

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

| Service | URL |
|---|---|
| App (nginx) | http://localhost:8088 |
| Backend (FastAPI) | http://localhost:8000 |
| Frontend (React dev) | http://localhost:3000 |

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

### Workers

| Worker | File | Description |
|---|---|---|
| Scanner | `scanner.py` | Scans `VIDEO_DIR` recursively, extracts metadata via `ffprobe`, detects audio/subtitle streams, inserts into SQLite as `pending` |
| Approver | `approver.py` | Auto-confirms single-audio pending videos and auto-accepts optimized videos (when `AUTO_CONFIRMED`/`AUTO_ACCEPT` are enabled) |
| Prepare | `prepare.py` | Sends confirmed videos to OpenAI with system + user prompts, saves generated `ffmpeg` command, status becomes `ready` |
| Processor | `processor.py` | Claims ready videos atomically, executes `ffmpeg` with real-time progress tracking, smart abort if output exceeds original size or reduction ratio is too low |
| Mover | `mover.py` | Replaces original files with optimized versions for accepted videos, cleans up skipped files |

### Processing Pipeline

1. **Scanner** — Discovers new video files, extracts metadata and stream info
2. **React UI** — User reviews pending videos, selects audio/subtitle streams, confirms or rejects
3. **Prepare (AI)** — Generates optimized `ffmpeg` command using OpenAI
4. **Processor** — Executes `ffmpeg` with progress tracking and smart abort
5. **React UI** — User reviews optimized result, accepts or skips
6. **Mover** — Replaces original file with optimized version

### Smart Abort

The processor automatically aborts encoding when:
- Estimated output size exceeds the original file size
- Estimated compression ratio falls below the configured threshold (`MIN_REDUCTION_RATIO`)
- Size estimation has stabilized (checked over `SIZE_CHECK_WINDOW` progress lines)

Aborted videos are automatically re-queued as `re-confirmed` for AI to generate a more aggressive command.

---

## ✅ Video Status Flow

```text
pending → confirmed → ready → processing → optimized → accepted → replaced
  │          │                     │            │
  ├→ rejected (user)               │            ├→ skipped (user)
  ├→ replaced (mark complete)      │            │
  │                                ├→ failed    │
  │                                │            │
  │                          re-confirmed ──→ ready (AI retry)
  │                          (smart abort)
```

### Status Descriptions

| Status | Description |
|---|---|
| `pending` | Newly scanned, awaiting user confirmation |
| `confirmed` | User confirmed, awaiting AI command generation |
| `ready` | AI command generated, queued for processing |
| `processing` | ffmpeg currently running |
| `optimized` | Processing complete, awaiting user review |
| `accepted` | User accepted, awaiting file replacement |
| `replaced` | Original file replaced with optimized version (complete) |
| `rejected` | User rejected from pending |
| `skipped` | User skipped optimized result |
| `failed` | Processing or replacement failed |
| `re-confirmed` | Auto re-queued after smart abort for AI retry |

### UI Tab Order

Pending → Queued → Processing → Optimized → Completed → Rejected → Skipped → Failed → Confirmed

---

## 🎧 Audio & Subtitle Stream Selection

The scanner extracts all audio and subtitle streams from each video during scan and stores them as structured JSON. On the pending screen, each video is color-coded by its stream complexity:

| Indicator | Condition | Auto-approve | Action on confirm |
|---|---|---|---|
| ⚪ Single Audio-Single Sub | Single audio, 0–1 subtitle | ✅ Yes | Auto-selects audio, removes subtitles |
| 🟢 Single Audio-Multi Sub | Single audio, 2+ subtitles | ✅ Yes | Opens stream selection dialog |
| 🟡 Multi Audio-Single Sub | Multiple audio, 0–1 subtitle | ❌ No | Opens stream selection dialog |
| 🔴 Multi Audio-Multi Sub | Multiple audio, 2+ subtitles | ❌ No | Opens stream selection dialog |

- Row background and filename text are tinted to match the tier color
- A **Stream Tier** filter dropdown on the pending tab allows filtering by tier
- The stream selection dialog requires one audio stream (mandatory) and optionally one subtitle stream — no subtitle selection means all subtitles are removed during conversion
- **Bulk confirm** only processes single-audio videos (⚪ and 🟢); multi-audio videos (🟡 and 🔴) are skipped with a notification
- **Auto-confirm** (`AUTO_CONFIRMED=true`) only applies to single-audio videos — multi-audio videos always require manual selection

All non-pending tabs display the user's selected audio and subtitle streams in dedicated columns.

---

## 🧠 AI Prompt Customization

The AI command generator uses separate **system** and **user** prompts with a retry instruction for re-optimization. All three have sensible hardcoded defaults and can be overridden by placing text files in the `/data` volume:

| File | Purpose |
|---|---|
| `/data/system_prompt.txt` | Override the AI's role, rules, and system context |
| `/data/user_prompt.txt` | Override the per-video task instructions |
| `/data/retry_prompt.txt` | Override the retry optimization instructions |

If the files don't exist or are empty, built-in defaults are used.

### Placeholder Substitution

All prompt files support placeholder substitution:

| Placeholder | Replaced With | Available In |
|---|---|---|
| `{{FFPROBE_DATA}}` | Video ffprobe metadata (JSON) | system, user, retry |
| `{{SYSTEM_INFO}}` | Host system info (JSON) | system, user, retry |
| `{{SELECTED_AUDIO}}` | User-selected audio stream | system, user, retry |
| `{{SELECTED_SUBTITLE}}` | User-selected subtitle stream | system, user, retry |
| `{{PREVIOUS_COMMAND}}` | Previous AI command (on retry) | system, user, retry |
| `{{RETRY_INSTRUCTION}}` | Resolved retry prompt block (on retry, empty otherwise) | system, user |

### How Prompts Are Resolved

```
1. Load system_prompt.txt (or fallback) → substitute placeholders → system message
2. Load user_prompt.txt (or fallback)   → substitute placeholders → user message
3. On retry: load retry_prompt.txt (or fallback) → substitute {{PREVIOUS_COMMAND}}
             → result injected into {{RETRY_INSTRUCTION}} placeholder
```

### Sample Override: `/data/user_prompt.txt`

```text
Video metadata: {{FFPROBE_DATA}}
Audio: {{SELECTED_AUDIO}}
Subtitle: {{SELECTED_SUBTITLE}}
Generate an optimized ffmpeg command using x265 with CRF 24.
{{RETRY_INSTRUCTION}}
```

### Sample AI Response

```text
ffmpeg -y -i input.mp4 -c:v libx265 -crf 24 -map 0:v:0 -map 0:a:0 -c:a copy -sn -movflags +faststart output.mp4
```

---

## 🗄️ Database

### Concurrency Handling

The system uses SQLite with WAL mode and enhanced concurrency support for multiple workers:

- 📝 Write-Ahead Logging (WAL) mode for concurrent reads/writes
- 🔄 Connection pooling with configurable timeouts
- 🔒 Thread-safe operations with automatic retry on locks
- 🔁 Exponential backoff for retries
- ⚡ Atomic video claiming to prevent duplicate processing

### Tables

| Table | Purpose |
|---|---|
| `videos` | Stores video metadata, status, AI commands, stream selections, and optimization results |
| `status_history` | Audit log of all status transitions with timestamps and comments |

---

## 🔄 CI/CD

GitHub Actions workflows automatically build and push Docker images:

| Branch/Trigger | Image Tag | Description |
|---|---|---|
| Push to `main` | `latest` + auto-versioned (e.g., `1.0.42`) | Production release with auto-generated release notes |
| Manual dispatch | `alpha` | Alpha/testing builds |

Version bumping follows conventional commits:
- `BREAKING CHANGE:` or `feat!:` → major bump
- `feat:` → minor bump
- Everything else → patch bump

---

## 📦 Build Notes

- Multi-stage Docker build (Python base → Node frontend build → final image)
- Xvfb virtual display included for headless video processing
- ffmpeg, ffprobe, vainfo, and GPU tools (pciutils, rocm-smi) available in container
- Nginx reverse proxy serves frontend static files and proxies `/api/` to FastAPI backend
- Development build includes Node.js for React dev server with hot-reload
- Python dependencies: `fastapi`, `uvicorn`, `python-dotenv`, `openai`, `pydantic`

---

## 📜 License

MIT — free to use and modify.

---

## 🙌 Credits

Built by Tinkeshwar Singh & ChatGPT 💡
