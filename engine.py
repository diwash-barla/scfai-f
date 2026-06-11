import json
import urllib.request
import urllib.parse
import concurrent.futures
import random
import hashlib
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer, util


class StockEngineV2:
    """
    🚀 StockClip Finder AI - Engine v2 (Industry Optimized)

    Upgrades:
    - Embedding cache (performance boost)
    - Better semantic fusion
    - Cluster-based diversity selection
    - Faster scoring pipeline
    - Cleaner modular architecture
    """

    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key

        self.max_results = 12
        self.embedding_cache = {}   # ⚡ query embedding cache

        self.headers = {
            "User-Agent": "Mozilla/5.0"
        }

        print("🚀 Loading AI Model (v2 optimized)...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✅ Model ready!")

    # =====================================================
    # PUBLIC API
    # =====================================================
    def execute_search(self, query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:

        expanded = self._expand_query(query)
        raw = self._fetch_all(expanded, orientation)

        filtered = self._filter(raw, orientation, quality)
        deduped = self._deduplicate(deduped := filtered)

        scored = self._score(deduped, query)
        clustered = self._cluster_diversity(scored)

        return clustered[:self.max_results]

    # =====================================================
    # QUERY EXPANSION
    # =====================================================
    def _expand_query(self, q: str) -> Dict[str, List[str]]:
        q = q.lower().strip()

        base_sets = [
            q,
            f"{q} cinematic",
            f"{q} documentary",
            f"{q} aerial",
            f"{q} wide shot",
            f"{q} dramatic"
        ]

        alt_sets = [
            f"{q} ruins",
            f"{q} nature",
            f"{q} landscape",
            f"{q} exploration",
            f"{q} mystery",
            f"{q} background"
        ]

        return {
            "pexels": base_sets[:6],
            "pixabay": alt_sets[:6]
        }

    # =====================================================
    # FETCH LAYER (parallel)
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

    # =====================================================
    # PEXELS
    # =====================================================
    def _fetch_pexels(self, query: str, orientation: str):

        url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=10&orientation={orientation}"

        req = urllib.request.Request(
            url,
            headers={**self.headers, "Authorization": self.pexels_key}
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())

            return [self._norm_pexels(v, query) for v in data.get("videos", [])]

        except:
            return []

    def _norm_pexels(self, v: dict, q: str):

        files = v.get("video_files", [])
        files = sorted(files, key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)

        best = files[0] if files else {}

        return {
            "id": str(v.get("id")),
            "source": "Pexels",
            "url": v.get("url"),
            "download": best.get("link"),
            "thumb": v.get("image"),
            "width": best.get("width", 0),
            "height": best.get("height", 0),
            "duration": v.get("duration", 0),
            "views": 0,
            "likes": 0,
            "tags": f"{q} pexels cinematic"
        }

    # =====================================================
    # PIXABAY
    # =====================================================
    def _fetch_pixabay(self, query: str, orientation: str):

        url = f"https://pixabay.com/api/videos/?key={self.pixabay_key}&q={urllib.parse.quote(query)}"

        req = urllib.request.Request(url, headers=self.headers)

        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())

            return [self._norm_pixabay(v, query) for v in data.get("hits", [])]

        except:
            return []

    def _norm_pixabay(self, v: dict, q: str):

        vids = v.get("videos", {})
        best = vids.get("large") or vids.get("medium") or vids.get("small") or {}

        return {
            "id": str(v.get("id")),
            "source": "Pixabay",
            "url": v.get("pageURL"),
            "download": best.get("url"),
            "thumb": v.get("picture"),
            "width": best.get("width", 0),
            "height": best.get("height", 0),
            "duration": v.get("duration", 0),
            "views": v.get("views", 0),
            "likes": v.get("likes", 0),
            "tags": f"{q} pixabay stock"
        }

    # =====================================================
    # FILTERING
    # =====================================================
    def _filter(self, clips, orientation, quality):

        out = []

        for c in clips:
            w, h = c["width"], c["height"]
            if not w or not h:
                continue

            ratio = w / h

            if orientation == "landscape" and not (1.70 <= ratio <= 1.85):
                continue
            if orientation == "portrait" and not (0.50 <= ratio <= 0.60):
                continue

            if quality == "720" and h < 720:
                continue
            if quality == "1080" and h < 1080:
                continue
            if quality == "4k" and h < 2160:
                continue

            out.append(c)

        return out

    # =====================================================
    # DEDUPLICATION (SMART)
    # =====================================================
    def _deduplicate(self, clips):

        seen = set()
        out = []

        for c in clips:
            fp = hashlib.md5(
                f"{c['width']}x{c['height']}_{c['duration']}_{c['source']}".encode()
            ).hexdigest()

            if fp in seen:
                continue

            seen.add(fp)
            out.append(c)

        return out

    # =====================================================
    # EMBEDDING CACHE
    # =====================================================
    def _get_embedding(self, text: str):

        if text in self.embedding_cache:
            return self.embedding_cache[text]

        emb = self.model.encode(text, convert_to_tensor=True)
        self.embedding_cache[text] = emb
        return emb

    # =====================================================
    # SCORING ENGINE
    # =====================================================
    def _score(self, clips, query):

        if not clips:
            return []

        q_emb = self._get_embedding(query)

        texts = [c["tags"] for c in clips]
        clip_embs = self.model.encode(texts, convert_to_tensor=True)

        sims = util.cos_sim(q_emb, clip_embs)[0].cpu().tolist()

        max_views = max([c["views"] for c in clips] + [1])
        max_likes = max([c["likes"] for c in clips] + [1])

        scored = []

        for i, c in enumerate(clips):

            sim = max(0.0, sims[i])

            if sim < 0.12:
                continue

            h = c["height"]

            res_score = 1.0 if h >= 2160 else (0.8 if h >= 1080 else 0.5)

            eng = (c["views"] / max_views + c["likes"] / max_likes) / 2

            duration_score = 1.0 if 6 <= c["duration"] <= 18 else 0.7

            final = (
                sim * 0.45 +
                res_score * 0.20 +
                eng * 0.15 +
                duration_score * 0.10 +
                random.uniform(0.01, 0.05)
            )

            c["score"] = round(final * 100, 2)
            c["sim"] = round(sim * 100, 2)

            scored.append(c)

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    # =====================================================
    # CLUSTER-BASED DIVERSITY (LIGHTWEIGHT)
    # =====================================================
    def _cluster_diversity(self, clips):

        if len(clips) <= self.max_results:
            return clips

        clusters = {"pexels": [], "pixabay": []}

        for c in clips:
            clusters[c["source"].lower()].append(c)

        final = []

        # alternate selection for diversity
        while len(final) < self.max_results:
            for src in ["pexels", "pixabay"]:
                if clusters[src]:
                    final.append(clusters[src].pop(0))
                if len(final) >= self.max_results:
                    break

        return final