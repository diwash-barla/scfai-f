import json
import urllib.request
import urllib.parse
import concurrent.futures
import hashlib
import numpy as np
import re
import requests
import cv2
import threading
import gc
from PIL import Image
from io import BytesIO
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer, util
import faiss
from deep_translator import GoogleTranslator

class StockEngine:
    """
    🔥 StockClip Finder AI - Engine V14 (THE JSON VALIDATOR)
    Includes: User's Custom JSON Parsing, Retry Logic, Zero Cache, and Strict Bouncers.
    """

    def __init__(self, pexels_key: str, pixabay_key: str, groq_key: str = ""):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.groq_key = groq_key
        self.max_results = 12
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        print("🚀 Loading Text AI Model (FAISS & KeyBERT)...")
        self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        print("👁️ Loading Vision AI Model (CLIP Extreme)...")
        self.clip_model = SentenceTransformer("clip-ViT-B-32")
        
        self.scene_anchors = {
            "Drone/Aerial": self.model.encode("aerial drone bird eye view flying above", convert_to_tensor=False),
            "Macro/Close-up": self.model.encode("macro close up extremely detailed zoom", convert_to_tensor=False),
            "Timelapse": self.model.encode("timelapse fast motion clouds passing time", convert_to_tensor=False),
            "Cinematic": self.model.encode("cinematic depth of field moody dramatic lighting", convert_to_tensor=False)
        }
        print("✅ Engine V14 (JSON Strict Mode) ready!")

    def has_keys(self) -> bool:
        return bool(self.pexels_key and self.pixabay_key)

    # =====================================================
    # 🧠 KeyBERT: AI VECTOR KEYWORD EXTRACTOR
    # =====================================================
    def _extract_visual_keywords(self, scene_text: str) -> tuple:
        try:
            en_text = GoogleTranslator(source='auto', target='en').translate(scene_text)
        except Exception:
            en_text = scene_text
        
        clean_text = re.sub(r'[^\w\s]', '', en_text.lower())
        words = clean_text.split()
        
        basic_stops = {"it", "is", "the", "a", "an", "and", "or", "to", "in", "on", "at", "of", "for", "with", "that", "this", "you", "are", "we", "i"}
        filtered_words = [w for w in words if w not in basic_stops]
        
        if not filtered_words:
            return en_text, "mysterious cinematic landscape"

        candidates = []
        for n in range(1, 4):
            for i in range(len(filtered_words) - n + 1):
                phrase = " ".join(filtered_words[i:i+n])
                if phrase not in candidates:
                    candidates.append(phrase)

        if not candidates:
            return en_text, " ".join(filtered_words[:4])

        doc_emb = self.model.encode([en_text], convert_to_tensor=False).astype('float32')
        cand_embs = self.model.encode(candidates, convert_to_tensor=False).astype('float32')
        
        faiss.normalize_L2(doc_emb)
        faiss.normalize_L2(cand_embs)
        
        sims = np.dot(cand_embs, doc_emb.T).flatten()
        best_idx = np.argmax(sims)
        best_phrase = candidates[best_idx]
        
        return en_text, best_phrase

    # =====================================================
    # ⚡ GROQ API SMART EXPANSION (JSON VALIDATOR LOGIC)
    # =====================================================
    def _fallback(self, q: str, queries=None):
        if queries is None:
            queries = [q]

        fallbacks = [
            f"{q} cinematic shot",
            f"{q} 4k ultra hd",
            f"{q} slow motion",
            f"{q} wide angle view",
            f"{q} natural lighting"
        ]

        for fb in fallbacks:
            if len(queries) < 6:
                queries.append(fb)

        return queries[:6]

    def _expand_query(self, q: str) -> List[str]:
        q = q.lower().strip()
        base_query = q
        queries = [base_query]

        if not self.groq_key:
            return self._fallback(base_query)

        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }

        system_prompt = """
You are a strict stock footage query generator.

RULES:
1. Return ONLY a valid JSON array of 5 strings.
2. Each string must be 2-5 words.
3. DO NOT change the core subject of the scene.
4. If subject includes an object (dog, man, car), EVERY query MUST include it.
5. Only vary environment, angle, lighting, cinematic style.
6. No explanation, no text, no commas outside JSON.
"""

        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Scene: {q}"}
            ],
            "temperature": 0.3
        }

        def call_api():
            return requests.post(
                "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)",
                headers=headers,
                json=payload,
                timeout=12
            )

        try:
            res = call_api()

            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]

                try:
                    # Clean markdown wrappers if AI adds them
                    clean_content = content.replace('```json', '').replace('```', '').strip()
                    groq_queries = json.loads(clean_content)

                    # Validation layer (VERY IMPORTANT)
                    cleaned = []
                    subject = base_query.split()[0] if base_query else ""
                    for item in groq_queries:
                        if isinstance(item, str) and len(item.split()) <= 6:
                            if subject in item.lower():  # Subject lock check
                                cleaned.append(item.strip())

                    print(f"⚡ [Groq AI JSON Validated]: {cleaned}")
                    queries.extend(cleaned[:5])

                except Exception:
                    print("⚠️ JSON Parse Failed. Retrying with STRICT MODE...")
                    # Retry once with stricter prompt
                    payload["messages"][0]["content"] += "\nRETURN ONLY JSON ARRAY. STRICT MODE."
                    res2 = call_api()

                    if res2.status_code == 200:
                        try:
                            content2 = res2.json()["choices"][0]["message"]["content"]
                            clean_content2 = content2.replace('```json', '').replace('```', '').strip()
                            groq_queries = json.loads(clean_content2)
                            queries.extend(groq_queries[:5])
                            print(f"⚡ [Groq AI Retry Success]: {groq_queries[:5]}")
                        except Exception as e:
                            print(f"⚠️ Retry Parse Failed: {e}")
                            pass

        except Exception as e:
            print(f"⚠️ Groq API Connection Failed: {e}")

        # Fallback safety net
        queries = self._fallback(base_query, queries)

        return queries[:6]

    # =====================================================
    # 👁️ HYBRID MULTIMODAL STREAMING GRABBER
    # =====================================================
    def _fetch_visual_context(self, clip: Dict) -> tuple:
        try:
            res = requests.get(clip['thumbnail'], timeout=3)
            if res.status_code == 200:
                img = Image.open(BytesIO(res.content)).convert("RGB")
                return clip, img, "Thumbnail"
        except Exception:
            pass
        
        try:
            video_url = clip['download_url']
            cap = cv2.VideoCapture(video_url)
            if cap.isOpened():
                for _ in range(5):
                    ret, _ = cap.read()
                    if not ret: break
                ret, frame = cap.read()
                cap.release()
                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    return clip, img, "VideoFrame"
        except Exception:
            pass
            
        return clip, None, "Failed"

    def _vision_score_candidates(self, target_english_text: str, clips: List[Dict]) -> List[Dict]:
        if not clips: return []
        
        valid_clips = []
        failed_clips = []
        images = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            results = ex.map(self._fetch_visual_context, clips)
            
        for c, img, source_type in results:
            if img is not None:
                valid_clips.append((c, source_type))
                images.append(img)
            else:
                c['visual_score'] = 0.0
                c['quality_label'] = f"{c['quality_label'].split(' | ')[0]} | ❌ Vision: Failed"
                c['score'] = round(c['score'] * 0.3) 
                failed_clips.append(c)
                
        if not valid_clips:
            return clips 
            
        img_embeddings = self.clip_model.encode(images, convert_to_tensor=True)
        txt_embedding = self.clip_model.encode([target_english_text], convert_to_tensor=True)
        
        sims = util.cos_sim(txt_embedding, img_embeddings)[0].cpu().tolist()
        
        for i, (c, source_type) in enumerate(valid_clips):
            vision_score = max(0.0, sims[i])
            c['visual_score'] = round(vision_score * 100, 2)
            c['quality_label'] = f"{c['quality_label'].split(' | ')[0]} | {source_type}: {c['visual_score']}%"
            c['score'] = min(round((c['score'] * 0.4) + (c['visual_score'] * 0.6)), 100)
            
        all_scored_clips = [item[0] for item in valid_clips] + failed_clips
        all_scored_clips.sort(key=lambda x: x['score'], reverse=True)

        del images
        del img_embeddings
        del txt_embedding
        gc.collect()

        return all_scored_clips

    # =====================================================
    # 🛤️ PURE ISOLATED TRACK WITH STRICT THRESHOLDS
    # =====================================================
    def _process_single_query_track(self, q: str, orientation: str, quality: str, full_context: str, global_seen_ids: set, seen_lock: threading.Lock) -> List[Dict]:
        raw_pex = self._fetch_pexels(q, orientation)
        raw_pix = self._fetch_pixabay(q, orientation)

        filtered_pex = self._filter(raw_pex, orientation, quality)
        filtered_pix = self._filter(raw_pix, orientation, quality)

        scored_pex = self._faiss_semantic_score(filtered_pex, q) if filtered_pex else []
        scored_pix = self._faiss_semantic_score(filtered_pix, q) if filtered_pix else []

        top_pex_candidates = scored_pex[:5]
        top_pix_candidates = scored_pix[:5]

        vision_pex = self._vision_score_candidates(full_context, top_pex_candidates) if top_pex_candidates else []
        vision_pix = self._vision_score_candidates(full_context, top_pix_candidates) if top_pix_candidates else []

        track_winners = []
        
        MIN_VISION_SCORE = 21.0
        MIN_FINAL_SCORE = 40

        if vision_pex:
            with seen_lock:
                for vp in vision_pex:
                    if vp['visual_score'] >= MIN_VISION_SCORE and vp['score'] >= MIN_FINAL_SCORE:
                        if vp['id'] not in global_seen_ids:
                            global_seen_ids.add(vp['id']) 
                            track_winners.append(vp)
                            break

        if vision_pix:
            with seen_lock:
                for vp in vision_pix:
                    if vp['visual_score'] >= MIN_VISION_SCORE and vp['score'] >= MIN_FINAL_SCORE:
                        if vp['id'] not in global_seen_ids:
                            global_seen_ids.add(vp['id']) 
                            track_winners.append(vp)
                            break

        return track_winners

    # =====================================================
    # MAIN SEARCH PIPELINE
    # =====================================================
    def execute_search(self, query: str, orientation: str, quality: str, full_context: str = None) -> List[Dict[str, Any]]:
        if not full_context:
            try: full_context = GoogleTranslator(source='auto', target='en').translate(query)
            except: full_context = query
                
        queries_to_run = self._expand_query(query) 
        all_final_winners = []
        
        global_seen_ids = set()
        seen_lock = threading.Lock()

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futures = [ex.submit(self._process_single_query_track, q, orientation, quality, full_context, global_seen_ids, seen_lock) for q in queries_to_run]
            for f in concurrent.futures.as_completed(futures):
                all_final_winners.extend(f.result())

        final_results = self._detect_scenes(all_final_winners)

        final_results.sort(key=lambda x: x["score"], reverse=True)
        return final_results[:self.max_results]

    # =====================================================
    # SCRIPT-TO-FOOTAGE PIPELINE
    # =====================================================
    def generate_video_timeline(self, script: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        raw_scenes = re.split(r'[.।|\n]+', script)
        scenes = [s.strip() for s in raw_scenes if len(s.strip()) > 15] 
        
        timeline = []
        for scene_text in scenes[:6]:
            full_en_text, search_query = self._extract_visual_keywords(scene_text)
            candidates = self.execute_search(query=search_query, orientation=orientation, quality=quality, full_context=full_en_text)
            
            timeline.append({
                "scene_text": scene_text,
                "clip": candidates[0] if candidates else None
            })
            
        return timeline

    # =====================================================
    # FETCHING & UTILITIES
    # =====================================================
    def _fetch_pexels(self, query: str, orientation: str):
        api_orient = "landscape" if orientation == "landscape" else "portrait"
        url = f"[https://api.pexels.com/videos/search?query=](https://api.pexels.com/videos/search?query=){urllib.parse.quote(query)}&per_page=10&orientation={api_orient}"
        req = urllib.request.Request(url, headers={**self.headers, "Authorization": self.pexels_key})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return [self._norm_pexels(v, query) for v in json.loads(r.read().decode()).get("videos", [])]
        except: return []

    def _norm_pexels(self, v: dict, query_used: str):
        files = sorted(v.get("video_files", []), key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
        best = files[0] if files else {}
        slug_words = [p for p in urllib.parse.urlparse(v.get('url', '')).path.split('/') if p][-1].split('-') if len(urllib.parse.urlparse(v.get('url', '')).path.split('/')) >= 2 else []
        extracted_tags = " ".join(slug_words[:-1] if slug_words and slug_words[-1].isdigit() else slug_words)

        return {
            "id": str(v.get("id")), "source": "Pexels", "url": v.get("url"),
            "download_url": best.get("link"), "thumbnail": v.get("image"),
            "width": best.get("width", 0), "height": best.get("height", 0),
            "duration": v.get("duration", 0), "views": 0, "likes": 0,
            "tags": extracted_tags, "query_used": query_used
        }

    def _fetch_pixabay(self, query: str, orientation: str):
        url = f"[https://pixabay.com/api/videos/?key=](https://pixabay.com/api/videos/?key=){self.pixabay_key}&q={urllib.parse.quote(query)}&per_page=10"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return [self._norm_pixabay(v, query) for v in json.loads(r.read().decode()).get("hits", [])]
        except: return []

    def _norm_pixabay(self, v: dict, query_used: str):
        vids = v.get("videos", {})
        best = vids.get("large") or vids.get("medium") or vids.get("small") or {}
        thumb_id = v.get('picture_id')
        thumb = f"[https://i.vimeocdn.com/video/](https://i.vimeocdn.com/video/){thumb_id}_640x360.jpg" if thumb_id else ""
        return {
            "id": str(v.get("id")), "source": "Pixabay", "url": v.get("pageURL"),
            "download_url": best.get("url"), "thumbnail": thumb,
            "width": best.get("width", 0), "height": best.get("height", 0),
            "duration": v.get("duration", 0), "views": v.get("views", 0), "likes": v.get("likes", 0),
            "tags": v.get('tags', ''), "query_used": query_used
        }

    def _filter(self, clips, orientation, quality):
        out = []
        for c in clips:
            w, h = c["width"], c["height"]
            if not w or not h: continue
            ratio = w / h
            if orientation == "landscape" and not (1.70 <= ratio <= 1.85): continue
            if orientation == "portrait" and not (0.50 <= ratio <= 0.60): continue
            if quality == "720" and h < 720: continue
            if quality == "1080" and h < 1080: continue
            if quality == "4k" and h < 2160: continue
            if c.get("download_url"): out.append(c)
        return out

    def _get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_tensor=False).astype('float32')

    def _faiss_semantic_score(self, clips, query):
        if not clips: return []
        
        q_emb = self._get_embeddings_batch([query])
        faiss.normalize_L2(q_emb)

        texts = [f"{c['tags']} {c['source']}" for c in clips]
        clip_embs = self._get_embeddings_batch(texts)
        faiss.normalize_L2(clip_embs)

        index = faiss.IndexFlatIP(clip_embs.shape[1])
        index.add(clip_embs)
        sims, _ = index.search(q_emb, len(clips))
        sims = sims[0]

        scored = []

        for i, c in enumerate(clips):
            sim = max(0.0, float(sims[i]))
            if sim < 0.15: continue

            h = c["height"]
            res_score = 1.0 if h >= 2160 else (0.8 if h >= 1080 else 0.5)
            eng = min(0.6 + (res_score * 0.3), 1.0) 
            duration_score = 1.0 if 6 <= c["duration"] <= 18 else 0.7

            final = (sim * 0.50) + (res_score * 0.20) + (eng * 0.20) + (duration_score * 0.10)
            c["score"] = min(round(final * 100), 100)
            c['quality_label'] = "4K" if h >= 2160 else ("1080p" if h >= 1080 else "720p")
            c['aspect_ratio'] = f"{c['width']}x{c['height']}"
            scored.append(c)

        del q_emb
        del clip_embs
        gc.collect()

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def _detect_scenes(self, clips):
        for c in clips:
            c["scene_type"] = "General" 
        return clips
