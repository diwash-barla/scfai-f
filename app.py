import os
import requests
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Initialize Frontend Flask App
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# ==========================================
# 🔒 ENVIRONMENT SECRETS (Vercel ENV)
# ==========================================
BACKEND_URL = os.environ.get("BACKEND_URL", "https://your-private-space-name.hf.space")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# 🔥 तुम्हारा नया फ्रंटएंड सीक्रेट (API KEY)
FRONTEND_API_KEY = os.environ.get("FRONTEND_API_KEY", "my-super-secret-key")

def require_frontend_key(f):
    """
    🛡️ Security Bouncer: यह चेक करता है कि रिक्वेस्ट में सही API Key है या नहीं।
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Header में 'X-API-Key' नाम से की (Key) आनी चाहिए
        provided_key = request.headers.get("X-API-Key")
        
        if not provided_key or provided_key != FRONTEND_API_KEY:
            print("🚫 Blocked Unauthorized Access Attempt!")
            return jsonify({"success": False, "error": "Unauthorized Access. Invalid API Key."}), 401
            
        return f(*args, **kwargs)
    return decorated_function

def forward_to_backend(endpoint, method='POST', json_data=None):
    """Securely forwards requests to the private HF backend using the HF Token."""
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{BACKEND_URL.rstrip('/')}/{endpoint}"
    
    try:
        if method == 'POST':
            # Timeout छोटा है क्योंकि बैकएंड तुरंत task_id दे देता है
            response = requests.post(url, headers=headers, json=json_data, timeout=10)
        else:
            response = requests.get(url, headers=headers, timeout=10)
            
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Frontend Proxy Error: {str(e)}"}), 500

# ==========================================
# 🌐 UI Routing (Serves HTML & PWA Files)
# ==========================================
@app.route('/')
def serve_index():
    # Will serve index.html from a /templates folder
    return send_from_directory('templates', 'index.html')

@app.route('/<path:filename>')
def serve_static_files(filename):
    # Will serve manifest.json, sw.js, icons from a /static folder
    return send_from_directory('static', filename)

# ==========================================
# 🔄 API Proxy Routes (Secured with FRONTEND_API_KEY)
# ==========================================
@app.route('/api/search', methods=['POST'])
@require_frontend_key  # 🔒 Security Layer
def proxy_search():
    return forward_to_backend('api/search', method='POST', json_data=request.get_json())

@app.route('/api/timeline', methods=['POST'])
@require_frontend_key  # 🔒 Security Layer
def proxy_timeline():
    return forward_to_backend('api/timeline', method='POST', json_data=request.get_json())

@app.route('/api/status/<task_id>', methods=['GET'])
@require_frontend_key  # 🔒 Security Layer
def proxy_status(task_id):
    return forward_to_backend(f'api/status/{task_id}', method='GET')

if __name__ == '__main__':
    print("Starting Secured Public Frontend Proxy Server...")
    # Render/Vercel handles ports dynamically via PORT env variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
