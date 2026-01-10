"""
AI-based engagement detection using transcription analysis.
"""
import os
import sys
import subprocess
import time

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from config import AI_MIN_SCORE, MAX_DURATION, WHISPER_MODEL
from subtitle_utils import format_time, estimate_transcribe_time


def analyze_engagement_from_subtitle(segments):
    """
    Analyze subtitle segments to detect high-engagement moments using AI.
    Returns list of segments with engagement scores.
    
    Detection methods:
    1. Excitement keywords (wow, amazing, incredible, etc.)
    2. Question patterns (engagement hooks)
    3. Repetition (emphasized points)
    4. Pause patterns (dramatic moments)
    5. Length variation (short punchy vs long explanations)
    """
    if not segments:
        return []
    
    # Indonesian & English excitement keywords
    excitement_keywords = [
        # ======================
        # PODCAST – Reactions & Opinions
        # ======================
        "wah", "wow", "gila", "parah", "ngeri", "sadis", "kacau",
        "menarik", "unik", "mindblowing", "dalem banget",
        "kena banget", "relate", "jujur", "asli", "sumpah",
        "gue setuju", "gue gak setuju", "menurut gue",
        "fakta", "realita", "realistis", "kenyataan",
        "berat nih", "panas nih", "ini serius",
        "plot twist", "unexpected", "di luar dugaan",

        # Podcast – Story / Insight Hooks
        "tahu gak", "tau gak", "pernah kepikiran",
        "pernah ngalamin", "pernah denger",
        "coba bayangin", "bayangkan",
        "kenapa bisa", "kok bisa",
        "menariknya", "yang bikin kaget",
        "yang jarang dibahas", "yang orang gak sadar",
        "masalahnya", "intinya", "point pentingnya",

        # ======================
        # GAMING – Hype & Reactions
        # ======================
        "anjay", "anjir", "buset", "gilak", "gokil",
        "auto panik", "auto kaget", "auto ngakak",
        "pecah", "meledak", "rusuh", "chaos",
        "clutch", "epic", "legendary", "insane",
        "crazy", "no way", "holy", "wtf",
        "clean", "perfect", "smooth",

        # Gaming – Gameplay Moments
        "headshot", "one tap", "one shot",
        "ace", "wipe", "team wipe",
        "gg", "ggwp", "ez", "ez win",
        "throw", "blunder", "fail",
        "outplay", "comeback", "turnaround",
        "last second", "detik terakhir",
        "sisa satu", "tinggal satu",

        # ======================
        # UNIVERSAL – Engagement Hooks
        # ======================
        "lihat ini", "coba lihat",
        "percaya gak", "siap-siap",
        "fokus", "dengerin",
        "tunggu", "bentar",
        "gimana menurut lo", "menurut kalian",

        # ======================
        # Emphasis / Intensifier (High Signal)
        # ======================
        "banget", "parah banget", "gila banget",
        "sangat", "sekali",
        "bener-bener", "serius",
        "really", "very", "so", "extremely",
        "literally", "totally"
    ]
    
    results = []
    
    for i, segment in enumerate(segments):
        text = segment.text.lower().strip()
        start = segment.start
        end = segment.end
        duration = end - start
        
        # Skip very short or very long segments
        if duration < 1 or duration > MAX_DURATION:
            continue
        
        score = 0.0
        
        # 1. Excitement keywords (weight: 0.4)
        keyword_count = sum(1 for keyword in excitement_keywords if keyword in text)
        if keyword_count > 0:
            score += min(0.4, keyword_count * 0.1)
        
        # 2. Question patterns (weight: 0.2)
        question_markers = ["?", "gimana", "bagaimana", "kenapa", "mengapa", 
                           "how", "what", "why", "tahu gak", "tau gak"]
        if any(marker in text for marker in question_markers):
            score += 0.2
        
        # 3. Repetition detection (weight: 0.15)
        words = text.split()
        if len(words) > 3:
            word_freq = {}
            for word in words:
                if len(word) > 3:  # Ignore short words
                    word_freq[word] = word_freq.get(word, 0) + 1
            max_repeat = max(word_freq.values()) if word_freq else 1
            if max_repeat >= 2:
                score += min(0.15, (max_repeat - 1) * 0.05)
        
        # 4. Optimal duration (weight: 0.15)
        # Clips between 5-30 seconds are most engaging
        if 5 <= duration <= 30:
            score += 0.15
        elif 3 <= duration <= 45:
            score += 0.10
        elif 1 <= duration <= 60:
            score += 0.05
        
        # 5. Text density (weight: 0.1)
        # Higher word count per second = more engaging
        words_per_sec = len(words) / duration if duration > 0 else 0
        if 2 <= words_per_sec <= 5:  # Optimal speaking pace
            score += 0.1
        elif 1 <= words_per_sec <= 6:
            score += 0.05
        
        # Normalize score to 0.0-1.0
        score = min(1.0, score)
        
        # Only include segments above threshold
        if score >= AI_MIN_SCORE:
            results.append({
                "start": start,
                "duration": min(duration, MAX_DURATION),
                "score": score,
                "method": "ai_subtitle"
            })
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return results


