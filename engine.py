import json
import urllib.request
import urllib.parse
import concurrent.futures
import hashlib
import numpy as np
import re
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import faiss
from sklearn.cluster import KMeans
from deep_translator import GoogleTranslator

class StockEngine:
    """
    🔥 StockClip Finder AI - Engine V3.1 (Autonomous Ready + Keyword Extraction)
    Includes: FAISS, KMeans, Cache, Scene Detection, and True Cross-lingual Script-to-Footage.
    """

    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.max_results = 12
        
        self.embedding_cache = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        print("🚀 Loading AI Model (V3.1 faiss-optimized)...")
        # Multilingual model supports both Hindi and English for semantic mapping
        self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        self.scene_anchors = {
            "Drone/Aerial": self.model.encode("aerial drone bird eye view flying above", convert_to_tensor=False),
            "Macro/Close-up": self.model.encode("macro close up extremely detailed zoom", convert_to_tensor=False),
            "Timelapse": self.model.encode("timelapse fast motion clouds passing time", convert_to_tensor=False),
            "Cinematic": self.model.encode("cinematic depth of field moody dramatic lighting", convert_to_tensor=False)
        }
        print("✅ Engine V3.1 ready!")

    def has_keys(self) -> bool:
        return bool(self.pexels_key and self.pixabay_key)

    # =====================================================
    # NLP KEYWORD EXTRACTOR (THE MAGIC FIX 🔥)
    # =====================================================
    def _extract_visual_keywords(self, scene_text: str) -> str:
        """Translates Hindi/Multilingual text to English and extracts pure visual NOUNS."""
        try:
            # 1. Auto-Translate to English
            en_text = GoogleTranslator(source='auto', target='en').translate(scene_text)
        except Exception as e:
            print(f"Translation error: {e}")
            en_text = scene_text
        
        # 2. Clean punctuation
        clean_text = re.sub(r'[^\w\s]', '', en_text.lower())
        words = clean_text.split()
        
        # 3. Aggressive Stopwords (Grammar + Action Verbs that confuse image APIs)
        stop_words = {
            # Grammar
            "imagine", "that", "you", "are", "in", "the", "middle", "of", "and", "as", "soon",
            "a", "to", "it", "out", "your", "there", "is", "with", "on", "at", "by", "for", 
            "from", "an", "was", "were", "will", "we", "they", "he", "she", "this", "these",
            
            # Action verbs that ruin visual search (The real culprits!)
            "run", "running", "go", "going", "walk", "walking", "stand", "standing", 
            "look", "looking", "see", "seeing", "reach", "reaching", "touch", "touching",
            "start", "starts", "find", "finding", "appear", "appears", "disappear",
            "feel", "feeling", "gather", "gathers", "begin", "begins", "blinds", "blind",
            
            # Adverbs / Prepositions
            "towards", "away", "suddenly", "then", "now", "here", "inside", "outside",
            "up", "down", "left", "right", "front", "back", "can", "could", "would", "about"
        }
        
        # 4. Filter words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # 5. VITAL FIX: English puts the most important nouns at the END of the sentence usually.
        # e.g., "you run towards an old broken building" -> we want "old broken building"
        # Taking the LAST 4 valid words instead of the first 4.
        final_query = " ".join(keywords[-4:])
        
        # Fallback if everything was filtered out
        if not final_query.strip():
            final_query = "mysterious cinematic landscape"
            
        print(f"🧠 [AI Translator] Original EN: '{en_text}'")
        print(f"🧠 [AI Translator] Extracted Target -> '{final_query}'")
        return final_query

    # =====================================================
    # SCRIPT-TO-FOOTAGE PIPELINE
    # =====================================================
    def generate_video_timeline(self, script: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        raw_scenes = re.split(r'[.।|\n]+', script)
        scenes = [s.strip() for s in raw_scenes if len(s.strip()) > 15] 
        
        timeline = []
        
        for scene_text in scenes[:6]:
            # 🔥 Using the new Extractor instead of raw slicing
            search_query = self._extract_visual_keywords(scene_text)
            
            clips = self.execute_search(query=search_query, orientation=orientation, quality=quality)
            
            best_clip = None
            if clips:
                # FAISS and KMeans already sorted the clips. The 0th index is the absolute centroid best.
                best_clip = clips[0] 
                
            timeline.append({
                "scene_text": scene_text,
                "clip": best_clip
            })
            
        return timeline

    # =====================================================
    # SEARCH & FAISS CORE
    # =====================================================
    def execute_search(self, query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        expanded = self._expand_query(query)
        raw = self._fetch_all(expanded, orientation)

        filtered = self._filter(raw, orientation, quality)
        deduped = self._deduplicate(filtered)
        
        if not deduped: return []

        scored = self._faiss_semantic_score(deduped, query)
        processed = self._detect_scenes(scored)
        final_results = self._kmeans_diversity(processed)

        # 🛑 CRITICAL FIX: Ensure no numpy arrays leak into the JSON response!
        for c in final_results:
            c.pop("vector", None)

        return final_results[:self.max_results]

    def _expand_query(self, q: str) -> Dict[str, List[str]]:
        q = q.lower().strip()
        base_sets = [q, f"{q} cinematic", f"{q} documentary", f"{q} aerial", f"{q} wide shot", f"{q} dramatic"]
        alt_sets = [f"{q} ruins", f"{q} nature", f"{q} landscape", f"{q} exploration", f"{q} mystery", f"{q} background"]
        return {"pexels": base_sets[:6], "pixabay": alt_sets[:6]}

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
            c["ai_similarity"] = round(sim * 100, 2)
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
            c["quality_label"] = f"{c['quality_label']} | {best_scene}"
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
