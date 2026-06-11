import json
import urllib.request
import urllib.parse
import concurrent.futures
import hashlib
import numpy as np
import re
import requests
import cv2
from PIL import Image
from io import BytesIO
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer, util
import faiss
from sklearn.cluster import KMeans
from deep_translator import GoogleTranslator

class StockEngine:
    """
    🔥 StockClip Finder AI - Engine V8 (GOD MODE)
    Includes: Groq API Smart Queries, KeyBERT, FAISS, KMeans, and Vision Reranker.
    """

    def __init__(self, pexels_key: str, pixabay_key: str, groq_key: str = ""):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.groq_key = groq_key
        self.max_results = 12
        
        self.embedding_cache = {}
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
        print("✅ Engine V8 (Groq API Integrated) ready!")

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
    # ⚡ GROQ API SMART EXPANSION (NEW)
    # =====================================================
    def _expand_query(self, q: str) -> Dict[str, List[str]]:
        q = q.lower().strip()
        queries = [q] # 1 Raw Query (User's / KeyBERT's choice)
        
        if self.groq_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "meta-llama/llama-4-scout-17b-16e-instruct", # Blazing fast
                    "messages": [
                        {"role": "system", "content": "You are an expert stock footage researcher. Given a visual scene, generate exactly 5 highly distinct, optimized search queries (2-4 words each) to find stock footage on Pexels/Pixabay. Return ONLY a comma-separated list of the 5 queries. No numbers, no intro."},
                        {"role": "user", "content": f"Scene: {q}"}
                    ],
                    "temperature": 0.7
                }
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=5)
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"]
                    # Clean and extract the comma-separated list
                    groq_queries = [x.strip().strip('"').strip("'") for x in content.split(',') if len(x.strip()) > 2]
                    print(f"⚡ [Groq AI] Generated Queries: {groq_queries}")
                    queries.extend(groq_queries[:5])
            except Exception as e:
                print(f"⚠️ Groq Expansion Failed (Fallback to generic): {e}")

        # Fallback in case Groq is not configured or failed
        if len(queries) < 6:
            fallbacks = [f"{q} cinematic", f"{q} wide shot", f"{q} dramatic", f"{q} 4k", f"{q} abstract"]
            for fb in fallbacks:
                if len(queries) < 6: queries.append(fb)

        # Send all 6 variations to both platforms
        return {"pexels": queries[:6], "pixabay": queries[:6]}

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

    def _batch_vision_score(self, target_english_text: str, clips: List[Dict]) -> List[Dict]:
        if not clips: return []
        
        valid_clips = []
        failed_clips = []
        images = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
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
        return all_scored_clips

    # =====================================================
    # SCRIPT-TO-FOOTAGE PIPELINE (AUTO-PILOT)
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
    # MAIN SEARCH PIPELINE
    # =====================================================
    def execute_search(self, query: str, orientation: str, quality: str, full_context: str = None) -> List[Dict[str, Any]]:
        if not full_context:
            try: full_context = GoogleTranslator(source='auto', target='en').translate(query)
            except: full_context = query
                
        expanded = self._expand_query(query) # Using Groq now!
        raw = self._fetch_all(expanded, orientation)

        filtered = self._filter(raw, orientation, quality)
        deduped = self._deduplicate(filtered)
        
        if not deduped: return []

        scored_text = self._faiss_semantic_score(deduped, query)
        
        top_candidates = scored_text[:24]
        vision_verified = self._batch_vision_score(target_english_text=full_context, clips=top_candidates)
        
        processed = self._detect_scenes(vision_verified)
        final_results = self._kmeans_diversity(processed)

        for c in final_results:
            c.pop("vector", None)

        return final_results[:self.max_results]

    # =====================================================
    # FETCHING & UTILITIES
    # =====================================================
    def _fetch_all(self, expanded: Dict[str, List[str]], orientation: str):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = []
            for q in expanded["pexels"]: futures.append(ex.submit(self._fetch_pexels, q, orientation))
            for q in expanded["pixabay"]: futures.append(ex.submit(self._fetch_pixabay, q, orientation))
            for f in concurrent.futures.as_completed(futures):
                try: results.extend(f.result())
                except: continue
        return results

    def _fetch_pexels(self, query: str, orientation: str):
        api_orient = "landscape" if orientation == "landscape" else "portrait"
        url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=10&orientation={api_orient}"
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
        url = f"https://pixabay.com/api/videos/?key={self.pixabay_key}&q={urllib.parse.quote(query)}&per_page=10"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return [self._norm_pixabay(v, query) for v in json.loads(r.read().decode()).get("hits", [])]
        except: return []

    def _norm_pixabay(self, v: dict, query_used: str):
        vids = v.get("videos", {})
        best = vids.get("large") or vids.get("medium") or vids.get("small") or {}
        thumb_id = v.get('picture_id')
        thumb = f"https://i.vimeocdn.com/video/{thumb_id}_640x360.jpg" if thumb_id else ""
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

    def _deduplicate(self, clips):
        seen, out = set(), []
        for c in clips:
            fp = hashlib.md5(f"{c['width']}x{c['height']}_{c['duration']}_{c['source']}".encode()).hexdigest()
            if fp not in seen:
                seen.add(fp)
                out.append(c)
        return out

    def _get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        embeddings, texts_to_compute, indices_to_compute = [], [], []
        for i, text in enumerate(texts):
            if text in self.embedding_cache:
                embeddings.append(self.embedding_cache[text])
            else:
                embeddings.append(None)
                texts_to_compute.append(text)
                indices_to_compute.append(i)
        if texts_to_compute:
            computed_embs = self.model.encode(texts_to_compute, convert_to_tensor=False)
            for i, idx in enumerate(indices_to_compute):
                emb = computed_embs[i]
                self.embedding_cache[texts_to_compute[i]] = emb
                embeddings[idx] = emb
        return np.vstack(embeddings).astype('float32')

    def _faiss_semantic_score(self, clips, query):
        q_emb = self._get_embeddings_batch([query])
        faiss.normalize_L2(q_emb)

        texts = [f"{c['tags']} {c['source']}" for c in clips]
        clip_embs = self._get_embeddings_batch(texts)
        faiss.normalize_L2(clip_embs)

        index = faiss.IndexFlatIP(clip_embs.shape[1])
        index.add(clip_embs)
        sims, _ = index.search(q_emb, len(clips))
        sims = sims[0]

        max_views, max_likes = max([c["views"] for c in clips] + [1]), max([c["likes"] for c in clips] + [1])
        scored = []

        for i, c in enumerate(clips):
            sim = max(0.0, float(sims[i]))
            if sim < 0.15: continue
            c["vector"] = clip_embs[i]

            h = c["height"]
            res_score = 1.0 if h >= 2160 else (0.8 if h >= 1080 else 0.5)
            eng = min(0.6 + (res_score * 0.3), 1.0) if c['source'] == 'Pexels' else (c["views"] / max_views + c["likes"] / max_likes) / 2
            duration_score = 1.0 if 6 <= c["duration"] <= 18 else 0.7

            final = (sim * 0.50) + (res_score * 0.20) + (eng * 0.20) + (duration_score * 0.10)
            c["score"] = min(round(final * 100), 100)
            c['quality_label'] = "4K" if h >= 2160 else ("1080p" if h >= 1080 else "720p")
            c['aspect_ratio'] = f"{c['width']}x{c['height']}"
            scored.append(c)

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def _detect_scenes(self, clips):
        for c in clips:
            best_scene, highest_sim = "General", 0.0
            clip_vec = c["vector"].reshape(1, -1)
            for scene_name, anchor_vec in self.scene_anchors.items():
                anchor_vec_norm = anchor_vec.reshape(1, -1).astype('float32')
                faiss.normalize_L2(anchor_vec_norm)
                sim = float(np.dot(clip_vec, anchor_vec_norm.T)[0][0])
                if sim > highest_sim and sim > 0.25:
                    highest_sim, best_scene = sim, scene_name
            c["scene_type"] = best_scene
        return clips

    def _kmeans_diversity(self, clips):
        if len(clips) <= self.max_results: return clips
        X = np.array([c["vector"] for c in clips])
        n_clusters = min(self.max_results, len(clips))
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        cluster_labels = kmeans.fit_predict(X)

        clusters_dict = {i: [] for i in range(n_clusters)}
        for idx, label in enumerate(cluster_labels): clusters_dict[label].append(clips[idx])

        final_selection = []
        for label, cluster_clips in clusters_dict.items():
            if cluster_clips:
                cluster_clips.sort(key=lambda x: x["score"], reverse=True)
                final_selection.append(cluster_clips[0])
                
        final_selection.sort(key=lambda x: x["score"], reverse=True)
        return final_selection
