import json
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import time
import random
from typing import List, Dict, Any

class StockEngine:
    """
    स्टॉकक्लिप फाइंडर एआई का मुख्य बिजनेस लॉजिक इंजन।
    यह एआई क्वेरी एक्सपेंशन, एपीआई इंटीग्रेशन, सख्त प्रासंगिकता फ़िल्टरिंग,
    इंटेलिजेंट स्कोरिंग, डुप्लीकेट हटाना और विविधता चयन को संभालता है।
    """

    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.max_results = 12
        # बॉट ब्लॉकिंग से बचने के लिए ब्राउज़र जैसा User-Agent उपयोग करें
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def has_keys(self) -> bool:
        """जांचता है कि क्या दोनों एपीआई कीज़ उपलब्ध हैं।"""
        return bool(self.pexels_key and self.pixabay_key)

    def execute_search(self, query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        """सर्च, फ़िल्टर, स्कोरिंग और विविधता की पूरी प्रक्रिया को संचालित करता है।"""
        
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
                    print(f"[इंजन त्रुटि] {source} थ्रेड क्रैश हुआ: {e}")

        filtered_clips = self._strict_filter(candidates, query, orientation, quality)
        unique_clips = self._deduplicate(filtered_clips)
        scored_clips = self._score_clips(unique_clips, query)
        final_selection = self._enforce_diversity(scored_clips)
        
        return final_selection

    def _expand_query(self, base_query: str) -> Dict[str, List[str]]:
        base = base_query.lower().strip()
        pexels_variations = [base, f"{base} cinematic", f"{base} space motion", f"{base} background", f"{base} scientific visualization", f"{base} abstract look"]
        pixabay_variations = [f"{base} space", f"{base} universe", f"{base} cosmos", f"{base} deep space", f"{base} animation", f"{base} stars"]
        return {
            "pexels": list(set(pexels_variations))[:6],
            "pixabay": list(set(pixabay_variations))[:6]
        }

    def _fetch_pexels(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        encoded_query = urllib.parse.quote(query)
        api_orient = "landscape" if orientation == "landscape" else "portrait"
        url = f"https://api.pexels.com/videos/search?query={encoded_query}&per_page=10&orientation={api_orient}"
        
        request_headers = self.headers.copy()
        request_headers["Authorization"] = self.pexels_key
        
        req = urllib.request.Request(url, headers=request_headers)
        
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pexels(v) for v in data.get('videos', [])]
        except Exception as e:
            print(f"❌ [पेक्सेल्स त्रुटि] सर्च फेल: '{query}' - {e}")
            return []

    def _normalize_pexels(self, video_data: dict) -> Dict[str, Any]:
        files = sorted(video_data.get('video_files', []), key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
        best_file = files[0] if files else {}
        
        url_path = urllib.parse.urlparse(video_data.get('url', '')).path
        parts = [p for p in url_path.split('/') if p]
        slug = parts[-1] if len(parts) >= 2 else ""
        slug_words = slug.split('-')
        if slug_words and slug_words[-1].isdigit():
            slug_words = slug_words[:-1]
        tags = " ".join(slug_words)

        return {
            "id": str(video_data.get('id')),
            "source": "Pexels",
            "url": video_data.get('url'),
            "download_url": best_file.get('link'),
            "thumbnail": video_data.get('image'),
            "width": best_file.get('width', 0),
            "height": best_file.get('height', 0),
            "duration": video_data.get('duration', 0),
            "views": 0,    # Pexels API doesn't provide this easily
            "likes": 0,    # Pexels API doesn't provide this easily
            "tags": tags 
        }

    def _fetch_pixabay(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        encoded_query = urllib.parse.quote(query)
        url = f"https://pixabay.com/api/videos/?key={self.pixabay_key}&q={encoded_query}&per_page=10"
        
        req = urllib.request.Request(url, headers=self.headers)
        
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pixabay(v) for v in data.get('hits', [])]
        except Exception as e:
            print(f"❌ [पिक्सबे त्रुटि] सर्च फेल: '{query}' - {e}")
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
            "views": video_data.get('views', 0), # Pixabay gives views
            "likes": video_data.get('likes', 0), # Pixabay gives likes
            "tags": video_data.get('tags', '') 
        }

    def _strict_filter(self, clips: List[Dict[str, Any]], base_query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
        filtered = []
        stop_words = {"in", "of", "the", "a", "an", "with", "and", "on", "for", "at", "by", "from"}
        query_words = [w.lower().strip() for w in base_query.split() if w.lower().strip() not in stop_words and len(w.strip()) > 2]

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
                
            if not valid_quality: continue

            clip_tags = clip.get('tags', '').lower()
            clip_url = clip.get('url', '').lower()
            text_pool = f"{clip_tags} {clip_url}"
            
            if query_words:
                match_found = any(word in text_pool for word in query_words)
                if not match_found:
                    continue

            if clip.get('download_url'):
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
        """
        नया बैलेंस्ड स्कोरिंग सिस्टम:
        35% प्रासंगिकता (Relevance) + 20% पॉपुलैरिटी (Views+Likes) + 20% रिज़ॉल्यूशन (Quality) + 15% विज़ुअल (Duration) + 10% रैंडम
        """
        # पॉपुलैरिटी कैलकुलेशन के लिए अधिकतम व्यूज और लाइक्स निकालें
        max_views = max([c.get('views', 1) for c in clips]) if clips else 1
        max_likes = max([c.get('likes', 1) for c in clips]) if clips else 1
        
        stop_words = {"in", "of", "the", "a", "an", "with", "and", "on", "for", "at", "by", "from"}
        query_words = [w.lower().strip() for w in base_query.split() if w.lower().strip() not in stop_words and len(w.strip()) > 2]

        for clip in clips:
            score = 0.0
            
            # A. RELEVANCE SCORE (0.35 भार)
            relevance = 0.0
            if query_words:
                clip_text = f"{clip.get('tags', '')} {clip.get('url', '')}".lower()
                matches = sum(1 for word in query_words if word in clip_text)
                relevance = matches / len(query_words)
            else:
                relevance = 1.0
            score += relevance * 0.35

            # B. RESOLUTION SCORE (0.20 भार) 
            h = clip.get('height', 0)
            res_score = 0.0
            if h >= 2160: res_score = 1.0     # 4K
            elif h >= 1080: res_score = 0.8   # 1080p
            elif h >= 720: res_score = 0.5    # 720p
            score += res_score * 0.20
            
            # C. ENGAGEMENT SCORE - VIEWS & LIKES (0.20 भार - बढ़ा हुआ)
            views_score = min(clip.get('views', 0) / max_views, 1.0) if max_views > 1 else 0.5
            likes_score = min(clip.get('likes', 0) / max_likes, 1.0) if max_likes > 1 else 0.5
            
            if clip['source'] == 'Pexels': 
                # Pexels व्यूज/लाइक्स नहीं देता, इसलिए इसे इसकी क्वालिटी (res_score) के आधार पर एक औसत अच्छा स्कोर देंगे
                # ताकि यह Pixabay के साथ प्रतियोगिता में बना रहे।
                eng_score = 0.6 + (res_score * 0.3)
                eng_score = min(eng_score, 1.0)
            else:
                # Pixabay के लिए व्यूज (50%) और लाइक्स (50%) का संयोजन
                eng_score = (views_score * 0.5) + (likes_score * 0.5)
                
            score += eng_score * 0.20

            # D. VISUAL & DURATION QUALITY (0.15 भार)
            quality_factor = 0.5
            duration = clip.get('duration', 0)
            if 8 <= duration <= 18: quality_factor = 1.0
            elif 5 <= duration <= 25: quality_factor = 0.8
            score += quality_factor * 0.15

            # E. FRESHNESS (0.10 भार)
            score += random.uniform(0.05, 0.10)

            clip['score'] = min(round(score * 100), 100)
            clip['quality_label'] = "4K" if h >= 2160 else ("1080p" if h >= 1080 else "720p")
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
