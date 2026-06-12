import os
import requests
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(docs_url=None, redoc_url=None)

# ==========================================
# 📂 Directory & Static Setup
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ==========================================
# 🔒 Environment Secrets
# ==========================================
FRONTEND_API_KEY = os.getenv("FRONTEND_API_KEY", "my-super-secret-key")
BACKEND_URL = os.getenv("BACKEND_URL", "https://your-private-space-name.hf.space").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN")

api_key_header = APIKeyHeader(name="x-api-key", auto_error=True)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != FRONTEND_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key. Access Denied!")
    return api_key

# ==========================================
# 🌐 UI Routing
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/docs", response_class=HTMLResponse)
async def read_docs(request: Request):
    return templates.TemplateResponse(request=request, name="docs.html")

# ==========================================
# 📱 PWA & Static Routes (FastAPI Style)
# ==========================================
@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(os.path.join(BASE_DIR, "static/manifest.json"), media_type="application/manifest+json")

@app.get("/sw.js")
async def serve_sw():
    return FileResponse(os.path.join(BASE_DIR, "static/sw.js"), media_type="application/javascript")

@app.get("/favicon.ico")
async def serve_favicon():
    # अगर static फोल्डर में तुम्हारा कोई आइकॉन है, तो उसका नाम यहाँ सेट कर दो
    icon_path = os.path.join(BASE_DIR, "static/favicon.png") # या .ico
    if os.path.exists(icon_path):
        return FileResponse(icon_path, media_type="image/png")
    return {"message": "No favicon found"}

# ==========================================
# 🔄 API Proxy Routes
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
    if not BACKEND_URL or "your-private-space" in BACKEND_URL:
        raise HTTPException(status_code=500, detail="BACKEND_URL is not configured properly.")
        
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"} if HF_TOKEN else {"Content-Type": "application/json"}
    
    try:
        res = requests.post(f"{BACKEND_URL}/api/search", json=request_data.dict(), headers=headers, timeout=10)
        if res.status_code == 202 or res.status_code == 200:
            return res.json()
        raise HTTPException(status_code=res.status_code, detail=f"HF Space Error: {res.text[:100]}")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Backend is sleeping. Please wake it up.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")

@app.post("/api/timeline")
async def proxy_timeline(request_data: TimelineRequest, api_key: str = Depends(get_api_key)):
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"} if HF_TOKEN else {"Content-Type": "application/json"}
    try:
        res = requests.post(f"{BACKEND_URL}/api/timeline", json=request_data.dict(), headers=headers, timeout=10)
        if res.status_code == 202 or res.status_code == 200:
            return res.json()
        raise HTTPException(status_code=res.status_code, detail=f"HF Space Error: {res.text[:100]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")

@app.get("/api/status/{task_id}")
async def proxy_status(task_id: str, api_key: str = Depends(get_api_key)):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    try:
        res = requests.get(f"{BACKEND_URL}/api/status/{task_id}", headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
        raise HTTPException(status_code=res.status_code, detail=f"HF Space Error: {res.text[:100]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")

