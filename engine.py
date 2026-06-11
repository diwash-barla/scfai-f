import json
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import time
import random
import torch
from sentence_transformers import SentenceTransformer, util
from typing import List, Dict, Any

class StockEngine:
    """
    स्टॉकक्लिप फाइंडर एआई का मुख्य बिजनेस लॉजिक इंजन।
    अब इसमें असली 'SentenceTransformer' AI जुड़ा है जो वीडियो के 
    शब्दों का मतलब (Semantic Meaning) समझकर सबसे बेस्ट रिजल्ट चुनता है!
    """

    def __init__(self, pexels_key: str, pixabay_key: str):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.max_results = 12
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 🚀 AI MODEL LOADING: हल्का और बेहद तेज़ मॉडल जो CPU पर भी बढ़िया चलता है
        print("🚀 AI Embedding Model Load हो रहा है... (इसमें कुछ सेकंड लग सकते हैं)")
        self.ai_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ AI Model सफलतापूर्वक लोड हो गया!")

    def has_keys(self) -> bool:
        return bool(self.pexels_key and self.pixabay_key)

    def execute_search(self, query: str, orientation: str, quality: str) -> List[Dict[str, Any]]:
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

        # बेसिक रिज़ॉल्यूशन फ़िल्टर
        filtered_clips = self._basic_filter(candidates, orientation, quality)
        unique_clips = self._deduplicate(filtered_clips)
        
        # 🧠 AI-POWERED SCORING & FILTERING
        scored_clips = self._ai_semantic_scoring(unique_clips, query)
        
        # विविधता चयन
        final_selection = self._enforce_diversity(scored_clips)
        return final_selection

    def _expand_query(self, base_query: str) -> Dict[str, List[str]]:
        base = base_query.lower().strip()
        pexels_variations = [base, f"{base} cinematic", f"{base} space motion", f"{base} background", f"{base} scientific", f"{base} abstract look"]
        pixabay_variations = [f"{base} space", f"{base} universe", f"{base} cosmos", f"{base} deep space", f"{base} animation", f"{base} stars"]
        return {
            "pexels": list(set(pexels_variations))[:6],
            "pixabay": list(set(pixabay_variations))[:6]
        }

    def _fetch_pexels(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        encoded_query = urllib.parse.quote(query)
        api_orient = "landscape" if orientation == "landscape" else "portrait"
        url = f"https://api.pexels.com/videos/search?query={encoded_query}&per_page=10&orientation={api_orient}"
        req = urllib.request.Request(url, headers={**self.headers, "Authorization": self.pexels_key})
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pexels(v) for v in data.get('videos', [])]
        except:
            return []

    def _normalize_pexels(self, video_data: dict) -> Dict[str, Any]:
        files = sorted(video_data.get('video_files', []), key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
        best_file = files[0] if files else {}
        url_path = urllib.parse.urlparse(video_data.get('url', '')).path
        slug_words = [p for p in url_path.split('/') if p][-1].split('-') if len(url_path.split('/')) >= 2 else []
        tags = " ".join(slug_words[:-1] if slug_words and slug_words[-1].isdigit() else slug_words)

        return {
            "id": str(video_data.get('id')),
            "source": "Pexels",
            "url": video_data.get('url'),
            "download_url": best_file.get('link'),
            "thumbnail": video_data.get('image'),
            "width": best_file.get('width', 0),
            "height": best_file.get('height', 0),
            "duration": video_data.get('duration', 0),
            "views": 0, "likes": 0, "tags": tags 
        }

    def _fetch_pixabay(self, query: str, orientation: str) -> List[Dict[str, Any]]:
        encoded_query = urllib.parse.quote(query)
        url = f"https://pixabay.com/api/videos/?key={self.pixabay_key}&q={encoded_query}&per_page=10"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                return [self._normalize_pixabay(v) for v in data.get('hits', [])]
        except:
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
            "views": video_data.get('views', 0), "likes": video_data.get('likes', 0),
            "tags": video_data.get('tags', '') 
        }

    def _basic_filter(self, clips: List[Dict[str, Any]], orientation: str, quality: str) -> List[Dict[str, Any]]:
        filtered = []
        for clip in clips:
            w, h = clip.get('width', 0), clip.get('height', 0)
            if w == 0 or h == 0: continue
            
            ratio = w / h
            if orientation == 'landscape' and not (1.70 <= ratio <= 1.85): continue
            if orientation == 'portrait' and not (0.50 <= ratio <= 0.60): continue
                
            if quality == '720' and h < 720: continue
            if quality == '1080' and h < 1080: continue
            if quality == '4k' and h < 2160: continue

            if clip.get('download_url'):
                filtered.append(clip)
        return filtered

    def _deduplicate(self, clips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen, unique = set(), []
        for clip in clips:
            fingerprint = f"{clip.get('width')}x{clip.get('height')}_{clip.get('duration')}"
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique.append(clip)
        return unique

    def _ai_semantic_scoring(self, clips: List[Dict[str, Any]], base_query: str) -> List[Dict[str, Any]]:
        """
        🚀 AI SEMANTIC ENGINE 🚀
        यह फ़ंक्शन SentenceTransformer का उपयोग करके आपके सर्च और वीडियो टैग्स के बीच 
        Cosine Similarity निकालता है। (AI द्वारा सबसे अच्छा वीडियो चुनना)
        """
        if not clips: return []

        # 1. यूज़र की सर्च क्वेरी को AI वेक्टर में बदलें
        query_embedding = self.ai_model.encode(base_query, convert_to_tensor=True)

        # 2. सभी वीडियो के टैग्स को इकट्ठा करें
        clip_texts = [f"{c.get('tags', '')} {c.get('source', '')}" for c in clips]
        
        # 3. सभी टैग्स को एक साथ (Batch) AI वेक्टर्स में बदलें (यह बहुत तेज़ होता है)
        clip_embeddings = self.ai_model.encode(clip_texts, convert_to_tensor=True)

        # 4. Cosine Similarity निकालें (0.0 से 1.0 तक का स्कोर, जहाँ 1.0 मतलब बिल्कुल सेम)
        cosine_scores = util.cos_sim(query_embedding, clip_embeddings)[0].cpu().tolist()

        max_views = max([c.get('views', 1) for c in clips]) if clips else 1
        max_likes = max([c.get('likes', 1) for c in clips]) if clips else 1
        
        valid_clips = []

        for i, clip in enumerate(clips):
            # AI द्वारा निकाला गया प्रासंगिकता स्कोर (Semantic Score)
            ai_similarity_score = max(0.0, cosine_scores[i])
            
            # अगर AI कहता है कि वीडियो बिल्कुल भी मेल नहीं खाता (स्कोर 0.15 से कम), तो उसे हटा दें
            if ai_similarity_score < 0.15:
                continue

            score = 0.0
            
            # A. AI SEMANTIC RELEVANCE (40% भार) - सबसे ज़्यादा पावर AI को!
            score += ai_similarity_score * 0.40

            # B. RESOLUTION SCORE (20% भार) 
            h = clip.get('height', 0)
            res_score = 1.0 if h >= 2160 else (0.8 if h >= 1080 else 0.5)
            score += res_score * 0.20
            
            # C. ENGAGEMENT SCORE (20% भार)
            views_score = min(clip.get('views', 0) / max_views, 1.0) if max_views > 1 else 0.5
            likes_score = min(clip.get('likes', 0) / max_likes, 1.0) if max_likes > 1 else 0.5
            if clip['source'] == 'Pexels': 
                eng_score = min(0.6 + (res_score * 0.3), 1.0)
            else:
                eng_score = (views_score * 0.5) + (likes_score * 0.5)
            score += eng_score * 0.20

            # D. VISUAL QUALITY (15% भार)
            duration = clip.get('duration', 0)
            quality_factor = 1.0 if 8 <= duration <= 18 else (0.8 if 5 <= duration <= 25 else 0.5)
            score += quality_factor * 0.15

            # E. FRESHNESS (5% भार)
            score += random.uniform(0.01, 0.05)

            clip['score'] = min(round(score * 100), 100)
            clip['ai_similarity'] = round(ai_similarity_score * 100) # UI में दिखाने के लिए सेव करें
            clip['quality_label'] = "4K" if h >= 2160 else ("1080p" if h >= 1080 else "720p")
            clip['aspect_ratio'] = f"{clip['width']}x{clip['height']}"
            
            valid_clips.append(clip)
            
        return sorted(valid_clips, key=lambda x: x['score'], reverse=True)

    def _enforce_diversity(self, sorted_clips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        final_selection, source_count, query_count = [], {'Pexels': 0, 'Pixabay': 0}, {}
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