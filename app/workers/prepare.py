#!/usr/bin/env python3

import json
import os
import platform
import subprocess
import time
import re
from typing import Dict, Optional, List
from backend.utils import logger
from openai import OpenAI
from backend.db_operations import (
    get_videos_by_status,
    update_video_command_and_system_info
)

# Environment Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", 3))
AI_INTERVAL = int(os.getenv("AI_INTERVAL", 10))
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
PROMPT_FILE_PATH = "/data/prompt.txt"

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")


def get_system_info() -> Dict[str, str]:
    """Retrieve system information including OS, CPU, GPU, and other hardware details."""
    info = {
        "OS": os.getenv("HOST_OS", platform.system()),
        "OS_Version": os.getenv("HOST_OS_VERSION", platform.version()),
        "Architecture": platform.machine(),
        "Processor": os.getenv("HOST_CPU_MODEL", platform.processor()),
        "Total_RAM_kB": os.getenv("HOST_TOTAL_RAM", "Unknown"),
        "Python_Version": platform.python_version(),
    }

    gpu_info = detect_gpu()
    if gpu_info:
        info["GPU"] = gpu_info

    return info


def detect_gpu() -> Optional[str]:
    """Detect GPU information using various tools."""
    env_gpu = os.getenv("HOST_GPU_MODEL")
    if env_gpu:
        return f"Host GPU: {env_gpu}"

    gpu_detection_methods = [
        (["vainfo"], "VAProfile", "VAAPI available"),
        (["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], None, "NVIDIA GPU: {output}"),
        (["rocm-smi", "--showproductname"], None, "AMD GPU (ROCm): {output}")
    ]

    for command, keyword, message in gpu_detection_methods:
        output = run_command(command)
        if output and (not keyword or keyword in output):
            return message.format(output=output.strip())

    if platform.system().lower() == "linux":
        return detect_gpu_via_lspci()

    return "GPU detection not supported on this OS without NVIDIA or ROCm tools"


def detect_gpu_via_lspci() -> Optional[str]:
    """Detect GPU using lspci on Linux."""
    lspci_output = run_command(["lspci"])
    if not lspci_output:
        return "No discrete GPU detected via lspci"

    for vendor, name in [("AMD", "AMD GPU detected via lspci"), ("NVIDIA", "NVIDIA GPU detected via lspci")]:
        lines = [line for line in lspci_output.splitlines() if vendor in line]
        if lines:
            return f"{name}: {lines[0]}"

    return "No discrete GPU detected via lspci"


def run_command(command: List[str]) -> Optional[str]:
    """Run a shell command and return its output."""
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def generate_ai_command(prompt: str) -> Optional[str]:
    """Send a prompt to OpenAI and return the generated command."""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are a video processing expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[AI Error] {str(e)}")
        return None


def create_prompt(video: Dict, system_info: Dict, previous_command: Optional[str] = None) -> str:
    """Create a prompt for OpenAI based on video metadata and system info."""
    base_prompt = f"""
        Here is the metadata of a video file:
        ffprobe data: {json.dumps(video["ffprobe_data"], indent=2)}
        System info: {json.dumps(system_info, indent=2)}

    """

    if os.path.exists(PROMPT_FILE_PATH):
        with open(PROMPT_FILE_PATH, "r") as file:
            custom_prompt = file.read().strip()
        base_prompt += custom_prompt
    else:
        base_prompt += f"""
            Your task is to generate the most optimal ffmpeg command to compress this video with the following requirements:

                - Prioritize significant space savings while preserving visual quality.
                - Use the **x265** codec if supported.
                - Maintain the original **resolution** and **frame rate** exactly.
                - Use **hardware acceleration** only (e.g., NVENC, VAAPI, or QSV) if available in system_info, add required tag in command.
                - Avoid lossless mode, but keep compression visually lossless (e.g., CRF 22-28 based on ffprobe_data).
                - Audio should be copied without re-encoding.
                - The result should be web-streaming friendly (i.e., add `-movflags +faststart`).
                - Only return a single-line ffmpeg command starting with `ffmpeg`.
                - Use `input.mp4` as input and `output.mp4` as output.
                - In file exist in output command should overwrite the file.
                - Do not include any other text or explanations.
                - Recheck command against all requirements.
        """

    if previous_command:
        base_prompt += f"""
            Here is the last command:
            {previous_command}
            The estimated size is too large compared to the original size.
            Please re-generate the command to be more efficient.
            Use -b:v (bitrate) and/or -maxrate/-bufsize to cap the output size more effectively if -crf of last command is 28 or more.
            The command should always be more efficient than the last one.
        """
    return base_prompt


def process_videos(status: str, regenerate: bool = False):
    """Process a batch of videos based on their status."""
    videos = get_videos_by_status(status, AI_BATCH_SIZE)
    if not videos:
        logger.info(f"No {status} videos to process.")
        return

    system_info = get_system_info()

    for video in videos:
        logger.info(f"Processing video: {video['filename']}")
        prompt = create_prompt(video, system_info, video["ai_command"] if regenerate else None)
        command = generate_ai_command(prompt)
        if command:
            command = extract_ffmpeg_command(command)
            update_video_command_and_system_info(video["id"], command, json.dumps(system_info, indent=2))
            logger.info(f"[Saved] AI command saved for video ID: {video['id']}")
        else:
            logger.warning(f"[Skipped] AI command generation failed for video ID: {video['id']}")


def extract_ffmpeg_command(text: str) -> str:
    """Extract the ffmpeg command from the AI response."""
    text = re.sub(r"^```(?:bash)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    match = re.search(r"(ffmpeg\s.+)", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def main():
    """Main function to continuously process video batches."""
    logger.info("Starting AI Command Generator...")
    while True:
        try:
            process_videos('confirmed')
            process_videos('re-confirmed', regenerate=True)
        except Exception as e:
            logger.error(f"[Main Error] {e}")
        time.sleep(AI_INTERVAL)


if __name__ == "__main__":
    main()
