import os
import logging
import uuid
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from engine import StockEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app and Enable CORS for Vercel Frontend
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app) 

# Initialize the V15 Engine
pexels_key = os.environ.get("PEXELS_API_KEY", "")
pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
groq_key = os.environ.get("GROQ_API_KEY", "") 

stock_engine = StockEngine(pexels_key=pexels_key, pixabay_key=pixabay_key, groq_key=groq_key)

# Global Task Dictionary (In-Memory Queue)
# To prevent OOM errors, we could limit concurrent threads here in the future
tasks = {}

def background_worker(task_id: str, mode: str, query: str, orientation: str, quality: str):
    """Runs the heavy AI engine in the background to prevent Vercel timeouts."""
    try:
        if mode == 'search':
            results = stock_engine.execute_search(query=query, orientation=orientation, quality=quality)
            tasks[task_id] = {"status": "completed", "data": results, "count": len(results)}
        elif mode == 'timeline':
            results = stock_engine.generate_video_timeline(script=query, orientation=orientation, quality=quality)
            tasks[task_id] = {"status": "completed", "data": results, "scene_count": len(results)}
    except Exception as e:
        logger.exception(f"Background Task Failed: {e}")
        tasks[task_id] = {"status": "error", "error": str(e)}

@app.route('/', methods=['GET'])
def serve_frontend():
    return send_file('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """Starts a Search Task and returns a Task ID."""
    try:
        data = request.get_json()
        query = str(data.get('query', '')).strip()
        orientation = str(data.get('orientation', 'landscape')).strip().lower()
        quality = str(data.get('quality', 'any')).strip().lower()

        if not stock_engine.has_keys():
            return jsonify({"success": False, "error": "API Keys missing. Configure Space Secrets."}), 500

        task_id = str(uuid.uuid4())
        tasks[task_id] = {"status": "processing"}
        
        # Start background thread
        thread = threading.Thread(target=background_worker, args=(task_id, 'search', query, orientation, quality))
        thread.start()
        
        return jsonify({"success": True, "task_id": task_id}), 202

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/timeline', methods=['POST'])
def api_timeline():
    """Starts a Timeline Task and returns a Task ID."""
    try:
        data = request.get_json()
        script = str(data.get('script', '')).strip()
        orientation = str(data.get('orientation', 'landscape')).strip().lower()
        quality = str(data.get('quality', 'any')).strip().lower()

        if not script:
            return jsonify({"success": False, "error": "Script cannot be empty."}), 400

        task_id = str(uuid.uuid4())
        tasks[task_id] = {"status": "processing"}
        
        thread = threading.Thread(target=background_worker, args=(task_id, 'timeline', script, orientation, quality))
        thread.start()
        
        return jsonify({"success": True, "task_id": task_id}), 202

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/status/<task_id>', methods=['GET'])
def api_status(task_id):
    """Endpoint for Vercel to poll the task status."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Invalid Task ID or Task Expired."}), 404
    
    # If completed or error, we can optionally delete the task from dict to free memory
    # but we'll leave it for a while in a real prod env. We'll return it directly.
    return jsonify({"success": True, "task": task}), 200

if __name__ == '__main__':
    print("Starting StockClip Microservice Server (V15 + Task Queue)...")
    app.run(host='0.0.0.0', port=7860, debug=False, threaded=True)
