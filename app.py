import os
import logging
from flask import Flask, request, jsonify, send_file
from engine import StockEngine

# Configure basic logging for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='.', static_url_path='')

# Initialize the V3 Engine
pexels_key = os.environ.get("PEXELS_API_KEY", "")
pixabay_key = os.environ.get("PIXABAY_API_KEY", "")

stock_engine = StockEngine(pexels_key=pexels_key, pixabay_key=pixabay_key)

@app.route('/', methods=['GET'])
def serve_frontend():
    """Serves the single-page application frontend."""
    return send_file('index.html')

@app.route('/search', methods=['POST'])
def search_api():
    """Main API endpoint for searching stock footage."""
    try:
        data = request.get_json()
        query = str(data.get('query', '')).strip()
        orientation = str(data.get('orientation', 'landscape')).strip().lower()
        quality = str(data.get('quality', 'any')).strip().lower()

        if not stock_engine.has_keys():
            return jsonify({"success": False, "error": "API Keys missing. Configure PEXELS_API_KEY and PIXABAY_API_KEY."}), 500

        results = stock_engine.execute_search(query=query, orientation=orientation, quality=quality)
        
        return jsonify({"success": True, "count": len(results), "clips": results}), 200

    except Exception as e:
        logger.exception(f"Search API Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/generate-timeline', methods=['POST'])
def timeline_api():
    """
    Script-to-Footage API Pipeline.
    Takes a full script, breaks it into scenes, and finds the best video for each scene.
    """
    try:
        data = request.get_json()
        script = str(data.get('script', '')).strip()
        orientation = str(data.get('orientation', 'landscape')).strip().lower()
        quality = str(data.get('quality', 'any')).strip().lower()

        if not script:
            return jsonify({"success": False, "error": "Script cannot be empty."}), 400

        if not stock_engine.has_keys():
            return jsonify({"success": False, "error": "API Keys missing."}), 500

        logger.info("Starting Script-to-Footage Autonomous Pipeline...")
        timeline = stock_engine.generate_video_timeline(script=script, orientation=orientation, quality=quality)
        
        return jsonify({"success": True, "scene_count": len(timeline), "timeline": timeline}), 200

    except Exception as e:
        logger.exception(f"Timeline API Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    print("Starting StockClip Finder AI Server (V3 + AutoPilot)...")
    app.run(host='0.0.0.0', port=7860, debug=False)