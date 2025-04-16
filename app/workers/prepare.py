#!/usr/bin/env python3

import json
import os
import platform
import subprocess
import time
from contextlib import contextmanager
from sqlite3 import Row, connect
from typing import Dict, List, Optional
import re

from openai import OpenAI

# Environment Config
DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", 3))
AI_INTERVAL = int(os.getenv("AI_INTERVAL", 10))

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

@contextmanager
def get_db():
    conn = connect(DB_PATH)
    conn.row_factory = Row
    try:
        yield conn
    finally:
        conn.close()

def get_system_info() -> Dict[str, str]:
    info = {
        "OS": os.getenv("HOST_OS", platform.system()),
        "OS_Version": os.getenv("HOST_OS_VERSION", platform.version()),
        "Architecture": platform.machine(),
        "Processor": os.getenv("HOST_CPU_MODEL", platform.processor()),
        "Total_RAM_kB": os.getenv("HOST_TOTAL_RAM", "Unknown"),
        "Python_Version": platform.python_version(),
    }

    # GPU from ENV if available
    env_gpu = os.getenv("HOST_GPU_MODEL")
    if env_gpu:
        info["GPU"] = f"Host GPU: {env_gpu}"
        return info

    # Try NVIDIA GPU detection
    try:
        gpu_info = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        if gpu_info:
            info["GPU"] = f"NVIDIA GPU: {gpu_info}"
            return info
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Try AMD ROCm GPU detection
    try:
        gpu_info = subprocess.check_output(
            ["rocm-smi", "--showproductname"],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        if gpu_info:
            info["GPU"] = f"AMD GPU (ROCm): {gpu_info}"
            return info
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Try VAAPI detection
    try:
        vainfo = subprocess.check_output(["vainfo"], stderr=subprocess.DEVNULL, text=True)
        if "VAProfile" in vainfo:
            info["GPU_Acceleration"] = "VAAPI available"
    except FileNotFoundError:
        info["GPU_Acceleration"] = "vainfo not installed"
    except subprocess.SubprocessError:
        info["GPU_Acceleration"] = "vainfo failed"

    # lspci fallback
    if platform.system().lower() == "linux":
        try:
            lspci_output = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
            amd_lines = [line for line in lspci_output.splitlines() if "AMD" in line or "ATI" in line]
            nvidia_lines = [line for line in lspci_output.splitlines() if "NVIDIA" in line]
            if amd_lines:
                info["GPU"] = f"AMD GPU detected via lspci: {amd_lines[0]}"
            elif nvidia_lines:
                info["GPU"] = f"NVIDIA GPU detected via lspci: {nvidia_lines[0]}"
            else:
                info["GPU"] = "No discrete GPU detected via lspci"
        except (subprocess.SubprocessError, FileNotFoundError):
            info["GPU"] = "Could not detect GPU (lspci failed)"
    else:
        info["GPU"] = "GPU detection not supported on this OS without NVIDIA or ROCm tools"

    return info


def get_confirmed_videos(limit: int) -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM videos WHERE status = 'confirmed' LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

def send_to_ai(ffprobe_data: Dict, system_info: Dict) -> Optional[str]:
    prompt = f"""
        Here is the metadata of a video file:
        ffprobe data: {json.dumps(ffprobe_data, indent=2)}

        System info: {json.dumps(system_info, indent=2)}

        Your task is to generate the most optimal ffmpeg command to compress this video with the following requirements:

            - Prioritize significant space savings while preserving visual quality.
            - Use the **x265** codec if supported.
            - Maintain the original **resolution** and **frame rate** exactly.
            - Use **hardware acceleration** (e.g., NVENC, VAAPI, or QSV) if available in system_info.
            - Avoid lossless mode, but keep compression visually lossless (e.g., CRF 22 or better).
            - Audio should be copied without re-encoding.
            - The result should be web-streaming friendly (i.e., add `-movflags +faststart`).
            - Only return a single-line ffmpeg command starting with `ffmpeg`.
            - Use `input.mp4` as input and `output.mp4` as output.
            - No extra explanation or formatting.
            - In file exist in output command should overwrite the file.

        Make sure the command is ready for use in `subprocess.run(command.split())` in Python.
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a video processing expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AI Error] {str(e)}")
        return None

def update_video(video_id: int, command: str) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE videos SET ai_command = ?, status = 'ready' WHERE id = ?",
            (command, video_id)
        )
        conn.commit()

def process_batch():
    videos = get_confirmed_videos(AI_BATCH_SIZE)
    if not videos:
        print("No confirmed videos to process.")
        return

    system_info = get_system_info()

    for video in videos:
        print(f"Sending to AI: {video['filename']}")
        command = send_to_ai(video["ffprobe_data"], system_info)
        if command:
            command = extract_ffmpeg_command(command)
            update_video(video["id"], command)
            print(f"[Saved] AI command saved for video ID: {video['id']}")
        else:
            print(f"[Skipped] AI command failed for video ID: {video['id']}")

def extract_ffmpeg_command(text: str) -> str:
    text = re.sub(r"^```(?:bash)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    match = re.search(r"(ffmpeg\s.+)", text, flags=re.DOTALL)
    if match:
        command = match.group(1).strip()
        return command
    else:
        return text.strip()

def main():
    print("Starting AI Command Generator...")
    while True:
        try:
            process_batch()
        except Exception as e:
            print(f"[Main Error] {e}")
        time.sleep(AI_INTERVAL)

if __name__ == "__main__":
    main()
