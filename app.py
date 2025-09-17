from flask import Flask, request, jsonify
import pytubefix
import time
import sys

app = Flask(__name__)

@app.route('/')
def index():
    print("Serving index.html", file=sys.stderr)  # Force to stderr for visibility
    return "Index page"

@app.route('/get_formats', methods=['POST'])
def get_formats():
    url = request.form.get('url')
    print(f"Starting get_formats - URL: {url}", file=sys.stderr)
    if not url:
        print("Error: No URL provided", file=sys.stderr)
        return jsonify({'error': 'No URL provided'}), 400
    
    print(f"Cleaned URL: {url}", file=sys.stderr)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} to fetch YouTube data", file=sys.stderr)
            yt = pytubefix.YouTube(url, use_po_token=True)
            print("YouTube object created successfully", file=sys.stderr)
            time.sleep(5)  # 5-second delay
            formats = [{'itag': s.itag, 'type': 'test', 'resolution': 'test'} for s in yt.streams]
            print(f"Returning formats: {formats}", file=sys.stderr)
            return jsonify({'title': yt.title, 'formats': formats})
        except Exception as e:
            print(f"Error in get_formats: {str(e)}, Traceback: {str(sys.exc_info()[2])}", file=sys.stderr)
            if '429' in str(e) and attempt < max_retries - 1:
                print(f"Rate limit hit (429) on attempt {attempt + 1}. Retrying in 10 seconds...", file=sys.stderr)
                time.sleep(10)
                continue
            return jsonify({'error': str(e)}), 500
    print("Max retries reached, giving up", file=sys.stderr)
    return jsonify({'error': 'Max retries reached, please try again later'}), 429

@app.route('/download', methods=['POST'])
def download():
    print("Download route not implemented yet", file=sys.stderr)
    return jsonify({'error': 'Download not implemented'}), 501

if __name__ == '__main__':
    print("Starting app in debug mode", file=sys.stderr)
    app.run(debug=True, use_reloader=False)  # Disable reloader to avoid duplicate logs