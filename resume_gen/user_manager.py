"""
User Manager - CRUD operations for multi-user resume data
Stores all users in a single JSON file with isolated sentence libraries
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any


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
        return True
    
    def delete_user(self, username: str) -> bool:
        """Delete user and all their data"""
        if not self.user_exists(username):
            return False
        
        data = self._load_data()
        del data["users"][username]
        self._save_data(data)
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
