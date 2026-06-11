import json
import urllib.request
import urllib.parse
import concurrent.futures
import hashlib
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import faiss
from sklearn.cluster import KMeans

class StockEngine:
    """
    🔥 StockClip Finder AI - Engine V3 (Research-Grade / Autonomous Ready)
    
    Upgrades Included:
    - FAISS Vector Indexing for instant semantic retrieval.
    - True KMeans Clustering for mathematical visual diversity.
    - Full Embedding Cache (Queries + Video Tags).
    - Scene Type Detection (Drone, Cinematic, Macro, etc.).
    - 100% Deterministic Scoring (No Randomness).
    """

    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.max_results = 12
        
        # ⚡ Full Memory Caching System
        self.embedding_cache = {}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        print("🚀 Loading AI Model (V3 faiss-optimized)...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Anchor vectors for Scene Detection
        self.scene_anchors = {
            "Drone/Aerial": self.model.encode("aerial drone bird eye view flying above", convert_to_tensor=False),
            "Macro/Close-up": self.model.encode("macro close up extremely detailed zoom", convert_to_tensor=False),
            "Timelapse": self.model.encode("timelapse fast motion clouds passing time", convert_to_tensor=False),
            "Cinematic": self.model.encode("cinematic depth of field moody dramatic lighting", convert_to_tensor=False)
        }
        print("✅ Engine V3 ready!")

    def has_keys(self) -> bool:
        return bool(self.pexels_key and self.pixabay_key)

    # =====================================================
    # PUBLIC API
    # =====================================================
    def execute_search(self, query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        expanded = self._expand_query(query)
        raw = self._fetch_all(expanded, orientation)

        filtered = self._filter(raw, orientation, quality)
        deduped = self._deduplicate(filtered)
        
        if not deduped:
            return []

        # 1. FAISS Semantic Search & Scoring
        scored = self._faiss_semantic_score(deduped, query)
        
        # 2. Scene Detection
        processed = self._detect_scenes(scored)
        
        # 3. True KMeans Clustering for Diversity
        final_results = self._kmeans_diversity(processed)

        return final_results[:self.max_results]

    # =====================================================
    # QUERY EXPANSION
    # =====================================================
    def _expand_query(self, q: str) -> Dict[str, List[str]]:
        q = q.lower().strip()
        base_sets = [q, f"{q} cinematic", f"{q} documentary", f"{q} aerial", f"{q} wide shot", f"{q} dramatic"]
        alt_sets = [f"{q} ruins", f"{q} nature", f"{q} landscape", f"{q} exploration", f"{q} mystery", f"{q} background"]
        return {"pexels": base_sets[:6], "pixabay": alt_sets[:6]}

    # =====================================================
    # FETCH LAYER (Parallel)
    # =====================================================
    def _fetch_all(self, expanded: Dict[str, List[str]], orientation: str):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = []
            for q in expanded["pexels"]:
                futures.append(ex.submit(self._fetch_pexels, q, orientation))
            for q in expanded["pixabay"]:
                futures.append(ex.submit(self._fetch_pixabay, q, orientation))
            
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.extend(f.result())
                except:
                    continue
        return results

    def _fetch_pexels(self, query: str, orientation: str):
        api_orient = "landscape" if orientation == "landscape" else "portrait"
        url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=10&orientation={api_orient}"
        req = urllib.request.Request(url, headers={**self.headers, "Authorization": self.pexels_key})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            return [self._norm_pexels(v, query) for v in data.get("videos", [])]
        except:
            return []

    def _norm_pexels(self, v: dict, query_used: str):
        files = sorted(v.get("video_files", []), key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
        best = files[0] if files else {}
        
        url_path = urllib.parse.urlparse(v.get('url', '')).path
        slug_words = [p for p in url_path.split('/') if p][-1].split('-') if len(url_path.split('/')) >= 2 else []
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
                data = json.loads(r.read().decode())
            return [self._norm_pixabay(v, query) for v in data.get("hits", [])]
        except:
            return []

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

    # =====================================================
    # HARD FILTERS & DEDUPLICATION
    # =====================================================
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

    # =====================================================
    # BATCH EMBEDDING CACHE
    # =====================================================
    def _get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Retrieves or computes embeddings efficiently using a cache."""
        embeddings = []
        texts_to_compute = []
        indices_to_compute = []

        for i, text in enumerate(texts):
            if text in self.embedding_cache:
                embeddings.append(self.embedding_cache[text])
            else:
                embeddings.append(None) # Placeholder
                texts_to_compute.append(text)
                indices_to_compute.append(i)

        if texts_to_compute:
            computed_embs = self.model.encode(texts_to_compute, convert_to_tensor=False)
            for i, idx in enumerate(indices_to_compute):
                emb = computed_embs[i]
                self.embedding_cache[texts_to_compute[i]] = emb
                embeddings[idx] = emb

        return np.vstack(embeddings).astype('float32')

    # =====================================================
    # FAISS SCORING ENGINE (DETERMINISTIC)
    # =====================================================
    def _faiss_semantic_score(self, clips, query):
        # 1. Get Query Embedding
        q_emb = self._get_embeddings_batch([query])
        faiss.normalize_L2(q_emb)

        # 2. Get Clip Embeddings
        texts = [f"{c['tags']} {c['source']}" for c in clips]
        clip_embs = self._get_embeddings_batch(texts)
        faiss.normalize_L2(clip_embs)

        # 3. Build FAISS Index for inner product (Cosine Similarity on normalized vectors)
        d = clip_embs.shape[1]
        index = faiss.IndexFlatIP(d)
        index.add(clip_embs)

        # 4. Search
        sims, _ = index.search(q_emb, len(clips))
        sims = sims[0]

        # 5. Deterministic Scoring
        max_views = max([c["views"] for c in clips] + [1])
        max_likes = max([c["likes"] for c in clips] + [1])
        scored = []

        for i, c in enumerate(clips):
            sim = max(0.0, float(sims[i]))
            if sim < 0.15: # Hard limit
                continue

            c["vector"] = clip_embs[i] # Store for KMeans later

            h = c["height"]
            res_score = 1.0 if h >= 2160 else (0.8 if h >= 1080 else 0.5)

            if c['source'] == 'Pexels':
                eng = min(0.6 + (res_score * 0.3), 1.0)
            else:
                eng = (c["views"] / max_views + c["likes"] / max_likes) / 2

            duration_score = 1.0 if 6 <= c["duration"] <= 18 else 0.7

            # No Randomness. Pure deterministic ranking.
            final = (sim * 0.50) + (res_score * 0.20) + (eng * 0.20) + (duration_score * 0.10)

            c["score"] = min(round(final * 100), 100)
            c["ai_similarity"] = round(sim * 100, 2)
            c['quality_label'] = "4K" if h >= 2160 else ("1080p" if h >= 1080 else "720p")
            c['aspect_ratio'] = f"{c['width']}x{c['height']}"
            scored.append(c)

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    # =====================================================
    # SCENE TYPE DETECTION
    # =====================================================
    def _detect_scenes(self, clips):
        for c in clips:
            best_scene = "General"
            highest_sim = 0.0
            
            clip_vec = c["vector"].reshape(1, -1)
            
            for scene_name, anchor_vec in self.scene_anchors.items():
                anchor_vec_norm = anchor_vec.reshape(1, -1).astype('float32')
                faiss.normalize_L2(anchor_vec_norm)
                
                # Manual cosine similarity for scene detection
                sim = float(np.dot(clip_vec, anchor_vec_norm.T)[0][0])
                if sim > highest_sim and sim > 0.25: # Threshold
                    highest_sim = sim
                    best_scene = scene_name
            
            c["scene_type"] = best_scene
            # To show in UI, we can append it to the quality label temporarily or handle in frontend
            c["quality_label"] = f"{c['quality_label']} | {best_scene}"
            
        return clips

    # =====================================================
    # TRUE KMEANS DIVERSITY CLUSTERING
    # =====================================================
    def _kmeans_diversity(self, clips):
        """Uses Machine Learning (KMeans) to cluster visually similar videos and pick the best from each."""
        if len(clips) <= self.max_results:
            return clips

        # Extract vectors for clustering
        X = np.array([c["vector"] for c in clips])
        
        # Determine number of clusters (We want exactly max_results distinct visual angles)
        n_clusters = min(self.max_results, len(clips))
        
        # Run KMeans
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        cluster_labels = kmeans.fit_predict(X)

        # Group clips by cluster
        clusters_dict = {i: [] for i in range(n_clusters)}
        for idx, label in enumerate(cluster_labels):
            clusters_dict[label].append(clips[idx])

        final_selection = []
        
        # Pick the highest-scoring clip from each cluster (Centroid representation)
        for label, cluster_clips in clusters_dict.items():
            if cluster_clips:
                # Sort within cluster by our deterministic score
                cluster_clips.sort(key=lambda x: x["score"], reverse=True)
                final_selection.append(cluster_clips[0])
                
        # Re-sort final output by score
        final_selection.sort(key=lambda x: x["score"], reverse=True)
        
        # Clean up numpy arrays before JSON serialization
        for c in final_selection:
            del c["vector"]

        return final_selection