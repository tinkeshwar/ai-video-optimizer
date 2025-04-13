import json
import os
import platform
import subprocess
import time
from contextlib import contextmanager
from sqlite3 import Row, connect
from typing import Dict, List, Optional

from openai import OpenAI

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

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
        "OS": platform.system(),
        "OS_Version": platform.version(),
        "Architecture": platform.machine(),
        "Processor": platform.processor(),
        "Python_Version": platform.python_version()
    }

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

    try:
        vainfo = subprocess.check_output(["vainfo"], stderr=subprocess.DEVNULL, text=True)
        if "VAProfile" in vainfo:
            info["GPU_Acceleration"] = "VAAPI available"
    except FileNotFoundError:
        info["GPU_Acceleration"] = "vainfo not installed"
    except subprocess.SubprocessError:
        info["GPU_Acceleration"] = "vainfo failed"
        
    # Fallback to lspci on Linux
    if platform.system().lower() == "linux":
        try:
            lspci_output = subprocess.check_output(
                ["lspci"], 
                text=True,
                stderr=subprocess.DEVNULL
            )
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

def get_confirmed_videos() -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE status = 'confirmed'")
        return [dict(row) for row in cursor.fetchall()]

def send_to_ai(ffprobe_data: Dict, system_info: Dict) -> Optional[str]:
    prompt = f"""
        Here is the metadata of a video file:
        The ffprobe data is: {json.dumps(ffprobe_data, indent=2)}
        And here is the system information: {json.dumps(system_info, indent=2)}
        Based on this information, suggest the most optimal ffmpeg command to compress the video with:
        - Best possible space saving, prefer x265 codec.
        - Use the same resolution and frame rate as the original video.
        - No visible quality loss.
        - Optionally using hardware acceleration if available.
        - Do not provide any other information or explanation, just the command stating with ffmpeg and parameter example output: ffmpeg -i input.mp4 -c:v libx265 -preset slow -x265-params log-level=error -crf 28 -c:a aac -b:a 192k -movflags +faststart -vf scale=1920:1080 -r 30000/1001 output.mp4, do not add bash or anything.
        - Consider the command is to be run in python subprocess.run in list form so you need to escape properly or avoid extra quotes.
        - Use input.mp4 as the input file and output.mp4 as the output file.
        - The command should be in a single line and should not contain any newlines or extra spaces.
        - The command should be compatible with ffmpeg version 5.0 or higher.
        - The command should be compatible with the system information provided.
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
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI API error: {str(e)}")
        return None

def update_video(video_id: int, command: str) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE videos SET ai_command = ?, status = 'ready' WHERE id = ?",
            (command, video_id)
        )
        conn.commit()

def main():
    print("Starting AI prepare...")
    while True:
        try:
            videos = get_confirmed_videos()
            if not videos:
                time.sleep(10)
                continue
                
            system_info = get_system_info()
            for video in videos:
                print(f"Sending to AI: {video['filename']}")
                command = send_to_ai(video["ffprobe_data"], system_info)
                if command:
                    update_video(video["id"], command)
                    print(f"Command saved for video {video['id']}")
                
            time.sleep(10)
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(30)

if __name__ == "__main__":
    main()
