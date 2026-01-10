"""
Subtitle generation utilities using Faster-Whisper.
"""
import time

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from config import WHISPER_MODEL


def get_model_size(model):
    """
    Get the approximate size of a Whisper model.
    """
    sizes = {
        "tiny": "75 MB",
        "base": "142 MB",
        "small": "466 MB",
        "medium": "1.5 GB",
        "large-v1": "2.9 GB",
        "large-v2": "2.9 GB",
        "large-v3": "2.9 GB"
    }
    return sizes.get(model, "unknown size")


def estimate_transcribe_time(video_duration_seconds, model_name):
    """
    Estimate transcription time based on video duration and model.
    Returns estimated time in seconds.
    """
    # Processing speed per minute of video (in seconds)
    speeds = {
        "tiny": 5,      # ~5 seconds per minute of video
        "base": 8,      # ~8 seconds per minute
        "small": 15,    # ~15 seconds per minute
        "medium": 40,   # ~40 seconds per minute
        "large-v1": 90,
        "large-v2": 90,
        "large-v3": 90
    }
    
    speed = speeds.get(model_name, 15)  # Default to small speed
    video_minutes = video_duration_seconds / 60
    estimated_seconds = video_minutes * speed
    
    return int(estimated_seconds)


def format_time(seconds):
    """Format seconds to human-readable time string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


def format_timestamp(seconds):
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_subtitle(video_file, subtitle_file):
    """
    Generate subtitle file using Faster-Whisper for the given video.
    Returns True if successful, False otherwise.
    """
    try:
        from faster_whisper import WhisperModel
        
        print(f"  Loading Faster-Whisper model '{WHISPER_MODEL}'...")
        print(f"  (If this is first time, downloading ~{get_model_size(WHISPER_MODEL)}...)")
        # Use int8 for CPU efficiency, or "float16" for GPU
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        
        print("  ✅ Model loaded. Transcribing audio...")
        start_time = time.time()
        segments, info = model.transcribe(video_file, language=None)
        
        # Collect segments with simple progress
        segments_list = []
        if HAS_TQDM:
            # Use tqdm for short clips
            for segment in tqdm(segments, desc="  Transcribing", unit="seg", 
                               bar_format='{l_bar}{bar}| {n_fmt} [{elapsed}]'):
                segments_list.append(segment)
        else:
            # Fallback: collect all segments
            segments_list = list(segments)
        
        elapsed = time.time() - start_time
        print(f"  ✅ Transcribed in {format_time(int(elapsed))} ({len(segments_list)} segments)")
        
        # Generate SRT format
        print("  Generating subtitle file...")
        with open(subtitle_file, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments_list, start=1):
                seg_start = format_timestamp(segment.start)
                seg_end = format_timestamp(segment.end)
                text = segment.text.strip()
                
                f.write(f"{i}\n")
                f.write(f"{seg_start} --> {seg_end}\n")
                f.write(f"{text}\n\n")
        
        return True
    except Exception as e:
        print(f"  Failed to generate subtitle: {str(e)}")
        return False
