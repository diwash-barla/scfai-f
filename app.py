import os
import logging
import uuid
import threading
from flask import Flask, request, jsonify
from engine import StockEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize the Engine
pexels_key = os.environ.get("PEXELS_API_KEY", "")
pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
groq_key = os.environ.get("GROQ_API_KEY", "") 

stock_engine = StockEngine(pexels_key=pexels_key, pixabay_key=pixabay_key, groq_key=groq_key)

# In-Memory Task Queue
tasks = {}

def background_worker(task_id: str, mode: str, query: str, orientation: str, quality: str):
    """Background thread to process AI tasks without blocking the API."""
    try:
        if mode == 'search':
            results = stock_engine.execute_search(query=query, orientation=orientation, quality=quality)
            tasks[task_id] = {"status": "completed", "data": results, "count": len(results)}
        elif mode == 'timeline':
            results = stock_engine.generate_video_timeline(script=query, orientation=orientation, quality=quality)
            tasks[task_id] = {"status": "completed", "data": results, "scene_count": len(results)}
    except Exception as e:
        logger.exception(f"Task Failed: {e}")
        tasks[task_id] = {"status": "error", "error": str(e)}

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.get_json()
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "processing"}
    
    thread = threading.Thread(target=background_worker, args=(task_id, 'search', data.get('query'), data.get('orientation'), data.get('quality')))
    thread.start()
    
    return jsonify({"success": True, "task_id": task_id}), 202

@app.route('/api/timeline', methods=['POST'])
def api_timeline():
    data = request.get_json()
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "processing"}
    
    thread = threading.Thread(target=background_worker, args=(task_id, 'timeline', data.get('script'), data.get('orientation'), data.get('quality')))
    thread.start()
    
    return jsonify({"success": True, "task_id": task_id}), 202

@app.route('/api/status/<task_id>', methods=['GET'])
def api_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Invalid Task ID."}), 404
    return jsonify({"success": True, "task": task}), 200

if __name__ == '__main__':
    print("Starting Private Backend Microservice...")
    # HF Spaces requires port 7860
    app.run(host='0.0.0.0', port=7860, debug=False, threaded=True)
