#!/usr/bin/env python3

import json
import os
import platform
import subprocess
import time
import re
from backend.utils import logger
from typing import Dict, Optional, List
from openai import OpenAI
from backend.db_operations import (
    get_videos_by_status,
    update_video_command_and_system_info
)

# Environment Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", 3))
AI_INTERVAL = int(os.getenv("AI_INTERVAL", 10))


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

    # GPU detection
    gpu_info = detect_gpu()
    if gpu_info:
        info["GPU"] = gpu_info

    return info


def detect_gpu() -> Optional[str]:
    """Detect GPU information using various tools."""
    # Check for GPU from environment variables
    env_gpu = os.getenv("HOST_GPU_MODEL")
    if env_gpu:
        return f"Host GPU: {env_gpu}"

    # NVIDIA GPU detection
    if gpu := run_command(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]):
        return f"NVIDIA GPU: {gpu.strip()}"

    # AMD ROCm GPU detection
    if gpu := run_command(["rocm-smi", "--showproductname"]):
        return f"AMD GPU (ROCm): {gpu.strip()}"

    # VAAPI detection
    if vainfo := run_command(["vainfo"]):
        if "VAProfile" in vainfo:
            return "VAAPI available"

    # lspci fallback for Linux
    if platform.system().lower() == "linux":
        lspci_output = run_command(["lspci"])
        if lspci_output:
            amd_lines = [line for line in lspci_output.splitlines() if "AMD" in line or "ATI" in line]
            nvidia_lines = [line for line in lspci_output.splitlines() if "NVIDIA" in line]
            if amd_lines:
                return f"AMD GPU detected via lspci: {amd_lines[0]}"
            if nvidia_lines:
                return f"NVIDIA GPU detected via lspci: {nvidia_lines[0]}"
        return "No discrete GPU detected via lspci"

    return "GPU detection not supported on this OS without NVIDIA or ROCm tools"


def run_command(command: List[str]) -> Optional[str]:
    """Run a shell command and return its output."""
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def send_to_ai(ffprobe_data: Dict, system_info: Dict) -> Optional[str]:
    """Send video metadata and system info to OpenAI to generate an ffmpeg command."""
    prompt = f"""
        Here is the metadata of a video file:
        ffprobe data: {json.dumps(ffprobe_data, indent=2)}
        System info: {json.dumps(system_info, indent=2)}

        Your task is to generate the most optimal ffmpeg command to compress this video with the following requirements:

            - Prioritize significant space savings while preserving visual quality.
            - Use the **x265** codec if supported.
            - Maintain the original **resolution** and **frame rate** exactly.
            - Use **hardware acceleration** (e.g., NVENC, VAAPI, or QSV) if available in system_info.
            - Avoid lossless mode, but keep compression visually lossless (e.g., CRF 22-28 based on ffprobe_data).
            - Audio should be copied without re-encoding.
            - The result should be web-streaming friendly (i.e., add `-movflags +faststart`).
            - Only return a single-line ffmpeg command starting with `ffmpeg`.
            - Use `input.mp4` as input and `output.mp4` as output.
            - In file exist in output command should overwrite the file.
            - Do not include any other text or explanations.

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
        logger.error(f"[AI Error] {str(e)}")
        return None

def send_to_ai_again(video: Dict, system_info: Dict) -> Optional[str]:
    """Send video metadata and system info to OpenAI to generate an ffmpeg command."""
    prompt = f"""
        Here is the ffprobe data of the video:
        {json.dumps(video["ffprobe_data"], indent=2)}
        Here is the system info:
        {json.dumps(system_info, indent=2)}

        You have already generated a command for this video, but it is not efficient enough.

        Here is the last command:
        {video["ai_command"]}     
        Here is the ffmpeg command output:
        {video["progress"]}

        The estimated size is too large compared to the original size.
        The original size is {video["original_size"]} bytes, and the estimated size is {video["estimated_size"]} bytes.
        The command you generated is not efficient enough, so re-generate the command.
        Here are the requirements for the new command:
            - Prioritize significant space savings while preserving visual quality.
            - Use the **x265** codec if supported.
            - Maintain the original **resolution** and **frame rate** exactly.
            - Use **hardware acceleration** (e.g., NVENC, VAAPI, or QSV) if available in system_info.
            - Avoid lossless mode, but keep compression visually lossless (e.g., CRF 22-28 based on ffprobe_data).
            - Audio should be copied without re-encoding.
            - The result should be web-streaming friendly (i.e., add `-movflags +faststart`).
            - Only return a single-line ffmpeg command starting with `ffmpeg`.
            - Use `input.mp4` as input and `output.mp4` as output.
            - In file exist in output command should overwrite the file.
            - Do not include any other text or explanations.

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
        logger.error(f"[AI Error] {str(e)}")
        return None

def process_batch():
    """Process a batch of videos by generating ffmpeg commands using AI."""
    videos = get_videos_by_status('confirmed', AI_BATCH_SIZE)
    if not videos:
        logger.info("No confirmed videos to process.")
        return

    system_info = get_system_info()

    for video in videos:
        logger.info(f"Processing video: {video['filename']}")
        command = send_to_ai(video["ffprobe_data"], system_info)
        if command:
            command = extract_ffmpeg_command(command)
            update_video_command_and_system_info(video["id"], command, json.dumps(system_info, indent=2))
            logger.info(f"[Saved] AI command saved for video ID: {video['id']}")
        else:
            logger.warning(f"[Skipped] AI command generation failed for video ID: {video['id']}")

def re_process_batch():
    """Process a batch of videos for which command already generated but not efficient enough, so re generate the command."""
    videos = get_videos_by_status('re-confirmed', AI_BATCH_SIZE)
    if not videos:
        logger.info("No re-confirmed videos to process.")
        return

    system_info = get_system_info()

    for video in videos:
        logger.info(f"Processing video: {video['filename']}")
        command = send_to_ai_again(video, system_info)
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
            process_batch()
            re_process_batch()
        except Exception as e:
            logger.error(f"[Main Error] {e}")
        time.sleep(AI_INTERVAL)


if __name__ == "__main__":
    main()