def detect_engagement_ai(video_id, total_duration):
    """
    Detect high-engagement segments using AI transcription analysis.
    Downloads full video audio, transcribes, and analyzes for engagement.
    """
    print("\n   Heatmap data not available.")
    print("   Falling back to AI-based engagement detection...")
    print("   This will transcribe the full video (may take a few minutes).")
    
    # Ask user confirmation
    confirm = input("\nProceed with AI analysis? (y/n): ").strip().lower()
    if confirm not in ["y", "yes"]:
        return []
    
    temp_audio = "temp_full_audio.mp4"
    
    try:
        # Download audio only (faster than full video)
        print("\n   Downloading audio track...")
        cmd_audio = [
            sys.executable, "-m", "yt_dlp",
            "--force-ipv4",
            "--quiet", "--no-warnings",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "-o", temp_audio,
            f"https://youtu.be/{video_id}"
        ]
        
        subprocess.run(
            cmd_audio,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if not os.path.exists(temp_audio):
            print("❌ Failed to download audio.")
            return []
        
        # Transcribe with Whisper
        print("\n   Transcribing full video with AI...")
        print(f"   Using model: {WHISPER_MODEL}")
        
        # Estimate transcription time
        estimated_time = estimate_transcribe_time(total_duration, WHISPER_MODEL)
        print(f"   Estimated time: ~{format_time(estimated_time)}")
        
        from faster_whisper import WhisperModel
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        
        # Start transcription with progress tracking
        start_time = time.time()
        segments, info = model.transcribe(temp_audio, language=None)
        
        # Collect segments with progress bar
        segments_list = []
        if HAS_TQDM:
            # Use tqdm for progress bar
            # Estimate total segments based on video duration (rough estimate: 1 segment per 2-3 seconds)
            estimated_segments = max(10, int(total_duration / 2.5))
            
            with tqdm(total=estimated_segments, desc="  Transcribing", unit="seg", 
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {postfix}]',
                     dynamic_ncols=True) as pbar:
                for segment in segments:
                    segments_list.append(segment)
                    pbar.update(1)
                    
                    # Update estimated remaining time every 5 segments
                    if len(segments_list) % 5 == 0:
                        elapsed = time.time() - start_time
                        if len(segments_list) > 0:
                            avg_time_per_seg = elapsed / len(segments_list)
                            remaining_segs = max(0, estimated_segments - len(segments_list))
                            remaining_time = avg_time_per_seg * remaining_segs
                            pbar.set_postfix({"ETA": format_time(int(remaining_time))})
                
                # Update to actual total at the end
                pbar.total = len(segments_list)
                pbar.refresh()
        else:
            # Fallback: simple progress without tqdm
            print("   Progress: ", end="", flush=True)
            segment_count = 0
            last_print = 0
            for segment in segments:
                segments_list.append(segment)
                segment_count += 1
                # Print dot every 10 segments
                if segment_count - last_print >= 10:
                    print(".", end="", flush=True)
                    last_print = segment_count
            
            elapsed = time.time() - start_time
            print(f"\n   Completed in {format_time(int(elapsed))}")
        
        print(f"✅ Transcription complete! ({len(segments_list)} segments)")
        
        # Analyze for engagement
        print("   Analyzing segments for engagement patterns...")
        results = analyze_engagement_from_subtitle(segments_list)
        
        # Cleanup
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        
        if results:
            print(f"✅ Found {len(results)} high-engagement segments using AI analysis!")
            print(f"   Top score: {results[0]['score']:.2f}")
        else:
            print("⚠️  No high-engagement segments detected by AI.")
        
        return results
        
    except Exception as e:
        # Cleanup on error
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except:
                pass
        
        print(f"❌ AI analysis failed: {str(e)}")
        return []
