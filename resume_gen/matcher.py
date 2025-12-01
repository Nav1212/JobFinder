"""
Hybrid Matcher - TF-IDF + Tag-based sentence matching
Finds the best resume sentences for a given job posting
"""

from typing import List, Dict, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re


class HybridMatcher:
    def __init__(self, sentences: List[Dict] = None):
        """Initialize matcher with optional sentence library
        
        Args:
            sentences: List of dicts with 'text', 'type', 'tags' keys
        """
        self.sentences = sentences or []
        self.vectorizer = None
        self.tfidf_matrix = None
        self._build_index()
    
    def _build_index(self):
        """Build TF-IDF index from sentences"""
        if not self.sentences:
            return
        
        texts = [s["text"] for s in self.sentences]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            ngram_range=(1, 2),  # Unigrams and bigrams
            max_features=5000
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
    
    def update_sentences(self, sentences: List[Dict]):
        """Update sentence library and rebuild index"""
        self.sentences = sentences
        self._build_index()
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract potential skill/requirement keywords from text"""
        # Common tech keywords to look for
        tech_patterns = [
            r'\b(python|java|javascript|typescript|c\+\+|c#|ruby|go|rust|scala|kotlin)\b',
            r'\b(react|angular|vue|node\.?js|django|flask|fastapi|spring|rails)\b',
            r'\b(aws|azure|gcp|docker|kubernetes|terraform|jenkins|ci/cd)\b',
            r'\b(sql|nosql|mongodb|postgresql|mysql|redis|elasticsearch)\b',
            r'\b(machine learning|ml|ai|deep learning|nlp|computer vision)\b',
            r'\b(data science|data engineering|analytics|etl|data pipeline)\b',
            r'\b(agile|scrum|kanban|leadership|management|team lead)\b',
            r'\b(api|rest|graphql|microservices|distributed systems)\b',
        ]
        
        keywords = set()
        text_lower = text.lower()
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            keywords.update(matches)
        
        return list(keywords)
    
    def match_by_tags(self, keywords: List[str], top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Match sentences by tag overlap
        
        Returns list of (sentence, score) tuples
        """
        if not self.sentences or not keywords:
            return []
        
        keywords_lower = [k.lower() for k in keywords]
        results = []
        
        for sentence in self.sentences:
            tags = [t.lower() for t in sentence.get("tags", [])]
            
            # Calculate tag overlap score
            overlap = len(set(tags) & set(keywords_lower))
            if overlap > 0:
                score = overlap / max(len(tags), 1)
                results.append((sentence, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def match_by_tfidf(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """Match sentences by TF-IDF similarity
        
        Returns list of (sentence, score) tuples
        """
        if not self.sentences or self.vectorizer is None:
            return []
        
        # Transform query
        query_vector = self.vectorizer.transform([query])
        
        # Calculate similarity
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.01:  # Minimum threshold
                results.append((self.sentences[idx], float(similarities[idx])))
        
        return results
    
    def hybrid_match(self, job_description: str, top_k: int = 15) -> List[Tuple[Dict, float, str]]:
        """Hybrid matching: tags first, then TF-IDF to fill gaps
        
        Returns list of (sentence, score, match_type) tuples
        """
        # Extract keywords for tag matching
        keywords = self.extract_keywords(job_description)
        
        results = []
        seen_texts = set()
        
        # 1. Tag-based matches (high confidence)
        tag_matches = self.match_by_tags(keywords, top_k=top_k // 2)
        for sentence, score in tag_matches:
            if sentence["text"] not in seen_texts:
                results.append((sentence, score * 1.5, "tag"))  # Boost tag matches
                seen_texts.add(sentence["text"])
        
        # 2. TF-IDF matches (semantic similarity)
        tfidf_matches = self.match_by_tfidf(job_description, top_k=top_k)
        for sentence, score in tfidf_matches:
            if sentence["text"] not in seen_texts:
                results.append((sentence, score, "tfidf"))
                seen_texts.add(sentence["text"])
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def match_by_type(self, job_description: str, sentence_type: str, 
                      top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Match only sentences of a specific type
        
        Args:
            job_description: Job posting text
            sentence_type: 'skill', 'experience', 'achievements', etc.
            top_k: Number of results to return
        """
        # Filter sentences by type
        type_sentences = [s for s in self.sentences if s.get("type") == sentence_type]
        
        if not type_sentences:
            return []
        
        # Create temporary matcher for this type
        temp_matcher = HybridMatcher(type_sentences)
        
        # Get matches
        matches = temp_matcher.hybrid_match(job_description, top_k=top_k)
        
        # Return without match_type for simpler API
        return [(m[0], m[1]) for m in matches]


# Quick test
if __name__ == "__main__":
    # Sample sentences
    sentences = [
        {"text": "Built production APIs with FastAPI serving 10K+ requests/day", "type": "skill", "tags": ["python", "api", "fastapi"]},
        {"text": "Developed ML pipelines using scikit-learn achieving 95% accuracy", "type": "skill", "tags": ["python", "machine_learning", "ml"]},
        {"text": "Led team of 5 engineers in agile development environment", "type": "experience", "tags": ["leadership", "agile", "management"]},
        {"text": "Deployed containerized applications using Docker and Kubernetes", "type": "skill", "tags": ["docker", "kubernetes", "devops"]},
        {"text": "Reduced system latency by 40% through query optimization", "type": "achievements", "tags": ["optimization", "performance"]},
        {"text": "Designed distributed data pipelines processing 1M+ records daily", "type": "experience", "tags": ["data_engineering", "distributed_systems"]},
    ]
    
    matcher = HybridMatcher(sentences)
    
    # Test job description
    job_desc = """
    We're looking for a Senior Python Developer with experience in:
    - Building RESTful APIs
    - Machine learning and data pipelines
    - Docker and Kubernetes
    - Leading small teams
    """
    
    print("Job Description Keywords:", matcher.extract_keywords(job_desc))
    print("\n" + "="*60 + "\n")
    
    matches = matcher.hybrid_match(job_desc, top_k=5)
    print("Top Matches:")
    for sentence, score, match_type in matches:
        print(f"  [{match_type:5}] {score:.3f} - {sentence['text'][:60]}...")
