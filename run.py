"""
YouTube Heatmap Clipper - Main Entry Point

This tool automatically extracts viral segments from YouTube videos based on:
1. YouTube's "Most Replayed" heatmap data
2. AI-based engagement detection (fallback when heatmap unavailable)

Generated clips are optimized for TikTok/Shorts format with optional subtitles.
"""
import os
import sys
import subprocess
import shutil
import warnings

warnings.filterwarnings("ignore")

# Import configurations
from config import (
    OUTPUT_DIR, MAX_CLIPS, PADDING, WHISPER_MODEL,
    USE_AI_FALLBACK
)

# Import utilities
from youtube_utils import extract_video_id, get_duration, ambil_most_replayed
from subtitle_utils import get_model_size
from ai_detection import detect_engagement_ai
from clip_processor import proses_satu_clip


def cek_dependensi(install_whisper=False):
    """
    Ensure required dependencies are available.
    Automatically updates yt-dlp and checks FFmpeg availability.
    """
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if install_whisper:
        # Check if faster-whisper package is installed
        try:
            import faster_whisper
            print(f"✅ Faster-Whisper package installed.")
            
            # Check if selected model is cached
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            model_name = f"faster-whisper-{WHISPER_MODEL}"
            
            model_cached = False
            if os.path.exists(cache_dir):
                try:
                    cached_items = os.listdir(cache_dir)
                    model_cached = any(model_name in item.lower() for item in cached_items)
                except Exception:
                    pass
            
            if model_cached:
                print(f"✅ Model '{WHISPER_MODEL}' already cached and ready.\n")
            else:
                print(f"⚠️  Model '{WHISPER_MODEL}' not found in cache.")
                print(f"      Will auto-download ~{get_model_size(WHISPER_MODEL)} on first transcribe.")
                print(f"      Download happens only once, then cached for future use.\n")
                
        except ImportError:
            print("   Installing Faster-Whisper package...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"✅ Faster-Whisper package installed successfully.")
            print(f"⚠️  Model '{WHISPER_MODEL}' (~{get_model_size(WHISPER_MODEL)}) will be downloaded on first use.\n")

    if not shutil.which("ffmpeg"):
        print("FFmpeg not found. Please install FFmpeg and ensure it is in PATH.")
        sys.exit(1)


def main():
    """
    Main entry point of the application.
    """
    # Select crop mode
    print("\n=== Crop Mode ===")
    print("1. Default (center crop)")
    print("2. Split 1 (top: center, bottom: bottom-left (facecam))")
    print("3. Split 2 (top: center, bottom: bottom-right ((facecam))")
    
    while True:
        choice = input("\nSelect crop mode (1-3): ").strip()
        if choice == "1":
            crop_mode = "default"
            crop_desc = "Default center crop"
            break
        elif choice == "2":
            crop_mode = "split_left"
            crop_desc = "Split crop (bottom-left facecam)"
            break
        elif choice == "3":
            crop_mode = "split_right"
            crop_desc = "Split crop (bottom-right facecam)"
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
    
    print(f"Selected: {crop_desc}")
    
    # Ask for subtitle
    print("\n=== Auto Subtitle ===")
    print(f"Available model: {WHISPER_MODEL} (~{get_model_size(WHISPER_MODEL)})")
    subtitle_choice = input("Add auto subtitle using Faster-Whisper? (y/n): ").strip().lower()
    use_subtitle = subtitle_choice in ["y", "yes"]
    
    if use_subtitle:
        print(f"✅ Subtitle enabled (Model: {WHISPER_MODEL}, Bahasa Indonesia)")
    else:
        print("❌ Subtitle disabled")
    
    print()
    
    # Check dependencies
    cek_dependensi(install_whisper=use_subtitle)

    link = input("Link YT: ").strip()
    video_id = extract_video_id(link)

    if not video_id:
        print("Invalid YouTube link.")
        return

    # Get video duration first (needed for both heatmap and AI fallback)
    total_duration = get_duration(video_id)
    
    heatmap_data = ambil_most_replayed(video_id)

    # Fallback to AI-based detection if heatmap unavailable
    if not heatmap_data:
        if USE_AI_FALLBACK:
            # Ensure Whisper is available for AI analysis
            if not use_subtitle:
                print("\n⚠️  AI fallback requires Whisper. Enabling temporarily...")
                cek_dependensi(install_whisper=True)
            
            heatmap_data = detect_engagement_ai(video_id, total_duration)
            
            if not heatmap_data:
                print("\n❌ No high-engagement segments found (heatmap or AI).")
                return
        else:
            print("No high-engagement segments found.")
            print("   Tip: Enable USE_AI_FALLBACK=True for AI-based detection.")
            return

    print(f"✅ Found {len(heatmap_data)} high-engagement segments.")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(
        f"Processing clips with {PADDING}s pre-padding "
        f"and {PADDING}s post-padding."
    )
    print(f"Using crop mode: {crop_desc}")

    success_count = 0

    for item in heatmap_data:
        if success_count >= MAX_CLIPS:
            break

        if proses_satu_clip(
            video_id,
            item,
            success_count + 1,
            total_duration,
            crop_mode,
            use_subtitle
        ):
            success_count += 1

    print(
        f"Finished processing. "
        f"{success_count} clip(s) successfully saved to '{OUTPUT_DIR}'."
    )


if __name__ == "__main__":
    main()
