python
import os
import logging
from flask import Flask, request, jsonify, send_file
from engine import StockEngine

# Configure basic logging for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
# Using current directory for static files since we only have index.html
app = Flask(__name__, static_folder='.', static_url_path='')

# Initialize the business logic engine
pexels_key = os.environ.get("PEXELS_API_KEY", "")
pixabay_key = os.environ.get("PIXABAY_API_KEY", "")

stock_engine = StockEngine(pexels_key=pexels_key, pixabay_key=pixabay_key)

@app.route('/', methods=['GET'])
def serve_frontend():
    """Serves the single-page application frontend."""
    try:
        return send_file('index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return "Frontend not found. Please ensure index.html is in the same directory.", 404

@app.route('/search', methods=['POST'])
def search_api():
    """
    Main API endpoint for searching stock footage.
    Expects JSON: { "query": str, "orientation": str, "quality": str }
    """
    try:
        # Validate JSON request
        if not request.is_json:
            return jsonify({
                "success": False, 
                "error": "Invalid request. Content-Type must be application/json."
            }), 400
            
        data = request.get_json()
        
        # Extract and sanitize parameters
        query = str(data.get('query', '')).strip()
        orientation = str(data.get('orientation', 'landscape')).strip().lower()
        quality = str(data.get('quality', 'any')).strip().lower()
        
        # Validation checks
        if not query:
            return jsonify({"success": False, "error": "Search query cannot be empty."}), 400
            
        valid_orientations = ['landscape', 'portrait']
        if orientation not in valid_orientations:
            return jsonify({"success": False, "error": f"Invalid orientation. Must be one of {valid_orientations}."}), 400
            
        valid_qualities = ['any', '720', '1080', '4k']
        if quality not in valid_qualities:
            return jsonify({"success": False, "error": f"Invalid quality. Must be one of {valid_qualities}."}), 400

        # Check API Keys
        if not stock_engine.has_keys():
            return jsonify({
                "success": False,
                "error": "API Keys are missing. Please configure PEXELS_API_KEY and PIXABAY_API_KEY in the environment."
            }), 500

        logger.info(f"Processing search: query='{query}', orientation='{orientation}', quality='{quality}'")
        
        # Execute business logic (Loose coupling: Flask knows nothing about how search works)
        results = stock_engine.execute_search(
            query=query, 
            orientation=orientation, 
            quality=quality
        )
        
        return jsonify({
            "success": True,
            "count": len(results),
            "clips": results
        }), 200

    except Exception as e:
        # Graceful error handling - never crash the server
        logger.exception(f"Unexpected server error during search: {e}")
        return jsonify({
            "success": False, 
            "error": "An unexpected error occurred on the server while processing your request."
        }), 500

if __name__ == '__main__':
    # Run production-ready server (debug off by default)
    print("Starting StockClip Finder AI Server...")
    print("Ensure PEXELS_API_KEY and PIXABAY_API_KEY are set.")
    app.run(host='0.0.0.0', port=5000, debug=False)
