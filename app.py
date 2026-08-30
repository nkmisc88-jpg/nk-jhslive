from flask import Flask, request, Response
import requests

app = Flask(__name__)

# This new route prevents the 404 error when you visit the main link
@app.route('/')
def home():
    return "Render Proxy is Live and Running!", 200

@app.route('/play')
def play():
    # The URL of the actual stream passed from your M3U playlist
    channel_url = request.args.get('url')
    if not channel_url:
        return "No stream URL provided", 400

    # Spoof the headers to bypass the 403 Access Denied error
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://stream4liv.netlify.app/",
        "Origin": "https://stream4liv.netlify.app"
    }
    
    try:
        # Fetch the stream manifest dynamically
        resp = requests.get(channel_url, headers=headers, stream=True)
        
        # Filter out headers that disrupt the proxy transfer
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        proxy_headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        
        # Return the verified manifest directly to your Android player
        return Response(resp.iter_content(chunk_size=1024), resp.status_code, proxy_headers)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
