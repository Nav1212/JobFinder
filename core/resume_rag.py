"""
Resume RAG (Retrieval-Augmented Generation) Index
Per-user FAISS vector index for semantic resume matching
Uses Ollama embeddings with mxbai-embed-large model (1024 dims)
"""

import os
import pickle
import json
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    faiss = None
    FAISS_AVAILABLE = False
    print("Warning: FAISS not installed. Install with: pip install faiss-cpu")

from .llm_client import LocalLLM


def is_faiss_available() -> bool:
    """Check if FAISS is installed and available"""
    return FAISS_AVAILABLE


class UserRAGIndex:
    """
    Per-user RAG index for semantic resume matching.
    
    Stores embeddings of resume sentences (skills, experience, achievements only)
    along with user profile data (name, email, education - NOT indexed).
    Supports multiple resumes per user via filename lookup.
    """
    
    # Sections to index (semantic search)
    INDEXABLE_SECTIONS = {'skills', 'experience', 'achievements'}
    
    # Sections to store in profile (NOT indexed)
    PROFILE_SECTIONS = {'education', 'projects'}
    
    def __init__(self, username: str, indexes_dir: str = "resume_gen/indexes",
                 embedding_model: str = "mxbai-embed-large",
                 similarity_threshold: float = 0.85):
        """
        Initialize RAG index for a user.
        
        Args:
            username: Unique user identifier (derived from resume name)
            indexes_dir: Directory to store pickle files
            embedding_model: Ollama embedding model to use
            similarity_threshold: Threshold for duplicate detection (0.0-1.0)
        """
        if not FAISS_AVAILABLE:
            raise ImportError(
                "FAISS is required for RAG indexing but is not installed.\n"
                "Install with: pip install faiss-cpu\n"
                "Or for GPU support: pip install faiss-gpu"
            )
        
        self.username = username
        self.indexes_dir = Path(indexes_dir)
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        
        # Ensure indexes directory exists
        self.indexes_dir.mkdir(parents=True, exist_ok=True)
        
        # Index file path
        self.index_path = self.indexes_dir / f"{username}_rag.pkl"
        
        # Initialize LLM client for embeddings
        self.llm = LocalLLM()
        
        # FAISS index (inner product for cosine similarity on normalized vectors)
        self.index: Optional[faiss.IndexFlatIP] = None
        self.embedding_dim = 1024  # mxbai-embed-large dimension
        
        # Stored data
        self.sentences: List[str] = []  # Original text for each vector
        self.sentence_metadata: List[Dict] = []  # Category, source, etc.
        self.profile: Dict[str, Any] = {}  # User profile (name, email, education, etc.)
        self.resume_filenames: List[str] = []  # List of resume files for this user
        self.created_at: Optional[str] = None
        self.updated_at: Optional[str] = None
        
        # Load existing index if available
        self._load()
    
    def _load(self) -> bool:
        """Load index from pickle file if exists"""
        if not self.index_path.exists():
            return False
        
        try:
            with open(self.index_path, 'rb') as f:
                data = pickle.load(f)
            
            self.sentences = data.get('sentences', [])
            self.sentence_metadata = data.get('sentence_metadata', [])
            self.profile = data.get('profile', {})
            self.resume_filenames = data.get('resume_filenames', [])
            self.created_at = data.get('created_at')
            self.updated_at = data.get('updated_at')
            
            # Rebuild FAISS index from stored vectors
            vectors = data.get('vectors')
            if vectors is not None and len(vectors) > 0:
                self.index = faiss.IndexFlatIP(self.embedding_dim)
                self.index.add(vectors)
            
            return True
        except Exception as e:
            print(f"Warning: Failed to load RAG index for {self.username}: {e}")
            return False
    
    def _save(self):
        """Save index to pickle file"""
        # Extract vectors from FAISS index
        vectors = None
        if self.index is not None and self.index.ntotal > 0:
            vectors = faiss.rev_swig_ptr(
                self.index.get_xb(), self.index.ntotal * self.embedding_dim
            ).reshape(self.index.ntotal, self.embedding_dim).copy()
        
        data = {
            'sentences': self.sentences,
            'sentence_metadata': self.sentence_metadata,
            'profile': self.profile,
            'resume_filenames': self.resume_filenames,
            'vectors': vectors,
            'created_at': self.created_at or datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        with open(self.index_path, 'wb') as f:
            pickle.dump(data, f)
    
    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """L2 normalize vectors for cosine similarity via inner product"""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
        return vectors / norms
    
    def _embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts using Ollama"""
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, self.embedding_dim)
        
        try:
            embeddings = self.llm.embed(texts, model=self.embedding_model, auto_install=True)
        except Exception as e:
            print(f"Embedding error: {e}")
            # Try installing model if it failed
            try:
                from .model_manager import get_model_manager
                manager = get_model_manager()
                if not manager.is_model_installed(self.embedding_model):
                    print(f"Installing embedding model {self.embedding_model}...")
                    success, msg = manager.install_model_sync(self.embedding_model)
                    if success:
                        embeddings = self.llm.embed(texts, model=self.embedding_model)
                    else:
                        raise RuntimeError(f"Failed to install {self.embedding_model}: {msg}")
                else:
                    raise
            except ImportError:
                raise
        
        # Ensure 2D array
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        
        # Normalize for cosine similarity
        return self._normalize(embeddings)
    
    def exists(self) -> bool:
        """Check if index exists for this user"""
        return self.index_path.exists() and self.index is not None and self.index.ntotal > 0
    
    def create_from_profile(self, profile: Dict[str, Any], 
                           sentences: Dict[str, Any],
                           resume_filename: str) -> int:
        """
        Create new index from user profile and sentences.
        
        Args:
            profile: User profile dict (name, email, education, etc.)
            sentences: Sentence library dict from user_manager
            resume_filename: Source resume filename
            
        Returns:
            Number of sentences indexed
        """
        self.profile = profile
        self.created_at = datetime.now().isoformat()
        
        # Add resume filename if not already tracked
        if resume_filename and resume_filename not in self.resume_filenames:
            self.resume_filenames.append(resume_filename)
        
        # Initialize empty FAISS index
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.sentences = []
        self.sentence_metadata = []
        
        # Collect indexable sentences
        texts_to_index = []
        metadata_list = []
        
        for section, content in sentences.items():
            # Only index specific sections
            if section.lower() not in self.INDEXABLE_SECTIONS:
                continue
            
            if isinstance(content, dict):
                # Nested dict (e.g., skills by category)
                for category, items in content.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                text = item.get('text', item.get('sentence', ''))
                            else:
                                text = str(item)
                            if text.strip():
                                texts_to_index.append(text)
                                metadata_list.append({
                                    'section': section,
                                    'category': category,
                                    'source': resume_filename
                                })
            elif isinstance(content, list):
                # Flat list (e.g., achievements)
                for item in content:
                    if isinstance(item, dict):
                        text = item.get('text', item.get('sentence', ''))
                    else:
                        text = str(item)
                    if text.strip():
                        texts_to_index.append(text)
                        metadata_list.append({
                            'section': section,
                            'category': None,
                            'source': resume_filename
                        })
        
        # Generate embeddings and add to index
        if texts_to_index:
            embeddings = self._embed(texts_to_index)
            self.index.add(embeddings)
            self.sentences = texts_to_index
            self.sentence_metadata = metadata_list
        
        self._save()
        return len(texts_to_index)
    
    def add_sentences(self, sentences: List[Dict[str, Any]], 
                     section: str,
                     category: Optional[str] = None) -> Tuple[int, List[Dict]]:
        """
        Add new sentences to the index.
        
        Args:
            sentences: List of sentence dicts with 'text' key
            section: Section name (skills, experience, achievements)
            category: Optional category within section
            
        Returns:
            Tuple of (num_added, list of duplicate warnings)
        """
        if section.lower() not in self.INDEXABLE_SECTIONS:
            return 0, []
        
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.embedding_dim)
        
        added = 0
        duplicates = []
        
        for item in sentences:
            text = item.get('text', item.get('sentence', '')) if isinstance(item, dict) else str(item)
            if not text.strip():
                continue
            
            # Check for duplicates
            similar = self.find_similar(text)
            if similar:
                duplicates.append({
                    'new_text': text,
                    'similar_to': similar[0]['text'],
                    'similarity': similar[0]['score']
                })
                continue
            
            # Add to index
            embedding = self._embed([text])
            self.index.add(embedding)
            self.sentences.append(text)
            self.sentence_metadata.append({
                'section': section,
                'category': category,
                'source': 'manual'
            })
            added += 1
        
        if added > 0:
            self._save()
        
        return added, duplicates
    
    def find_similar(self, text: str, threshold: Optional[float] = None) -> List[Dict]:
        """
        Find sentences similar to the given text.
        
        Args:
            text: Text to compare
            threshold: Similarity threshold (default: self.similarity_threshold)
            
        Returns:
            List of dicts with 'text', 'score', 'metadata' for matches above threshold
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        
        threshold = threshold or self.similarity_threshold
        
        # Embed query text
        query_embedding = self._embed([text])
        
        # Search all vectors
        k = min(10, self.index.ntotal)
        scores, indices = self.index.search(query_embedding, k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and score >= threshold:
                results.append({
                    'text': self.sentences[idx],
                    'score': float(score),
                    'metadata': self.sentence_metadata[idx]
                })
        
        return results
    
    def retrieve(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Retrieve most relevant sentences for a query (e.g., job description).
        
        Args:
            query: Query text (e.g., job description excerpt)
            top_k: Number of results to return
            
        Returns:
            List of dicts with 'text', 'score', 'metadata' sorted by relevance
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Embed query
        query_embedding = self._embed([query])
        
        # Search
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_embedding, k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                results.append({
                    'text': self.sentences[idx],
                    'score': float(score),
                    'metadata': self.sentence_metadata[idx]
                })
        
        return results

    def judge_relevance(self, query: str, candidates: List[Dict[str, Any]], 
                        model: str = "llama3.1:8b", max_items: int = 10) -> List[Dict[str, Any]]:
        """
        Re-score retrieved sentences with an LLM judge (0-100 relevance).
        
        Args:
            query: The job description/title text to match against.
            candidates: Retrieved sentences with metadata.
            model: LLM model to use for judging.
            max_items: Maximum candidates to include in the prompt.
        
        Returns:
            List of candidates with added 'judge_score' and 'judge_reason', sorted by judge_score.
        """
        if not candidates:
            return []
        
        # Trim to avoid huge prompts
        limited = candidates[:max_items]
        
        # Build prompt with numbered items for easy mapping
        items_block = []
        for idx, item in enumerate(limited, 1):
            section = item.get('metadata', {}).get('section', 'unknown')
            category = item.get('metadata', {}).get('category', 'unknown')
            items_block.append(
                f"{idx}. [{section}/{category}] {item.get('text', '')}"
            )
        items_text = "\n".join(items_block)
        
        prompt = f"""
You are an assistant scoring resume sentences for relevance to a job query.
Give each sentence a relevance score 0-100 (integer). Use stricter grading: 100 means directly proves fit; 0 means unrelated.

Job Query:
{query[:1000]}

Sentences:
{items_text}

Return JSON array only, with objects:
[{{"idx": 1, "score": 0-100, "reason": "short why"}}]
"""
        try:
            judge = LocalLLM(model=model)
            raw = judge.generate(prompt, stream=False, temperature=0.0, timeout=60)
            
            # Extract JSON payload
            start = raw.find('[')
            end = raw.rfind(']') + 1
            payload = raw[start:end] if start != -1 and end > start else raw
            parsed = json.loads(payload)
            
            # Map idx -> scores
            score_map = {}
            if isinstance(parsed, list):
                for entry in parsed:
                    if not isinstance(entry, dict):
                        continue
                    idx = int(entry.get('idx', -1))
                    score = entry.get('score')
                    reason = entry.get('reason', '')
                    if 1 <= idx <= len(limited) and isinstance(score, (int, float)):
                        score_map[idx] = {'judge_score': int(score), 'judge_reason': str(reason)}
        except Exception as e:
            print(f"RAG judge scoring error: {e}")
            score_map = {}
        
        # Attach scores; fallback to 0 if missing
        for pos, item in enumerate(limited, 1):
            meta = score_map.get(pos, {'judge_score': 0, 'judge_reason': 'not scored'})
            item['judge_score'] = meta['judge_score']
            item['judge_reason'] = meta['judge_reason']
        
        # Sort by judge_score (desc), fallback to original order
        limited.sort(key=lambda x: x.get('judge_score', 0), reverse=True)
        
        # Append any untouched candidates (if we clipped for prompt)
        if len(candidates) > len(limited):
            rest = candidates[len(limited):]
            for item in rest:
                item['judge_score'] = 0
                item['judge_reason'] = 'not scored'
            limited.extend(rest)
        
        return limited
    
    def rebuild_from_sentences(self, sentences: Dict[str, Any]) -> int:
        """
        Rebuild entire index from sentence library (for debugging/repair).
        Preserves profile and resume_filenames.
        
        Args:
            sentences: Full sentence library dict from user_manager
            
        Returns:
            Number of sentences indexed
        """
        # Preserve existing data
        old_profile = self.profile
        old_filenames = self.resume_filenames
        old_created = self.created_at
        
        # Reset index
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.sentences = []
        self.sentence_metadata = []
        
        # Collect indexable sentences
        texts_to_index = []
        metadata_list = []
        
        for section, content in sentences.items():
            if section.lower() not in self.INDEXABLE_SECTIONS:
                continue
            
            if isinstance(content, dict):
                for category, items in content.items():
                    if isinstance(items, list):
                        for item in items:
                            text = item.get('text', item.get('sentence', '')) if isinstance(item, dict) else str(item)
                            if text.strip():
                                texts_to_index.append(text)
                                metadata_list.append({
                                    'section': section,
                                    'category': category,
                                    'source': 'rebuild'
                                })
            elif isinstance(content, list):
                for item in content:
                    text = item.get('text', item.get('sentence', '')) if isinstance(item, dict) else str(item)
                    if text.strip():
                        texts_to_index.append(text)
                        metadata_list.append({
                            'section': section,
                            'category': None,
                            'source': 'rebuild'
                        })
        
        # Generate embeddings and add to index
        if texts_to_index:
            embeddings = self._embed(texts_to_index)
            self.index.add(embeddings)
            self.sentences = texts_to_index
            self.sentence_metadata = metadata_list
        
        # Restore preserved data
        self.profile = old_profile
        self.resume_filenames = old_filenames
        self.created_at = old_created
        
        self._save()
        return len(texts_to_index)
    
    def add_resume_filename(self, filename: str):
        """Add a resume filename to the lookup list"""
        if filename and filename not in self.resume_filenames:
            self.resume_filenames.append(filename)
            self._save()
    
    def update_profile(self, profile_updates: Dict[str, Any]):
        """Update user profile data (non-indexed)"""
        self.profile.update(profile_updates)
        self._save()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'username': self.username,
            'total_sentences': len(self.sentences),
            'index_size': self.index.ntotal if self.index else 0,
            'resume_count': len(self.resume_filenames),
            'resume_files': self.resume_filenames,
            'has_profile': bool(self.profile),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def delete(self) -> bool:
        """Delete the index file"""
        if self.index_path.exists():
            os.remove(self.index_path)
            return True
        return False


# ==================== Utility Functions ====================

def get_username_from_filename(filename: str, indexes_dir: str = "resume_gen/indexes") -> Optional[str]:
    """
    Look up username from resume filename across all indexes.
    
    Args:
        filename: Resume filename to look up
        indexes_dir: Directory containing index files
        
    Returns:
        Username if found, None otherwise
    """
    indexes_path = Path(indexes_dir)
    if not indexes_path.exists():
        return None
    
    for index_file in indexes_path.glob("*_rag.pkl"):
        try:
            with open(index_file, 'rb') as f:
                data = pickle.load(f)
            
            if filename in data.get('resume_filenames', []):
                # Extract username from filename
                return index_file.stem.replace('_rag', '')
        except:
            continue
    
    return None


def list_all_indexes(indexes_dir: str = "resume_gen/indexes") -> List[Dict[str, Any]]:
    """List all RAG indexes with basic stats"""
    indexes_path = Path(indexes_dir)
    if not indexes_path.exists():
        return []
    
    results = []
    for index_file in indexes_path.glob("*_rag.pkl"):
        username = index_file.stem.replace('_rag', '')
        try:
            idx = UserRAGIndex(username, indexes_dir)
            results.append(idx.get_stats())
        except:
            results.append({
                'username': username,
                'error': 'Failed to load index'
            })
    
    return results
