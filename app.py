import os
import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ==========================================
# ⚙️ Setup & Logging
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 🔒 Environment Secrets
# ==========================================
FRONTEND_API_KEY = os.getenv("FRONTEND_API_KEY", "my-super-secret-key")
BACKEND_URL = os.getenv("BACKEND_URL", "https://your-private-space-name.hf.space").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN")

# ==========================================
# 🚀 Lifespan (Global HTTP Client with Connection Pooling)
# ==========================================
# यह ग्लोबल क्लाइंट कनेक्शन्स को री-यूज़ करेगा, जिससे TCP हैंडशेक का टाइम बचेगा
http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    
    # Startup Validation
    if not BACKEND_URL or "your-private-space" in BACKEND_URL:
        logger.warning("⚠️ BACKEND_URL is not properly configured. Proxy might fail!")
    
    # Timeout 20s रखा है, क्योंकि HF Spaces को जागने (Cold start) में टाइम लगता है
    http_client = httpx.AsyncClient(timeout=20.0, limits=httpx.Limits(max_keepalive_connections=50))
    logger.info("✅ Global HTTPX Client Initialized")
    
    yield  # यहाँ ऐप रन होती रहेगी
    
    # Shutdown Cleanup
    await http_client.aclose()
    logger.info("🛑 Global HTTPX Client Closed")

app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)

# ==========================================
# 📂 Directory & Static Setup
# ==========================================
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

api_key_header = APIKeyHeader(name="x-api-key", auto_error=True)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != FRONTEND_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key. Access Denied!")
    return api_key

# ==========================================
# 🔄 Proxy Helper Function (DRY Principle)
# ==========================================
async def forward_request(method: str, endpoint: str, payload: dict = None):
    """सेंट्रल फंक्शन जो सारी HTTP रिक्वेस्ट्स को बैकएंड पर भेजेगा"""
    headers = {"Content-Type": "application/json"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
        
    url = f"{BACKEND_URL}{endpoint}"
    
    try:
        if method.upper() == "POST":
            res = await http_client.post(url, json=payload, headers=headers)
        else:
            res = await http_client.get(url, headers=headers)
            
        if res.status_code in [200, 202]:
            return res.json()
            
        raise HTTPException(status_code=res.status_code, detail=f"Backend Error: {res.text[:100]}")
        
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Backend (HF Space) is sleeping. Please wake it up.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Proxy forwarding failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Proxy Error")

# ==========================================
# 🌐 UI & Static Routes
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(os.path.join(BASE_DIR, "static/manifest.json"), media_type="application/manifest+json")

@app.get("/sw.js")
async def serve_sw():
    return FileResponse(os.path.join(BASE_DIR, "static/sw.js"), media_type="application/javascript")

# ==========================================
# 🚀 API Proxy Routes (अब एकदम क्लीन और छोटे हैं)
# ==========================================
class SearchRequest(BaseModel):
    query: str
    orientation: str = "landscape"
    quality: str = "any"

class TimelineRequest(BaseModel):
    script: str
    orientation: str = "landscape"
    quality: str = "any"

@app.post("/api/search")
async def proxy_search(request_data: SearchRequest, api_key: str = Depends(get_api_key)):
    return await forward_request("POST", "/api/search", request_data.model_dump())

@app.post("/api/timeline")
async def proxy_timeline(request_data: TimelineRequest, api_key: str = Depends(get_api_key)):
    return await forward_request("POST", "/api/timeline", request_data.model_dump())

@app.get("/api/status/{task_id}")
async def proxy_status(task_id: str, api_key: str = Depends(get_api_key)):
    return await forward_request("GET", f"/api/status/{task_id}")
