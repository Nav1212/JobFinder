"""
User Manager - CRUD operations for multi-user resume data
Stores all users in a single JSON file with isolated sentence libraries
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

# RAG integration (lazy loaded to avoid circular imports)
_rag_module = None

def _get_rag_module():
    """Lazy load RAG module to avoid circular imports"""
    global _rag_module
    if _rag_module is None:
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from core import resume_rag
            _rag_module = resume_rag
        except ImportError as e:
            print(f"Warning: RAG module not available: {e}")
            _rag_module = False
    return _rag_module if _rag_module else None


class UserManager:
    def __init__(self, data_file: str = None):
        """Initialize user manager with data file path"""
        if data_file is None:
            data_file = Path(__file__).parent / 'users_data.json'
        self.data_file = Path(data_file)
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Create data file if it doesn't exist"""
        if not self.data_file.exists():
            self._save_data({
                "_metadata": {
                    "version": "1.0",
                    "created": datetime.now().isoformat(),
                    "description": "Multi-user resume sentence library"
                },
                "users": {}
            })
    
    def _load_data(self) -> Dict:
        """Load all data from JSON file"""
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_data(self, data: Dict):
        """Save all data to JSON file"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # ==================== User Operations ====================
    
    def list_users(self) -> List[str]:
        """Get list of all usernames"""
        data = self._load_data()
        return list(data.get("users", {}).keys())
    
    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        return username in self.list_users()
    
    def create_user(self, username: str, profile: Dict = None) -> bool:
        """Create a new user with empty sentence library"""
        if self.user_exists(username):
            return False
        
        data = self._load_data()
        data["users"][username] = {
            "profile": profile or {
                "name": username,
                "email": "",
                "created": datetime.now().isoformat()
            },
            "resume_filenames": [],  # List of resume files for this user
            "sentences": {
                "skills": {},
                "experience": {},
                "achievements": [],
                "education": [],
                "certifications": [],
                "projects": []
            },
            "templates": {}
        }
        self._save_data(data)
        return True
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user data by username"""
        data = self._load_data()
        return data.get("users", {}).get(username)
    
    def update_user_profile(self, username: str, profile: Dict) -> bool:
        """Update user profile information"""
        if not self.user_exists(username):
            return False
        
        data = self._load_data()
        data["users"][username]["profile"].update(profile)
        self._save_data(data)
        
        # Update RAG index profile (non-indexed data like education)
        rag = _get_rag_module()
        if rag:
            try:
                idx = rag.UserRAGIndex(username, self._get_indexes_dir())
                if idx.exists():
                    idx.update_profile(profile)
            except Exception as e:
                print(f"Warning: Failed to update RAG profile for {username}: {e}")
        
        return True
    
    def _get_indexes_dir(self) -> str:
        """Get RAG indexes directory path"""
        return str(Path(__file__).parent / "indexes")
    
    def delete_user(self, username: str) -> bool:
        """Delete user and all their data"""
        if not self.user_exists(username):
            return False
        
        data = self._load_data()
        del data["users"][username]
        self._save_data(data)
        
        # Auto-delete orphaned RAG index when user is deleted
        # This prevents stale indexes from accumulating and saves disk space
        rag = _get_rag_module()
        if rag:
            try:
                idx = rag.UserRAGIndex(username, self._get_indexes_dir())
                if idx.exists():
                    idx.delete()
                    print(f"✓ Deleted RAG index for {username}")
            except Exception as e:
                print(f"Warning: Failed to delete RAG index for {username}: {e}")
        
        return True
    
    # ==================== Sentence Operations ====================
    
    def get_all_sentences(self, username: str) -> Dict:
        """Get all sentences for a user"""
        user = self.get_user(username)
        if not user:
            return {}
        return user.get("sentences", {})
    
    def get_sentences_flat(self, username: str) -> List[Dict]:
        """Get all sentences as flat list with metadata"""
        sentences = self.get_all_sentences(username)
        flat = []
        
        # Skills (nested by category)
        for category, items in sentences.get("skills", {}).items():
            for item in items:
                if isinstance(item, str):
                    flat.append({"text": item, "type": "skill", "tags": [category]})
                elif isinstance(item, dict):
                    flat.append({
                        "text": item.get("text", ""),
                        "type": "skill",
                        "tags": [category] + item.get("tags", [])
                    })
        
        # Experience (nested by category)
        for category, items in sentences.get("experience", {}).items():
            for item in items:
                if isinstance(item, str):
                    flat.append({"text": item, "type": "experience", "tags": [category]})
                elif isinstance(item, dict):
                    flat.append({
                        "text": item.get("text", ""),
                        "type": "experience",
                        "tags": [category] + item.get("tags", [])
                    })
        
        # Simple lists
        for list_type in ["achievements", "education", "certifications", "projects"]:
            for item in sentences.get(list_type, []):
                if isinstance(item, str):
                    flat.append({"text": item, "type": list_type, "tags": []})
                elif isinstance(item, dict):
                    flat.append({
                        "text": item.get("text", ""),
                        "type": list_type,
                        "tags": item.get("tags", [])
                    })
        
        return flat
    
    def add_sentence(self, username: str, sentence_type: str, text: str, 
                     category: str = None, tags: List[str] = None) -> bool:
        """Add a sentence to user's library
        
        Args:
            username: User to add sentence for
            sentence_type: 'skills', 'experience', 'achievements', etc.
            text: The sentence text
            category: For skills/experience, the sub-category (e.g., 'python', 'leadership')
            tags: Optional additional tags for matching
        """
        if not self.user_exists(username):
            return False
        
        data = self._load_data()
        sentences = data["users"][username]["sentences"]
        
        # Build sentence entry
        if tags:
            entry = {"text": text, "tags": tags}
        else:
            entry = text
        
        # Add to appropriate location
        if sentence_type in ["skills", "experience"]:
            if category is None:
                category = "general"
            if category not in sentences[sentence_type]:
                sentences[sentence_type][category] = []
            sentences[sentence_type][category].append(entry)
        elif sentence_type in ["achievements", "education", "certifications", "projects"]:
            sentences[sentence_type].append(entry)
        else:
            return False
        
        self._save_data(data)
        
        # Update RAG index if sentence is in indexable sections
        if sentence_type in ["skills", "experience", "achievements"]:
            rag = _get_rag_module()
            if rag:
                try:
                    idx = rag.UserRAGIndex(username, self._get_indexes_dir())
                    if idx.exists():
                        # Add single sentence to existing index
                        added, duplicates = idx.add_sentences(
                            [{"text": text}], 
                            section=sentence_type, 
                            category=category
                        )
                        if duplicates:
                            print(f"⚠ Similar sentence already exists: {duplicates[0]['similar_to'][:50]}...")
                except Exception as e:
                    print(f"Warning: Failed to update RAG index: {e}")
        
        return True
    
    def remove_sentence(self, username: str, sentence_type: str, text: str,
                        category: str = None) -> bool:
        """Remove a sentence from user's library"""
        if not self.user_exists(username):
            return False
        
        data = self._load_data()
        sentences = data["users"][username]["sentences"]
        
        if sentence_type in ["skills", "experience"]:
            if category and category in sentences[sentence_type]:
                items = sentences[sentence_type][category]
                sentences[sentence_type][category] = [
                    item for item in items
                    if (item if isinstance(item, str) else item.get("text", "")) != text
                ]
        elif sentence_type in ["achievements", "education", "certifications", "projects"]:
            items = sentences[sentence_type]
            sentences[sentence_type] = [
                item for item in items
                if (item if isinstance(item, str) else item.get("text", "")) != text
            ]
        
        self._save_data(data)
        return True
    
    def get_categories(self, username: str, sentence_type: str) -> List[str]:
        """Get all categories for a sentence type (skills/experience)"""
        sentences = self.get_all_sentences(username)
        if sentence_type in ["skills", "experience"]:
            return list(sentences.get(sentence_type, {}).keys())
        return []
    
    def get_all_tags(self, username: str) -> List[str]:
        """Get all unique tags used by a user"""
        flat = self.get_sentences_flat(username)
        tags = set()
        for item in flat:
            tags.update(item.get("tags", []))
        return sorted(tags)
    
    # ==================== Resume Filename Operations ====================
    
    def add_resume_filename(self, username: str, filename: str) -> bool:
        """Add a resume filename to user's tracked files"""
        if not self.user_exists(username):
            return False
        
        data = self._load_data()
        user = data["users"][username]
        
        # Ensure resume_filenames list exists (for older data)
        if "resume_filenames" not in user:
            user["resume_filenames"] = []
        
        if filename not in user["resume_filenames"]:
            user["resume_filenames"].append(filename)
            self._save_data(data)
            
            # Also update RAG index filename list
            rag = _get_rag_module()
            if rag:
                try:
                    idx = rag.UserRAGIndex(username, self._get_indexes_dir())
                    if idx.exists():
                        idx.add_resume_filename(filename)
                except Exception as e:
                    print(f"Warning: Failed to update RAG filenames: {e}")
        
        return True
    
    def get_resume_filenames(self, username: str) -> List[str]:
        """Get list of resume filenames for a user"""
        user = self.get_user(username)
        if not user:
            return []
        return user.get("resume_filenames", [])
    
    def get_username_by_filename(self, filename: str) -> Optional[str]:
        """Look up username from resume filename"""
        data = self._load_data()
        for username, user_data in data.get("users", {}).items():
            if filename in user_data.get("resume_filenames", []):
                return username
        return None
    
    # ==================== RAG Index Operations ====================
    
    def rebuild_rag_index(self, username: str) -> int:
        """Rebuild RAG index from current sentence library (for debugging)"""
        if not self.user_exists(username):
            return -1
        
        rag = _get_rag_module()
        if not rag:
            print("RAG module not available")
            return -1
        
        try:
            sentences = self.get_all_sentences(username)
            idx = rag.UserRAGIndex(username, self._get_indexes_dir())
            count = idx.rebuild_from_sentences(sentences)
            print(f"✓ Rebuilt RAG index for {username}: {count} sentences indexed")
            return count
        except Exception as e:
            print(f"Failed to rebuild RAG index: {e}")
            return -1
    
    def get_rag_index_stats(self, username: str) -> Optional[Dict]:
        """Get RAG index statistics for a user"""
        rag = _get_rag_module()
        if not rag:
            return None
        
        try:
            idx = rag.UserRAGIndex(username, self._get_indexes_dir())
            if idx.exists():
                return idx.get_stats()
            return None
        except Exception as e:
            print(f"Failed to get RAG stats: {e}")
            return None


# Quick test
if __name__ == "__main__":
    um = UserManager()
    
    # Create test user
    if not um.user_exists("demo"):
        um.create_user("demo", {"name": "Demo User", "email": "demo@example.com"})
        
        # Add some sentences
        um.add_sentence("demo", "skills", "Built production APIs with FastAPI serving 10K+ requests/day", "python")
        um.add_sentence("demo", "skills", "Developed ML pipelines using scikit-learn and TensorFlow", "machine_learning")
        um.add_sentence("demo", "experience", "Led team of 5 engineers in agile environment", "leadership")
        um.add_sentence("demo", "achievements", "Reduced system latency by 40% through optimization")
        
        print("✓ Created demo user with sample sentences")
    
    # Show users
    print(f"\nUsers: {um.list_users()}")
    print(f"Demo sentences: {len(um.get_sentences_flat('demo'))} total")
    print(f"Tags: {um.get_all_tags('demo')}")
