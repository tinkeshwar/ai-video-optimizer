#!/usr/bin/env python3

import json
import os
import platform
import subprocess
import time
import re
from typing import Dict, Optional, List, Tuple
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
SYSTEM_PROMPT_FILE = "/data/system_prompt.txt"
USER_PROMPT_FILE = "/data/user_prompt.txt"
RETRY_PROMPT_FILE = "/data/retry_prompt.txt"

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# ── Fallback Prompts ──

FALLBACK_SYSTEM_PROMPT = """You are a video processing expert specializing in ffmpeg command generation.
You have deep knowledge of video codecs (x264, x265, AV1), container formats,
hardware acceleration (NVENC, VAAPI, QSV), and compression optimization.

System environment:
{{SYSTEM_INFO}}

Rules:
- Only respond with a single-line ffmpeg command starting with `ffmpeg`.
- Do not include any explanations, markdown, code fences, or extra text.
- Use `input.mp4` as input and `output.mp4` as output.
- Output command must overwrite existing files.
- Recheck the command against all user requirements before responding."""

FALLBACK_USER_PROMPT = """Here is the metadata of a video file:
{{FFPROBE_DATA}}

User selected audio stream: {{SELECTED_AUDIO}}
User selected subtitle stream: {{SELECTED_SUBTITLE}}

Generate the most optimal ffmpeg command to compress this video with the following requirements:
- Prioritize significant space savings while preserving visual quality.
- Use the x265 codec if supported.
- Maintain the original resolution and frame rate exactly.
- Use hardware acceleration (e.g., NVENC, VAAPI, or QSV) only if available in the system environment, and add required tags in the command.
- Avoid lossless mode, but keep compression visually lossless (e.g., CRF 22-28 based on content).
- Map only the user-selected audio stream using its index (e.g., `-map 0:a:0`). Copy audio without re-encoding.
- If a subtitle stream is selected, map it (e.g., `-map 0:s:0`). If no subtitle is selected, use `-sn` to remove all subtitles.
- Add `-movflags +faststart` for web-streaming compatibility.
{{RETRY_INSTRUCTION}}"""

RETRY_INSTRUCTION_TEMPLATE = """
The previous command was:
{{PREVIOUS_COMMAND}}
The estimated output size is too large compared to the original.
Re-generate a more efficient command.
Use -b:v (bitrate) and/or -maxrate/-bufsize to cap the output size more effectively if -global_quality of the last command is 30 or more.
The new command must always be more efficient than the previous one."""

# ── System Info Detection ──


def get_system_info() -> Dict[str, str]:
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
    env_gpu = os.getenv("HOST_GPU_MODEL")
    if env_gpu:
        return f"Host GPU: {env_gpu}"

    gpu_detection_methods = [
        (["rocm-smi", "--showproductname"], None, "AMD GPU (ROCm): {output}"),
        (["vainfo"], "VAProfile", "VAAPI available"),
        (["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], None, "NVIDIA GPU: {output}")
    ]

    for command, keyword, message in gpu_detection_methods:
        output = run_command(command)
        if output and (not keyword or keyword in output):
            return message.format(output=output.strip())

    if platform.system().lower() == "linux":
        return detect_gpu_via_lspci()

    return "GPU detection not supported on this OS without NVIDIA or ROCm tools"


def detect_gpu_via_lspci() -> Optional[str]:
    lspci_output = run_command(["lspci"])
    if not lspci_output:
        return "No discrete GPU detected via lspci"

    for vendor, name in [("AMD", "AMD GPU detected via lspci"), ("NVIDIA", "NVIDIA GPU detected via lspci")]:
        lines = [line for line in lspci_output.splitlines() if vendor in line]
        if lines:
            return f"{name}: {lines[0]}"

    return "No discrete GPU detected via lspci"


def run_command(command: List[str]) -> Optional[str]:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


# ── Prompt Building ──


def load_prompt_template(filepath: str, fallback: str) -> str:
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            content = f.read().strip()
            if content:
                logger.info(f"Loaded prompt override from {filepath}")
                return content
    return fallback


def resolve_placeholders(template: str, placeholders: Dict[str, str]) -> str:
    for key, value in placeholders.items():
        template = template.replace(key, str(value))
    return template


def build_placeholders(video: Dict, system_info: Dict, previous_command: Optional[str] = None) -> Dict[str, str]:
    retry_instruction = ""
    if previous_command:
        retry_template = load_prompt_template(RETRY_PROMPT_FILE, RETRY_INSTRUCTION_TEMPLATE)
        retry_instruction = resolve_placeholders(
            retry_template,
            {"{{PREVIOUS_COMMAND}}": previous_command}
        )

    return {
        "{{FFPROBE_DATA}}": json.dumps(video.get("ffprobe_data", {}), indent=2),
        "{{SYSTEM_INFO}}": json.dumps(system_info, indent=2),
        "{{SELECTED_AUDIO}}": video.get("selected_audio") or "Not specified",
        "{{SELECTED_SUBTITLE}}": video.get("selected_subtitle") or "None (remove all subtitles)",
        "{{PREVIOUS_COMMAND}}": previous_command or "",
        "{{RETRY_INSTRUCTION}}": retry_instruction,
    }


def build_prompts(video: Dict, system_info: Dict, previous_command: Optional[str] = None) -> Tuple[str, str]:
    placeholders = build_placeholders(video, system_info, previous_command)

    system_template = load_prompt_template(SYSTEM_PROMPT_FILE, FALLBACK_SYSTEM_PROMPT)
    user_template = load_prompt_template(USER_PROMPT_FILE, FALLBACK_USER_PROMPT)

    system_prompt = resolve_placeholders(system_template, placeholders)
    user_prompt = resolve_placeholders(user_template, placeholders)

    return system_prompt, user_prompt


# ── AI Interaction ──


def generate_ai_command(system_prompt: str, user_prompt: str) -> Optional[str]:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[AI Error] {str(e)}")
        return None


def extract_ffmpeg_command(text: str) -> str:
    text = re.sub(r"^```(?:bash)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    match = re.search(r"(ffmpeg\s.+)", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text.strip()


# ── Video Processing ──


def process_videos(status: str, regenerate: bool = False):
    videos = get_videos_by_status(status, AI_BATCH_SIZE)
    if not videos:
        logger.info(f"No {status} videos to process.")
        return

    system_info = get_system_info()

    for video in videos:
        logger.info(f"Processing video: {video['filename']}")
        previous_command = video["ai_command"] if regenerate else None
        system_prompt, user_prompt = build_prompts(video, system_info, previous_command)
        command = generate_ai_command(system_prompt, user_prompt)
        if command:
            command = extract_ffmpeg_command(command)
            comment = f"AI command {'regenerated' if regenerate else 'generated'} using {AI_MODEL}"
            update_video_command_and_system_info(
                video["id"], command, json.dumps(system_info, indent=2), comment=comment
            )
            logger.info(f"[Saved] AI command saved for video ID: {video['id']}")
        else:
            logger.warning(f"[Skipped] AI command generation failed for video ID: {video['id']}")


def main():
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
