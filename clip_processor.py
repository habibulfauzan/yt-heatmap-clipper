"""
Clip processing utilities for downloading, cropping, and exporting clips.
"""
import os
import sys
import subprocess

from config import OUTPUT_DIR, PADDING, TOP_HEIGHT, BOTTOM_HEIGHT
from subtitle_utils import generate_subtitle


def proses_satu_clip(video_id, item, index, total_duration, crop_mode="default", use_subtitle=False):
    """
    Download, crop, and export a single vertical clip
    based on a heatmap segment.
    
    Args:
        crop_mode: "default", "split_left", or "split_right"
        use_subtitle: whether to generate and burn subtitle
    """
    start_original = item["start"]
    end_original = item["start"] + item["duration"]

    start = max(0, start_original - PADDING)
    end = min(end_original + PADDING, total_duration)

    if end - start < 3:
        return False

    temp_file = f"temp_{index}.mp4"
    cropped_file = f"temp_cropped_{index}.mp4"
    subtitle_file = f"temp_{index}.srt"
    output_file = os.path.join(OUTPUT_DIR, f"clip_{index}.mp4")

    print(
        f"[Clip {index}] Processing segment "
        f"({int(start)}s - {int(end)}s, padding {PADDING}s)"
    )

    cmd_download = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        "--quiet", "--no-warnings",
        "--downloader", "ffmpeg",
        "--downloader-args",
        f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
        "-f",
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", temp_file,
        f"https://youtu.be/{video_id}"
    ]

    try:
        result = subprocess.run(
            cmd_download,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if not os.path.exists(temp_file):
            print("Failed to download video segment.")
            return False

        # Build video filter based on crop_mode
        # First, crop the video to cropped_file
        if crop_mode == "default":
            # Standard center crop - ambil dari tengah video
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", temp_file,
                "-vf", "scale=-2:1280,crop=720:1280:(iw-720)/2:(ih-1280)/2",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]
        elif crop_mode == "split_left":
            # Split crop: 
            # - Top: konten game dari tengah-tengah video (960px)
            # - Bottom: facecam dari kiri bawah video asli (320px)
            vf = (
                f"scale=-2:1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:(ih-1280)/2[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:0:ih-{BOTTOM_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", temp_file,
                "-filter_complex", vf,
                "-map", "[out]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]
        elif crop_mode == "split_right":
            # Split crop: 
            # - Top: konten game dari tengah-tengah video (960px)
            # - Bottom: facecam dari kanan bawah video asli (320px)
            vf = (
                f"scale=-2:1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:(ih-1280)/2[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:iw-720:ih-{BOTTOM_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", temp_file,
                "-filter_complex", vf,
                "-map", "[out]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]

        print("  Cropping video...")
        result = subprocess.run(
            cmd_crop,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        os.remove(temp_file)

        # Generate and burn subtitle if enabled
        if use_subtitle:
            print("  Generating subtitle...")
            if generate_subtitle(cropped_file, subtitle_file):
                print("  Burning subtitle to video...")
                # Get absolute path for subtitle file
                abs_subtitle_path = os.path.abspath(subtitle_file)
                # Escape for FFmpeg: replace \ with / and escape special chars
                subtitle_path = abs_subtitle_path.replace("\\", "/").replace(":", "\\:")
                
                cmd_subtitle = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", cropped_file,
                    "-vf", f"subtitles='{subtitle_path}':force_style='FontName=Arial,FontSize=12,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=100'",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "copy",
                    output_file
                ]
                
                result = subprocess.run(
                    cmd_subtitle,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                os.remove(cropped_file)
                os.remove(subtitle_file)
            else:
                # If subtitle generation failed, use cropped file as output
                print("  Subtitle generation failed, continuing without subtitle...")
                os.rename(cropped_file, output_file)
        else:
            # No subtitle, rename cropped file to output
            os.rename(cropped_file, output_file)

        print("Clip successfully generated.")
        return True

    except subprocess.CalledProcessError as e:
        # Cleanup temp files
        for f in [temp_file, cropped_file, subtitle_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        print(f"Failed to generate this clip.")
        print(f"Error details: {e.stderr if e.stderr else e.stdout}")
        return False
    except Exception as e:
        # Cleanup temp files
        for f in [temp_file, cropped_file, subtitle_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        print(f"Failed to generate this clip.")
        print(f"Error: {str(e)}")
        return False
