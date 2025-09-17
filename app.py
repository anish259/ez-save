from flask import Flask, render_template, request, jsonify, Response
from pytubefix import YouTube, request as pytube_request
import os
import tempfile
import subprocess
import pytubefix.exceptions as pytube_exceptions
import urllib.error
from urllib.parse import urlparse, parse_qs
import time
import threading
import sys

app = Flask(__name__)

def clean_youtube_url(url):
    """Remove extra parameters like ?si= to avoid issues."""
    if 'youtu.be' in url:
        parsed = urlparse(url)
        video_id = parsed.path[1:]  # e.g., KR7KcaettM
        params = parse_qs(parsed.query)
        if 'si' in params:
            del params['si']  # Remove si param
        clean_params = '&'.join([f"{k}={v[0]}" for k, v in params.items() if v])
        return f"https://www.youtube.com/watch?v={video_id}" + ("?" + clean_params if clean_params else "")
    return url

@app.route('/')
def index():
    print("Serving index.html")
    return render_template('index.html')

@app.route('/get_formats', methods=['POST'])
def get_formats():
    url = request.form.get('url')
    print(f"Starting get_formats - URL: {url}")
    if not url:
        print("Error: No URL provided")
        return jsonify({'error': 'No URL provided'}), 400
    
    url = clean_youtube_url(url)
    print(f"Cleaned URL: {url}")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} to fetch YouTube data")
            yt = YouTube(url, use_po_token=True)
            print("YouTube object created successfully")
            time.sleep(5)  # 5-second delay to avoid rate limiting
            
            try:
                formats = []
                seen_resolutions = set()
                
                video_streams = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
                print(f"Found {len(video_streams)} video streams")
                for stream in video_streams:
                    if stream.includes_video_track and stream.resolution and stream.resolution not in seen_resolutions:
                        formats.append({
                            'itag': stream.itag,
                            'type': 'video',
                            'resolution': stream.resolution,
                            'fps': stream.fps if stream.fps else 'N/A',
                            'size': f"{stream.filesize / (1024 * 1024):.2f} MB" if stream.filesize else "Unknown"
                        })
                        seen_resolutions.add(stream.resolution)
                
                audio_streams = yt.streams.filter(only_audio=True).order_by('abr').desc()
                print(f"Found {len(audio_streams)} audio streams")
                for stream in audio_streams:
                    formats.append({
                        'itag': stream.itag,
                        'type': 'audio',
                        'resolution': f"MP3 {stream.abr}kbps" if stream.abr else 'MP3 Audio',
                        'fps': 'N/A',
                        'size': f"{stream.filesize / (1024 * 1024):.2f} MB" if stream.filesize else "Unknown"
                    })
                
                print(f"Returning formats: {formats}")
                return jsonify({'title': yt.title, 'formats': formats})
            except Exception as stream_error:
                print(f"Error processing streams: {str(stream_error)}")
                raise
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                print(f"Rate limit hit (429) on attempt {attempt + 1}. Retrying in 10 seconds...")
                time.sleep(10)
                continue
            print(f"HTTP Error in get_formats: {str(e)}")
            return jsonify({'error': f'Failed to fetch video: {str(e)}'}), 400
        except (pytube_exceptions.ExtractError, pytube_exceptions.VideoUnavailable) as e:
            print(f"pytube Error in get_formats: {str(e)}")
            return jsonify({'error': f'Failed to fetch video: {str(e)}'}), 400
        except Exception as e:
            print(f"Unexpected error in get_formats: {str(e)}, Traceback: {str(sys.exc_info()[2])}")
            return jsonify({'error': str(e)}), 500
    print("Max retries reached, giving up")
    return jsonify({'error': 'Max retries reached, please try again later'}), 429

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    itag = request.form.get('itag')
    download_type = request.form.get('type')
    
    print(f"Starting download - URL: {url}, itag: {itag}, type: {download_type}")
    if not url or not itag:
        print("Error: Missing parameters")
        return jsonify({'error': 'Missing parameters'}), 400
    
    url = clean_youtube_url(url)
    print(f"Cleaned URL: {url}")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} to download")
            yt = YouTube(url, use_po_token=True)
            print("YouTube object created successfully")
            time.sleep(5)  # 5-second delay to avoid rate limiting
            stream = yt.streams.get_by_itag(int(itag))
            print(f"Stream selected: itag={itag}, includes_audio={stream.includes_audio_track}")

            ext = 'mp3' if download_type == 'audio' else 'mp4'
            filename = f"{yt.title.replace(' ', '_').replace('/', '_')}.{ext}"
            
            if download_type == 'audio':
                with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as temp_audio:
                    stream.download(output_path=os.path.dirname(temp_audio.name), filename=os.path.basename(temp_audio.name))
                    audio_path = temp_audio.name
                
                cmd = [
                    'ffmpeg',
                    '-i', audio_path,
                    '-vn',
                    '-c:a', 'libmp3lame',
                    '-q:a', '2',
                    '-f', 'mp3',
                    'pipe:1'
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=-1)
                start_time = time.time()
                print(f"Starting ffmpeg audio conversion for {filename}")
                
                def generate():
                    try:
                        while True:
                            chunk = proc.stdout.read(8192)
                            if not chunk:
                                break
                            yield chunk
                        proc.wait(timeout=600)
                        if proc.returncode != 0:
                            err = proc.stderr.read().decode('utf-8', errors='ignore')
                            print(f"FFmpeg audio error: {err}")
                            raise RuntimeError(f"FFmpeg error: {err}")
                        print(f"FFmpeg audio conversion completed in {time.time() - start_time:.2f} seconds")
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        print("FFmpeg audio conversion timed out")
                        raise RuntimeError("FFmpeg timeout")
                    finally:
                        proc.terminate()
                        os.unlink(audio_path)
                
                return Response(
                    generate(),
                    mimetype='audio/mpeg',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'}
                )
            
            elif download_type == 'video' and not stream.includes_audio_track:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
                    stream.download(output_path=os.path.dirname(temp_video.name), filename=os.path.basename(temp_video.name))
                    video_path = temp_video.name
                
                audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
                if not audio_stream:
                    os.unlink(video_path)
                    return jsonify({'error': 'No audio stream available'}), 400
                with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as temp_audio:
                    audio_stream.download(output_path=os.path.dirname(temp_audio.name), filename=os.path.basename(temp_audio.name))
                    audio_path = temp_audio.name
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_output:
                    output_path = temp_output.name
                    cmd = [
                        'ffmpeg',
                        '-i', video_path,
                        '-i', audio_path,
                        '-c', 'copy',
                        '-map', '0:v',
                        '-map', '1:a',
                        '-y',  # Overwrite output without asking
                        output_path
                    ]
                    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
                    start_time = time.time()
                    print(f"Starting ffmpeg merge for {filename}")
                    
                    def log_stderr():
                        while True:
                            line = proc.stderr.readline()
                            if not line:
                                break
                            print(f"FFmpeg progress: {line.strip()}")
                    
                    stderr_thread = threading.Thread(target=log_stderr)
                    stderr_thread.daemon = True
                    stderr_thread.start()
                    
                    try:
                        proc.wait(timeout=600)
                        if proc.returncode != 0:
                            err = proc.stderr.read()
                            print(f"FFmpeg merge error: {err}")
                            raise RuntimeError(f"FFmpeg error: {err}")
                        print(f"FFmpeg merge completed in {time.time() - start_time:.2f} seconds")
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        print("FFmpeg merge timed out after 600 seconds")
                        raise RuntimeError("FFmpeg merge timeout")
            
                def generate():
                    try:
                        with open(output_path, 'rb') as f:
                            while chunk := f.read(8192):
                                yield chunk
                    finally:
                        os.unlink(video_path)
                        os.unlink(audio_path)
                        os.unlink(output_path)
            
                return Response(
                    generate(),
                    mimetype='video/mp4',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'}
                )
            
            else:
                def generate():
                    for chunk in pytube_request.stream(stream.url):
                        yield chunk
            
                return Response(
                    generate(),
                    mimetype='video/mp4',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'}
                )
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                print(f"Rate limit hit (429) on attempt {attempt + 1}. Retrying in 10 seconds...")
                time.sleep(10)
                continue
            print(f"HTTP Error in download: {str(e)}")
            return jsonify({'error': f'Failed to download video: {str(e)}'}), 400
        except Exception as e:
            print(f"Download error: {str(e)}, Traceback: {str(sys.exc_info()[2])}")
            return jsonify({'error': str(e)}), 500
    print("Max retries reached, giving up")
    return jsonify({'error': 'Max retries reached, please try again later'}), 429

if __name__ == '__main__':
    print("Starting app in debug mode")
    app.run(debug=True)