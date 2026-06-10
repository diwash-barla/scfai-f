import json
import urllib.request
import urllib.parse
import concurrent.futures
import time
import random
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

    def has_keys(self) -> bool:
        """Validates if required API keys are provided."""
        return bool(self.pexels_key and self.pixabay_key)

    def execute_search(self, query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        """Orchestrates the entire search, rank, and diversity pipeline."""
        
        # 1. AI Query Expansion
        expanded_queries = self._expand_query(query)
        
        # 2. Parallel API Execution
        candidates = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            future_to_req = {}
            
            # Submit Pexels tasks
            for q in expanded_queries['pexels']:
                future = executor.submit(self._fetch_pexels, q, orientation)
                future_to_req[future] = ('pexels', q)
                
            # Submit Pixabay tasks
            for q in expanded_queries['pixabay']:
                future = executor.submit(self._fetch_pixabay, q, orientation)
                future_to_req[future] = ('pixabay', q)
                
            # Gather results
            for future in concurrent.futures.as_completed(future_to_req):
                source, ai_query = future_to_req[future]
                try:
                    data = future.result()
                    for clip in data:
                        clip['query_used'] = ai_query
                    candidates.extend(data)
                except Exception as e:
                    print(f"Error fetching from {source} for query '{ai_query}': {e}")

        # 3. Aspect Ratio & Quality Filtering
        filtered_clips = self._strict_filter(candidates, orientation, quality)
        
        # 4. Deduplication
        unique_clips = self._deduplicate(filtered_clips)
        
        # 5. Intelligent Scoring
        scored_clips = self._score_clips(unique_clips, query)
        
        # 6. Diversity Selection (Max 12 clips)
        final_selection = self._enforce_diversity(scored_clips)
        
        return final_selection

    def _expand_query(self, base_query: str) -> Dict[str, List[str]]:
        """
        Simulates AI-powered query expansion.
        Generates 6 distinct visual angles for each platform to maximize diversity.
        """
        base = base_query.lower().strip()
        
        # Pexels leans heavily on cinematic & mood keywords
        pexels_variations = [
            base,
            f"{base} cinematic",
            f"{base} wide angle",
            f"{base} beautiful",
            f"{base} nature",
            f"{base} aesthetic"
        ]
        
        # Pixabay leans heavily on straightforward subjects & quality tags
        pixabay_variations = [
            f"{base} 4k",
            f"{base} landscape",
            f"{base} scenery",
            f"{base} pro",
            f"{base} environment",
            f"{base} stunning"
        ]
        
        return {
            "pexels": list(set(pexels_variations))[:6],
            "pixabay": list(set(pixabay_variations))[:6]
        }

    def _fetch_pexels(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        """Fetches and normalizes data from Pexels Video API."""
        encoded_query = urllib.parse.quote(query)
        # Using a slight orientation hint for the API, but we will strictly filter later
        api_orient = "landscape" if orientation == "landscape" else "portrait"
        url = f"https://api.pexels.com/videos/search?query={encoded_query}&per_page=10&orientation={api_orient}"
        
        req = urllib.request.Request(url, headers={"Authorization": self.pexels_key})
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pexels(v) for v in data.get('videos', [])]
        except Exception:
            return []

    def _normalize_pexels(self, video_data: dict) -> Dict[str, Any]:
        """Converts Pexels format into our universal clip format."""
        # Find best video file (highest resolution)
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
            "views": 0, # Pexels doesn't provide this via API
            "likes": 0
        }

    def _fetch_pixabay(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        """Fetches and normalizes data from Pixabay Video API."""
        encoded_query = urllib.parse.quote(query)
        url = f"https://pixabay.com/api/videos/?key={self.pixabay_key}&q={encoded_query}&per_page=10"
        
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pixabay(v) for v in data.get('hits', [])]
        except Exception:
            return []

    def _normalize_pixabay(self, video_data: dict) -> Dict[str, Any]:
        """Converts Pixabay format into our universal clip format."""
        videos = video_data.get('videos', {})
        # Pick the largest available resolution
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
        """Filters clips strictly based on mathematical aspect ratio and actual pixel height."""
        filtered = []
        for clip in clips:
            w, h = clip.get('width', 0), clip.get('height', 0)
            if w == 0 or h == 0:
                continue
                
            # Aspect Ratio Calculation
            ratio = w / h
            valid_ratio = False
            
            if orientation == 'landscape':
                valid_ratio = 1.70 <= ratio <= 1.85
            elif orientation == 'portrait':
                valid_ratio = 0.50 <= ratio <= 0.60
                
            if not valid_ratio:
                continue
                
            # Quality Verification
            valid_quality = False
            if quality == 'any':
                valid_quality = True
            elif quality == '720' and h >= 720:
                valid_quality = True
            elif quality == '1080' and h >= 1080:
                valid_quality = True
            elif quality == '4k' and h >= 2160:
                valid_quality = True
                
            if valid_quality and clip.get('download_url'):
                filtered.append(clip)
                
        return filtered

    def _deduplicate(self, clips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Removes duplicate clips based on unique download URLs and identical dimensions/duration."""
        seen_urls = set()
        seen_fingerprints = set()
        unique = []
        
        for clip in clips:
            url = clip.get('download_url')
            # Create a heuristic fingerprint for cross-platform duplicates
            fingerprint = f"{clip.get('width')}x{clip.get('height')}_{clip.get('duration')}"
            
            if url not in seen_urls and fingerprint not in seen_fingerprints:
                seen_urls.add(url)
                seen_fingerprints.add(fingerprint)
                unique.append(clip)
                
        return unique

    def _score_clips(self, clips: List[Dict[str, Any]], base_query: str) -> List[Dict[str, Any]]:
        """
        Applies weighted intelligent scoring to every clip.
        Weights: Relevance (0.40), Quality/Resolution (0.30), Engagement (0.15), Freshness (0.15)
        """
        max_views = max([c.get('views', 1) for c in clips]) if clips else 1
        
        for clip in clips:
            score = 0.0
            
            # 1. Quality / Resolution (0.30 weight) - Normalize against 4K
            res_score = min(clip.get('height', 0) / 2160.0, 1.0)
            score += res_score * 0.30
            
            # 2. Relevance (0.40 weight) - Simulated via duration & aspect correctness
            # Ideal stock footage duration is 5-20 seconds.
            duration = clip.get('duration', 0)
            if 5 <= duration <= 20:
                score += 0.40
            elif 2 < duration < 5 or 20 < duration < 40:
                score += 0.20
                
            # 3. Engagement (0.15 weight) - Normalized views
            eng_score = min(clip.get('views', 0) / max_views, 1.0)
            if clip['source'] == 'Pexels':
                eng_score = 0.5 # Default average since Pexels doesn't expose views easily
            score += eng_score * 0.15
            
            # 4. Freshness/Random jitter (0.15 weight) - Adds organic variety
            score += random.uniform(0.05, 0.15)
            
            # Format and attach properties
            clip['score'] = round(score * 100) # Convert to 0-100 scale
            clip['quality_label'] = "4K" if clip['height'] >= 2160 else ("1080p" if clip['height'] >= 1080 else "720p")
            clip['aspect_ratio'] = f"{clip['width']}x{clip['height']}"
            
        # Sort highest score first
        return sorted(clips, key=lambda x: x['score'], reverse=True)

    def _enforce_diversity(self, sorted_clips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensures the final selection is highly diverse.
        Avoids showing 12 identical clips from the same query or source.
        """
        final_selection = []
        source_count = {'Pexels': 0, 'Pixabay': 0}
        query_count = {}
        
        for clip in sorted_clips:
            if len(final_selection) >= self.max_results:
                break
                
            src = clip['source']
            q_used = clip['query_used']
            
            # Diversity Rules:
            # 1. Try not to exceed 8 from a single source if possible
            if source_count[src] >= 8 and len(sorted_clips) > self.max_results:
                continue
                
            # 2. Max 3 clips from the exact same AI expanded query
            if query_count.get(q_used, 0) >= 3:
                continue
                
            # Passed diversity checks
            final_selection.append(clip)
            source_count[src] += 1
            query_count[q_used] = query_count.get(q_used, 0) + 1
            
        # If we couldn't fill the quota due to strict diversity, backfill with remaining best clips
        if len(final_selection) < self.max_results:
            for clip in sorted_clips:
                if len(final_selection) >= self.max_results: break
                if clip not in final_selection:
                    final_selection.append(clip)
                    
        # Sort final selection again by score just to ensure best ones are on top
        return sorted(final_selection, key=lambda x: x['score'], reverse=True)