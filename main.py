#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import urllib.request
from threading import Thread
from flask import Flask, jsonify

app = Flask(__name__)

# Environment variables (set these in Render dashboard - NOT in code)
YT_STREAM_KEY = os.environ.get("YT_STREAM_KEY")
VIDEO_URL = os.environ.get("VIDEO_URL")
BITRATE = os.environ.get("BITRATE", "1800k")   # default 1800k, change if needed
VIDEO_FILE = "/tmp/loop_video.mp4"
FFMPEG_BINARY = os.path.join(os.getcwd(), "bin", "ffmpeg") if os.path.exists(os.path.join(os.getcwd(), "bin", "ffmpeg")) else "ffmpeg"

def download_video(url, dest, retries=5, wait=5):
    for attempt in range(1, retries+1):
        try:
            print(f"[{time.ctime()}] Download attempt {attempt} -> {url}")
            # use urllib to avoid extra deps
            urllib.request.urlretrieve(url, dest)
            print(f"[{time.ctime()}] Download succeeded: {dest}")
            return True
        except Exception as e:
            print(f"[{time.ctime()}] Download failed (attempt {attempt}): {e}")
            if attempt < retries:
                time.sleep(wait)
    return False

def ffmpeg_loop():
    if not YT_STREAM_KEY or not VIDEO_URL:
        print("ERROR: YT_STREAM_KEY or VIDEO_URL not set. Exiting ffmpeg_loop.")
        return

    # ensure video exists
    ok = download_video(VIDEO_URL, VIDEO_FILE, retries=5, wait=8)
    if not ok:
        print("ERROR: Could not download video. Exiting.")
        return

    while True:
        cmd = [
            FFMPEG_BINARY,
            "-re",
            "-stream_loop", "-1",
            "-i", VIDEO_FILE,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", BITRATE,
            "-maxrate", BITRATE,
            "-bufsize", "2M",
            "-pix_fmt", "yuv420p",
            "-r", "24",
            "-g", "48",
            "-c:a", "aac",
            "-b:a", "96k",
            "-ar", "44100",
            "-f", "flv",
            f"rtmps://a.rtmp.youtube.com/live2/{YT_STREAM_KEY}"
        ]
        print(f"[{time.ctime()}] Starting ffmpeg with: {' '.join(cmd[:6])} ...")
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            # stream ffmpeg logs to stdout
            for line in p.stdout:
                print(line.rstrip())
            p.wait()
            print(f"[{time.ctime()}] ffmpeg exited with code {p.returncode}. Restarting in 5s...")
        except Exception as e:
            print(f"[{time.ctime()}] ffmpeg failed to start: {e}")

        time.sleep(5)
        # re-download video periodically (in case source changed), optional:
        try:
            download_video(VIDEO_URL, VIDEO_FILE, retries=2, wait=5)
        except:
            pass

# small health endpoints for Render / monitoring
@app.route("/")
def home():
    return "YT Loop Stream service running."

@app.route("/status")
def status():
    return jsonify({
        "yt_stream_key_set": bool(YT_STREAM_KEY),
        "video_url_set": bool(VIDEO_URL),
        "bitrate": BITRATE,
        "ffmpeg_bin": FFMPEG_BINARY
    })

if __name__ == "__main__":
    # start ffmpeg loop in a background thread
    t = Thread(target=ffmpeg_loop, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", "10000"))
    print(f"[{time.ctime()}] Starting Flask on port {port} ...")
    app.run(host="0.0.0.0", port=port)
