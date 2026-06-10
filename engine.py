import json
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import time
import random
import logging
from typing import List, Dict, Any

class StockEngine:
    """
    Core business logic engine for StockClip Finder AI.
    Handles AI query expansion, API integrations, strict filtering, 
    intelligent scoring, deduplication, and diversity selection.
    """

    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.max_results = 12
        # Adding a User-Agent is crucial because Pexels often blocks default Python requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def has_keys(self) -> bool:
        """Validates if required API keys are provided."""
        return bool(self.pexels_key and self.pixabay_key)

    def execute_search(self, query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        """Orchestrates the entire search, rank, and diversity pipeline."""
        
        expanded_queries = self._expand_query(query)
        candidates = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            future_to_req = {}
            
            for q in expanded_queries['pexels']:
                future = executor.submit(self._fetch_pexels, q, orientation)
                future_to_req[future] = ('pexels', q)
                
            for q in expanded_queries['pixabay']:
                future = executor.submit(self._fetch_pixabay, q, orientation)
                future_to_req[future] = ('pixabay', q)
                
            for future in concurrent.futures.as_completed(future_to_req):
                source, ai_query = future_to_req[future]
                try:
                    data = future.result()
                    for clip in data:
                        clip['query_used'] = ai_query
                    candidates.extend(data)
                except Exception as e:
                    print(f"[Engine Error] Thread crashed for {source} with query '{ai_query}': {e}")

        filtered_clips = self._strict_filter(candidates, orientation, quality)
        unique_clips = self._deduplicate(filtered_clips)
        scored_clips = self._score_clips(unique_clips, query)
        final_selection = self._enforce_diversity(scored_clips)
        
        return final_selection

    def _expand_query(self, base_query: str) -> Dict[str, List[str]]:
        base = base_query.lower().strip()
        pexels_variations = [base, f"{base} cinematic", f"{base} wide angle", f"{base} beautiful", f"{base} nature", f"{base} aesthetic"]
        pixabay_variations = [f"{base} 4k", f"{base} landscape", f"{base} scenery", f"{base} pro", f"{base} environment", f"{base} stunning"]
        return {
            "pexels": list(set(pexels_variations))[:6],
            "pixabay": list(set(pixabay_variations))[:6]
        }

    def _fetch_pexels(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        encoded_query = urllib.parse.quote(query)
        api_orient = "landscape" if orientation == "landscape" else "portrait"
        url = f"https://api.pexels.com/videos/search?query={encoded_query}&per_page=10&orientation={api_orient}"
        
        # Pexels requires Authorization header
        request_headers = self.headers.copy()
        request_headers["Authorization"] = self.pexels_key
        
        req = urllib.request.Request(url, headers=request_headers)
        
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pexels(v) for v in data.get('videos', [])]
        except urllib.error.HTTPError as e:
            # THIS WILL PRINT EXACTLY WHY PEXELS IS FAILING
            try:
                error_body = e.read().decode()
            except:
                error_body = "Could not read error body"
            print(f"❌ [Pexels API Error] HTTP {e.code} for query '{query}'. Details: {error_body}")
            return []
        except Exception as e:
            print(f"❌ [Pexels Network Error] Failed for query '{query}'. Reason: {e}")
            return []

    def _normalize_pexels(self, video_data: dict) -> Dict[str, Any]:
        files = sorted(video_data.get('video_files', []), key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
        best_file = files[0] if files else {}
        return {
            "id": str(video_data.get('id')),
            "source": "Pexels",
            "url": video_data.get('url'),
            "download_url": best_file.get('link'),
            "thumbnail": video_data.get('image'),
            "width": best_file.get('width', 0),
            "height": best_file.get('height', 0),
            "duration": video_data.get('duration', 0),
            "views": 0,
            "likes": 0
        }

    def _fetch_pixabay(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        encoded_query = urllib.parse.quote(query)
        url = f"https://pixabay.com/api/videos/?key={self.pixabay_key}&q={encoded_query}&per_page=10"
        
        req = urllib.request.Request(url, headers=self.headers)
        
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pixabay(v) for v in data.get('hits', [])]
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode()
            except:
                error_body = "Could not read error body"
            print(f"❌ [Pixabay API Error] HTTP {e.code} for query '{query}'. Details: {error_body}")
            return []
        except Exception as e:
            print(f"❌ [Pixabay Network Error] Failed for query '{query}'. Reason: {e}")
            return []

    def _normalize_pixabay(self, video_data: dict) -> Dict[str, Any]:
        videos = video_data.get('videos', {})
        best_file = videos.get('large') or videos.get('medium') or videos.get('small') or videos.get('tiny', {})
        thumbnail_id = video_data.get('picture_id')
        thumbnail = f"https://i.vimeocdn.com/video/{thumbnail_id}_640x360.jpg" if thumbnail_id else ""
        return {
            "id": str(video_data.get('id')),
            "source": "Pixabay",
            "url": video_data.get('pageURL'),
            "download_url": best_file.get('url'),
            "thumbnail": thumbnail,
            "width": best_file.get('width', 0),
            "height": best_file.get('height', 0),
            "duration": video_data.get('duration', 0),
            "views": video_data.get('views', 0),
            "likes": video_data.get('likes', 0)
        }

    def _strict_filter(self, clips: List[Dict[str, Any]], orientation: str, quality: str) -> List[Dict[str, Any]]:
        filtered = []
        for clip in clips:
            w, h = clip.get('width', 0), clip.get('height', 0)
            if w == 0 or h == 0: continue
            
            ratio = w / h
            valid_ratio = False
            if orientation == 'landscape': valid_ratio = 1.70 <= ratio <= 1.85
            elif orientation == 'portrait': valid_ratio = 0.50 <= ratio <= 0.60
            if not valid_ratio: continue
            
            valid_quality = False
            if quality == 'any': valid_quality = True
            elif quality == '720' and h >= 720: valid_quality = True
            elif quality == '1080' and h >= 1080: valid_quality = True
            elif quality == '4k' and h >= 2160: valid_quality = True
                
            if valid_quality and clip.get('download_url'):
                filtered.append(clip)
        return filtered

    def _deduplicate(self, clips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_urls, seen_fingerprints, unique = set(), set(), []
        for clip in clips:
            url = clip.get('download_url')
            fingerprint = f"{clip.get('width')}x{clip.get('height')}_{clip.get('duration')}"
            if url not in seen_urls and fingerprint not in seen_fingerprints:
                seen_urls.add(url)
                seen_fingerprints.add(fingerprint)
                unique.append(clip)
        return unique

    def _score_clips(self, clips: List[Dict[str, Any]], base_query: str) -> List[Dict[str, Any]]:
        max_views = max([c.get('views', 1) for c in clips]) if clips else 1
        for clip in clips:
            score = 0.0
            res_score = min(clip.get('height', 0) / 2160.0, 1.0)
            score += res_score * 0.30
            
            duration = clip.get('duration', 0)
            if 5 <= duration <= 20: score += 0.40
            elif 2 < duration < 5 or 20 < duration < 40: score += 0.20
                
            eng_score = min(clip.get('views', 0) / max_views, 1.0)
            if clip['source'] == 'Pexels': eng_score = 0.5
            score += eng_score * 0.15
            
            score += random.uniform(0.05, 0.15)
            clip['score'] = round(score * 100)
            clip['quality_label'] = "4K" if clip['height'] >= 2160 else ("1080p" if clip['height'] >= 1080 else "720p")
            clip['aspect_ratio'] = f"{clip['width']}x{clip['height']}"
            
        return sorted(clips, key=lambda x: x['score'], reverse=True)

    def _enforce_diversity(self, sorted_clips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        final_selection = []
        source_count = {'Pexels': 0, 'Pixabay': 0}
        query_count = {}
        
        for clip in sorted_clips:
            if len(final_selection) >= self.max_results: break
            src, q_used = clip['source'], clip['query_used']
            
            if source_count[src] >= 8 and len(sorted_clips) > self.max_results: continue
            if query_count.get(q_used, 0) >= 3: continue
                
            final_selection.append(clip)
            source_count[src] += 1
            query_count[q_used] = query_count.get(q_used, 0) + 1
            
        if len(final_selection) < self.max_results:
            for clip in sorted_clips:
                if len(final_selection) >= self.max_results: break
                if clip not in final_selection: final_selection.append(clip)
                    
        return sorted(final_selection, key=lambda x: x['score'], reverse=True)
