"""
Resume Generator - Generate tailored resumes using hybrid matching + LLM polish
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add parent to path for package imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from resume_gen.user_manager import UserManager
from resume_gen.matcher import HybridMatcher

try:
    from core.llm_client import LocalLLM
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠ LocalLLM not available - will skip LLM polish step")


class ResumeGenerator:
    def __init__(self, username: str, data_file: str = None):
        """Initialize generator for a specific user
        
        Args:
            username: User whose sentences to use
            data_file: Path to users_data.json (optional)
        """
        self.username = username
        self.user_manager = UserManager(data_file)
        self.matcher = None
        self.llm = None
        
        # Verify user exists
        if not self.user_manager.user_exists(username):
            raise ValueError(f"User '{username}' not found. Create user first.")
        
        # Load user's sentences into matcher
        self._load_sentences()
        
        # Initialize LLM if available
        if LLM_AVAILABLE:
            try:
                self.llm = LocalLLM()
            except Exception as e:
                print(f"⚠ Could not initialize LLM: {e}")
    
    def _load_sentences(self):
        """Load user's sentences into the matcher"""
        sentences = self.user_manager.get_sentences_flat(self.username)
        self.matcher = HybridMatcher(sentences)
        print(f"✓ Loaded {len(sentences)} sentences for user '{self.username}'")
    
    def reload_sentences(self):
        """Reload sentences from database (call after adding new sentences)"""
        self._load_sentences()
    
    def analyze_job(self, job_description: str) -> Dict:
        """Analyze a job posting and extract requirements
        
        Returns dict with keywords, requirements breakdown, etc.
        """
        keywords = self.matcher.extract_keywords(job_description)
        
        return {
            "keywords": keywords,
            "keyword_count": len(keywords),
            "text_length": len(job_description),
            "has_ml": any(k in keywords for k in ['machine_learning', 'ml', 'ai', 'deep_learning']),
            "has_leadership": any(k in keywords for k in ['leadership', 'management', 'team_lead']),
            "has_cloud": any(k in keywords for k in ['aws', 'azure', 'gcp', 'cloud']),
        }
    
    def find_matching_sentences(self, job_description: str, 
                                 top_k: int = 15) -> List[Tuple[Dict, float, str]]:
        """Find best matching sentences for a job posting
        
        Returns list of (sentence, score, match_type) tuples
        """
        return self.matcher.hybrid_match(job_description, top_k=top_k)
    
    def generate_section(self, job_description: str, section_type: str,
                         max_items: int = 5) -> List[str]:
        """Generate a resume section with best-matching sentences
        
        Args:
            job_description: Job posting text
            section_type: 'skill', 'experience', 'achievements', etc.
            max_items: Maximum items to include
            
        Returns:
            List of sentence strings (polished if LLM available)
        """
        # Get matches for this section type
        matches = self.matcher.match_by_type(job_description, section_type, top_k=max_items)
        
        if not matches:
            return []
        
        sentences = [m[0]["text"] for m in matches]
        
        # Optionally polish with LLM
        if self.llm and len(sentences) > 0:
            sentences = self._polish_sentences(sentences, job_description, section_type)
        
        return sentences
    
    def _polish_sentences(self, sentences: List[str], job_description: str, 
                          section_type: str) -> List[str]:
        """Use LLM to tailor sentences to the job posting"""
        if not self.llm:
            return sentences
        
        prompt = f"""You are a professional resume writer. Given these resume bullet points and a job description, 
slightly reword each bullet point to better align with the job requirements while keeping the core facts intact.
Do NOT invent new achievements or skills - only adjust wording.

Job Description (excerpt):
{job_description[:500]}...

Original {section_type} bullet points:
{chr(10).join(f'- {s}' for s in sentences)}

Rewrite each bullet point on its own line, starting with a dash (-). Keep the same number of bullets."""

        try:
            response = self.llm.chat(prompt, max_tokens=500)
            
            # Parse response into list
            polished = []
            for line in response.strip().split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    polished.append(line[1:].strip())
                elif line.startswith('•'):
                    polished.append(line[1:].strip())
            
            # Fall back to original if parsing failed
            if len(polished) != len(sentences):
                return sentences
            
            return polished
            
        except Exception as e:
            print(f"⚠ LLM polish failed: {e}")
            return sentences
    
    def generate_resume(self, job_description: str, 
                        sections: Dict[str, int] = None) -> Dict[str, List[str]]:
        """Generate a complete tailored resume
        
        Args:
            job_description: Job posting text
            sections: Dict of {section_type: max_items} to include
                     Default: {"skill": 6, "experience": 4, "achievements": 3}
        
        Returns:
            Dict of {section_name: [sentences]}
        """
        if sections is None:
            sections = {
                "skill": 6,
                "experience": 4,
                "achievements": 3,
                "projects": 2
            }
        
        resume = {}
        
        for section_type, max_items in sections.items():
            sentences = self.generate_section(job_description, section_type, max_items)
            if sentences:
                resume[section_type] = sentences
        
        return resume
    
    def format_resume_text(self, resume: Dict[str, List[str]], 
                           include_header: bool = True) -> str:
        """Format resume dict as plain text
        
        Args:
            resume: Dict from generate_resume()
            include_header: Whether to include user profile header
        """
        lines = []
        
        # Header
        if include_header:
            user = self.user_manager.get_user(self.username)
            profile = user.get("profile", {})
            name = profile.get("name", self.username)
            email = profile.get("email", "")
            
            lines.append(f"{'='*60}")
            lines.append(f"{name.upper()}")
            if email:
                lines.append(f"{email}")
            lines.append(f"{'='*60}")
            lines.append("")
        
        # Sections
        section_titles = {
            "skill": "TECHNICAL SKILLS",
            "experience": "PROFESSIONAL EXPERIENCE",
            "achievements": "KEY ACHIEVEMENTS",
            "projects": "PROJECTS",
            "education": "EDUCATION",
            "certifications": "CERTIFICATIONS"
        }
        
        for section_type, sentences in resume.items():
            title = section_titles.get(section_type, section_type.upper())
            lines.append(title)
            lines.append("-" * len(title))
            for sentence in sentences:
                lines.append(f"• {sentence}")
            lines.append("")
        
        return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    from user_manager import UserManager
    
    # Ensure demo user exists with sample data
    um = UserManager()
    if not um.user_exists("demo"):
        um.create_user("demo", {"name": "Demo User", "email": "demo@example.com"})
        
        # Add sample sentences
        um.add_sentence("demo", "skills", "Built production APIs with FastAPI serving 10K+ requests/day", "python", ["api", "backend"])
        um.add_sentence("demo", "skills", "Developed ML pipelines using scikit-learn achieving 95% accuracy", "machine_learning", ["ml", "data_science"])
        um.add_sentence("demo", "skills", "Deployed containerized applications using Docker and Kubernetes", "devops", ["docker", "kubernetes"])
        um.add_sentence("demo", "experience", "Led team of 5 engineers in agile development environment", "leadership", ["management", "agile"])
        um.add_sentence("demo", "experience", "Designed distributed data pipelines processing 1M+ records daily", "data_engineering", ["etl", "big_data"])
        um.add_sentence("demo", "achievements", "Reduced system latency by 40% through query optimization")
        um.add_sentence("demo", "achievements", "Increased test coverage from 45% to 92%")
        um.add_sentence("demo", "projects", "Built real-time analytics dashboard with React and D3.js")
        
        print("✓ Created demo user with sample data\n")
    
    # Test generator
    generator = ResumeGenerator("demo")
    
    job_desc = """
    Senior Python Developer
    
    We're looking for an experienced Python developer to join our team.
    
    Requirements:
    - 5+ years Python experience
    - Experience with FastAPI or Django
    - Machine learning background preferred
    - Docker and Kubernetes experience
    - Team leadership experience
    - Strong communication skills
    """
    
    print("\n" + "="*60)
    print("JOB ANALYSIS")
    print("="*60)
    analysis = generator.analyze_job(job_desc)
    print(f"Keywords found: {analysis['keywords']}")
    print(f"Has ML requirement: {analysis['has_ml']}")
    print(f"Has leadership requirement: {analysis['has_leadership']}")
    
    print("\n" + "="*60)
    print("TOP MATCHING SENTENCES")
    print("="*60)
    matches = generator.find_matching_sentences(job_desc, top_k=5)
    for sentence, score, match_type in matches:
        print(f"[{match_type:5}] {score:.3f} - {sentence['text']}")
    
    print("\n" + "="*60)
    print("GENERATED RESUME")
    print("="*60)
    resume = generator.generate_resume(job_desc)
    print(generator.format_resume_text(resume))
