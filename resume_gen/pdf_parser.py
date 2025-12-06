"""
PDF Resume Parser with LLM-based analysis
Extracts text from PDF resumes and uses LLM to categorize and score sentences

Architecture:
- Parsing (sentence extraction): Uses small/fast model via SentenceParser
- Grading (scoring sentences): Uses medium model for quality assessment
"""

import json
import re
import requests
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .sentence_parser import SentenceParser, load_parser_from_config


@dataclass
class ParsedSentence:
    """A sentence extracted from a resume with LLM analysis"""
    text: str
    original_text: str  # Keep original for comparison
    category: str  # skills, experience, achievements, etc.
    suggested_category: str  # LLM suggestion if different
    tags: List[str] = field(default_factory=list)
    
    # Three quality scores (0-100)
    categorization_confidence: int = 0
    extraction_quality: int = 0
    impact_score: int = 0
    
    # Suggestions
    impact_suggestion: str = ""
    extraction_issues: List[str] = field(default_factory=list)
    
    # User edits (during review)
    user_edited_text: Optional[str] = None
    user_category_override: Optional[str] = None
    
    # Status
    is_rescoring: bool = False
    
    def get_display_text(self) -> str:
        """Get the text to display (user edit or original)"""
        return self.user_edited_text if self.user_edited_text else self.text
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class ReviewSession:
    """Holds all parsed sentences during import review"""
    source_file: str
    sentences: List[ParsedSentence] = field(default_factory=list)
    raw_text: str = ""
    parse_errors: List[str] = field(default_factory=list)
    
    def get_by_category(self, category: str) -> List[ParsedSentence]:
        """Get sentences filtered by category"""
        return [s for s in self.sentences if s.category == category]
    
    def get_low_confidence(self, threshold: int = 70) -> List[ParsedSentence]:
        """Get sentences with low categorization confidence"""
        return [s for s in self.sentences if s.categorization_confidence < threshold]
    
    def get_low_quality(self, threshold: int = 70) -> List[ParsedSentence]:
        """Get sentences with low extraction quality"""
        return [s for s in self.sentences if s.extraction_quality < threshold]
    
    def get_low_impact(self, threshold: int = 70) -> List[ParsedSentence]:
        """Get sentences with low impact score"""
        return [s for s in self.sentences if s.impact_score < threshold]


class PDFParser:
    """Parses PDF resumes and extracts structured data"""
    
    def __init__(self, llm_base_url: str = None, 
                 llm_model: str = None,
                 parsing_model: str = None):
        """
        Initialize PDF Parser with configurable models.
        
        Args:
            llm_base_url: Ollama API URL (default from config)
            llm_model: Model for grading/scoring (default from config)
            parsing_model: Model for sentence extraction (default from config)
        """
        # Load from config if not provided
        config = self._load_config()
        models_config = config.get('models', {})
        
        self.llm_base_url = llm_base_url or models_config.get('ollama_url', 'http://localhost:11434')
        self.llm_model = llm_model or models_config.get('grading_model', 'llama3.1:8b')
        self.parsing_model = parsing_model or models_config.get('parsing_model', 'llama3.2:1b')
        
        # Initialize sentence parser with dedicated parsing model
        self.sentence_parser = SentenceParser(
            model=self.parsing_model,
            base_url=self.llm_base_url
        )
        
        self._check_dependencies()
    
    def _load_config(self) -> Dict:
        """Load config.yaml"""
        config_path = Path(__file__).parent.parent / 'config.yaml'
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except:
            pass
        return {}
    
    def _check_dependencies(self):
        """Check if required PDF libraries are available"""
        self.pdf_library = None
        try:
            import pdfplumber
            self.pdf_library = "pdfplumber"
        except ImportError:
            try:
                import PyPDF2
                self.pdf_library = "PyPDF2"
            except ImportError:
                pass
    
    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, List[str]]:
        """Extract text from PDF file
        
        Returns:
            Tuple of (extracted_text, list_of_errors)
        """
        errors = []
        
        if self.pdf_library is None:
            return "", ["No PDF library available. Install pdfplumber or PyPDF2"]
        
        path = Path(pdf_path)
        if not path.exists():
            return "", [f"File not found: {pdf_path}"]
        
        text = ""
        
        try:
            if self.pdf_library == "pdfplumber":
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            
            elif self.pdf_library == "PyPDF2":
                import PyPDF2
                with open(path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
        
        except Exception as e:
            errors.append(f"PDF extraction error: {str(e)}")
        
        return text.strip(), errors
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into individual sentences/bullet points"""
        # Split on bullet points, newlines, and sentence endings
        lines = []
        
        # First split by newlines
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Remove common bullet characters
            line = re.sub(r'^[\•\-\–\—\*\○\●\◦\▪\▸\►]+\s*', '', line)
            line = re.sub(r'^\d+[\.\)]\s*', '', line)  # Numbered lists
            
            # Skip very short lines (likely headers or noise)
            if len(line) < 10:
                continue
            
            # Skip lines that look like headers
            if line.isupper() and len(line) < 50:
                continue
            
            lines.append(line)
        
        return lines
    
    def _call_llm(self, prompt: str, stream: bool = False) -> str:
        """Call the LLM API"""
        url = f"{self.llm_base_url}/api/generate"
        data = {
            "model": self.llm_model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": 0.3  # Lower for more consistent scoring
            }
        }
        
        try:
            print(f"  [LLM] Calling {self.llm_model} with {len(prompt)} char prompt...")
            response = requests.post(url, json=data, timeout=120)  # Increased timeout
            
            # Check HTTP status
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                print(f"  [LLM] ERROR: {error_msg}")
                return f"LLM_ERROR: {error_msg}"
            
            result = response.json()
            
            # Check for error in response
            if 'error' in result:
                error_msg = result['error']
                print(f"  [LLM] ERROR from Ollama: {error_msg}")
                return f"LLM_ERROR: {error_msg}"
            
            llm_response = result.get('response', '')
            print(f"  [LLM] Got {len(llm_response)} char response")
            return llm_response
            
        except requests.exceptions.Timeout:
            print(f"  [LLM] ERROR: Request timed out after 120s")
            return "LLM_ERROR: Request timed out - model may be overloaded"
        except requests.exceptions.ConnectionError as e:
            print(f"  [LLM] ERROR: Connection failed - {e}")
            return f"LLM_ERROR: Connection refused - is Ollama running? (ollama serve)"
        except Exception as e:
            print(f"  [LLM] ERROR: {type(e).__name__}: {e}")
            return f"LLM_ERROR: {type(e).__name__}: {str(e)}"
    
    def _analyze_sentence_batch(self, sentences: List[str]) -> List[Dict]:
        """Analyze a batch of sentences with single LLM call"""
        if not sentences:
            return []
        
        print(f"  [BATCH] Analyzing {len(sentences)} sentences...")
        
        # Build prompt for batch analysis
        prompt = """You are analyzing resume bullet points. For each sentence, provide:
1. category: One of [skills, experience, achievements, projects, education, certifications, summary]
2. suggested_category: Your suggested category if different (or same if confident)
3. tags: Relevant skill/topic tags (comma-separated)
4. categorization_confidence: 0-100 how confident you are in the category
5. extraction_quality: 0-100 how clean/well-formed the text is (deduct for OCR errors, incomplete sentences, etc.)
6. impact_score: 0-100 how impactful/impressive the achievement is
7. impact_suggestion: A rewritten version that sounds more impactful (or empty if already good)
8. extraction_issues: List of any issues found (OCR errors, truncation, etc.)

Return ONLY a valid JSON array with one object per sentence. No other text.

Sentences to analyze:
"""
        for i, sentence in enumerate(sentences):
            prompt += f"\n{i+1}. {sentence}"
        
        prompt += "\n\nJSON Response:"
        
        response = self._call_llm(prompt)
        
        # Check for LLM errors
        if response.startswith("LLM_ERROR:"):
            print(f"  [BATCH] LLM call failed: {response}")
            return []
        
        # Parse JSON response
        try:
            # Try to find JSON in response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                print(f"  [BATCH] Successfully parsed {len(parsed)} results")
                return parsed
            else:
                print(f"  [BATCH] No JSON array found in response")
                print(f"  [BATCH] Response preview: {response[:500]}...")
                return []
        except json.JSONDecodeError as e:
            print(f"  [BATCH] JSON parse error: {e}")
            print(f"  [BATCH] Response preview: {response[:500]}...")
            return []
    
    def _grade_single_sentence(self, sentence: str) -> Dict:
        """Grade a single sentence and return analysis dict"""
        prompt = f"""Analyze this resume bullet point. Return ONLY a JSON object with:
- category: One of [skills, experience, achievements, projects, education, certifications, summary]
- suggested_category: Your suggested category if different (or same if confident)
- tags: Relevant skill/topic tags as array
- categorization_confidence: 0-100 how confident in category
- extraction_quality: 0-100 how clean/well-formed the text is
- impact_score: 0-100 how impactful/impressive
- impact_suggestion: Rewritten more impactful version (or empty if good)
- extraction_issues: Array of any issues found

Sentence: {sentence}

JSON Response:"""
        
        response = self._call_llm(prompt)
        
        # Check for LLM errors
        if response.startswith("LLM_ERROR:"):
            error_msg = response.replace('LLM_ERROR: ', '')
            print(f"  [GRADE] LLM error: {error_msg}")
            return self._default_analysis(error_msg)
        
        # Parse JSON response
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                # Validate required fields exist
                if 'category' in parsed:
                    return parsed
            
            print(f"  [GRADE] No valid JSON in response: {response[:200]}...")
            return self._default_analysis("Invalid LLM response format")
        except json.JSONDecodeError as e:
            print(f"  [GRADE] JSON parse error: {e}")
            return self._default_analysis("JSON parse error")
    
    def _default_analysis(self, error_msg: str = "") -> Dict:
        """Return default analysis dict when LLM fails"""
        return {
            "category": "experience",
            "suggested_category": "experience",
            "tags": [],
            "categorization_confidence": 50,
            "extraction_quality": 80,
            "impact_score": 50,
            "impact_suggestion": "",
            "extraction_issues": [error_msg] if error_msg else []
        }
    
    def _analyze_single_sentence(self, sentence: str) -> Dict:
        """Analyze a single sentence (for re-scoring after edits)"""
        prompt = f"""Analyze this resume bullet point and return a JSON object with:
- category: One of [skills, experience, achievements, projects, education, certifications, summary]
- tags: Relevant skill/topic tags as array
- categorization_confidence: 0-100 how confident in category
- extraction_quality: 0-100 how clean/well-formed the text is
- impact_score: 0-100 how impactful/impressive
- impact_suggestion: Rewritten more impactful version (or empty if already good)
- extraction_issues: Array of any issues found

Sentence: {sentence}

Return ONLY valid JSON, no other text:"""
        
        response = self._call_llm(prompt)
        
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}
        except json.JSONDecodeError:
            return {}
    
    def parse_pdf(self, pdf_path: str, callback=None, use_llm_parsing: bool = True) -> ReviewSession:
        """Parse a PDF resume and return a ReviewSession
        
        Args:
            pdf_path: Path to PDF file
            callback: Optional callback(progress, message) for progress updates
            use_llm_parsing: If True, use LLM for sentence parsing (slower but more accurate)
        """
        session = ReviewSession(source_file=pdf_path)
        
        # Step 1: Extract text
        if callback:
            callback(0.1, "Extracting text from PDF...")
        
        text, errors = self.extract_text_from_pdf(pdf_path)
        session.raw_text = text
        session.parse_errors.extend(errors)
        
        if not text:
            session.parse_errors.append("No text extracted from PDF")
            return session
        
        # Step 2: Parse into sentences (using dedicated parsing model)
        if callback:
            callback(0.15, f"Parsing sentences with {self.parsing_model}...")
        
        if use_llm_parsing:
            # Use LLM-based sentence parser (small model, handles OCR errors)
            parse_result = self.sentence_parser.parse(text)
            raw_sentences = [s.text for s in parse_result.sentences]
            session.parse_errors.extend(parse_result.parse_errors)
            
            if callback:
                callback(0.25, f"Found {len(raw_sentences)} sentences")
        else:
            # Fallback to regex-based splitting (fast but less accurate)
            raw_sentences = self._split_into_sentences(text)
        
        if not raw_sentences:
            session.parse_errors.append("No valid sentences found in PDF")
            return session
        
        # Step 3: Grade/analyze with LLM (using grading model) - one at a time for reliability
        if callback:
            callback(0.3, f"Grading sentences with {self.llm_model}...")
        
        all_analyses = []
        total = len(raw_sentences)
        
        for i, sentence in enumerate(raw_sentences):
            progress = 0.3 + (0.6 * (i / total))
            
            if callback:
                callback(progress, f"Grading sentence {i+1}/{total}...")
            
            analysis = self._grade_single_sentence(sentence)
            all_analyses.append(analysis)
        
        # Step 4: Create ParsedSentence objects
        if callback:
            callback(0.95, "Finalizing results...")
        
        for sentence, analysis in zip(raw_sentences, all_analyses):
            parsed = ParsedSentence(
                text=sentence,
                original_text=sentence,
                category=analysis.get("category", "experience"),
                suggested_category=analysis.get("suggested_category", analysis.get("category", "experience")),
                tags=analysis.get("tags", []) if isinstance(analysis.get("tags"), list) else 
                     [t.strip() for t in str(analysis.get("tags", "")).split(",") if t.strip()],
                categorization_confidence=int(analysis.get("categorization_confidence", 50)),
                extraction_quality=int(analysis.get("extraction_quality", 80)),
                impact_score=int(analysis.get("impact_score", 50)),
                impact_suggestion=analysis.get("impact_suggestion", ""),
                extraction_issues=analysis.get("extraction_issues", []) if isinstance(analysis.get("extraction_issues"), list) else []
            )
            session.sentences.append(parsed)
        
        if callback:
            callback(1.0, f"Parsed {len(session.sentences)} sentences")
        
        return session
    
    def rescore_sentence(self, sentence: ParsedSentence, new_text: str) -> ParsedSentence:
        """Re-score a sentence after user edit
        
        Returns updated ParsedSentence with new scores
        """
        analysis = self._analyze_single_sentence(new_text)
        
        if not analysis:
            # LLM failed, keep old scores but update text
            sentence.user_edited_text = new_text
            return sentence
        
        # Update with new analysis
        sentence.user_edited_text = new_text
        sentence.category = analysis.get("category", sentence.category)
        sentence.suggested_category = analysis.get("category", sentence.category)
        sentence.tags = analysis.get("tags", sentence.tags) if isinstance(analysis.get("tags"), list) else \
                       [t.strip() for t in str(analysis.get("tags", "")).split(",") if t.strip()]
        sentence.categorization_confidence = int(analysis.get("categorization_confidence", 50))
        sentence.extraction_quality = int(analysis.get("extraction_quality", 80))
        sentence.impact_score = int(analysis.get("impact_score", 50))
        sentence.impact_suggestion = analysis.get("impact_suggestion", "")
        sentence.extraction_issues = analysis.get("extraction_issues", []) if isinstance(analysis.get("extraction_issues"), list) else []
        
        return sentence
    
    def extract_user_profile(self, pdf_path: str = None, text: str = None) -> Dict:
        """
        Extract user profile information from resume.
        Used to auto-populate user data and derive username.
        
        Args:
            pdf_path: Path to PDF file (will extract text)
            text: Pre-extracted text (optional, skips PDF extraction)
            
        Returns:
            Dict with profile fields:
            - name: Full name (e.g., "John Doe")
            - username: Derived username (e.g., "john_doe")
            - email: Email address if found
            - phone: Phone number if found
            - location: City/State/Country if found
            - linkedin: LinkedIn URL if found
            - education: List of education entries (NOT indexed in RAG)
            - summary: Professional summary if found
        """
        # Extract text if not provided
        if text is None:
            if pdf_path is None:
                return {"error": "No PDF path or text provided"}
            text, errors = self.extract_text_from_pdf(pdf_path)
            if not text:
                return {"error": f"Failed to extract text: {errors}"}
        
        # Use LLM to extract profile information
        prompt = f"""Extract user profile information from this resume text.

Resume text:
{text[:5000]}

Return a JSON object with these fields:
- name: The person's full name (REQUIRED)
- email: Email address if found (or empty string)
- phone: Phone number if found (or empty string)
- location: City, State/Province, Country if found (or empty string)
- linkedin: LinkedIn URL if found (or empty string)
- education: Array of education entries, each with "degree", "school", "year" (or empty array)
- summary: Professional summary/objective if found (or empty string)

Return ONLY valid JSON, no other text:"""
        
        response = self._call_llm(prompt)
        
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                profile = json.loads(json_match.group())
                
                # Derive username from name
                name = profile.get("name", "").strip()
                if name:
                    # Convert "John Doe" -> "john_doe"
                    username = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
                    username = re.sub(r'\s+', '_', username.strip())
                    profile["username"] = username
                else:
                    profile["username"] = ""
                
                # Ensure all expected fields exist
                profile.setdefault("name", "")
                profile.setdefault("email", "")
                profile.setdefault("phone", "")
                profile.setdefault("location", "")
                profile.setdefault("linkedin", "")
                profile.setdefault("education", [])
                profile.setdefault("summary", "")
                
                return profile
            
            return {"error": "LLM did not return valid JSON"}
        
        except json.JSONDecodeError as e:
            return {"error": f"JSON parse error: {e}"}
        except Exception as e:
            return {"error": f"Profile extraction error: {e}"}


# Quick test
if __name__ == "__main__":
    parser = PDFParser()
    print(f"PDF library: {parser.pdf_library}")
    
    # Test sentence analysis
    test_sentences = [
        "Led team of 5 engineers to deliver project 2 weeks ahead of schedule",
        "Python programming",
        "Reduced system latency by 40% through code optimization"
    ]
    
    print("\nAnalyzing test sentences...")
    results = parser._analyze_sentence_batch(test_sentences)
    
    for sentence, result in zip(test_sentences, results):
        print(f"\n{sentence}")
        print(f"  Category: {result.get('category')} (confidence: {result.get('categorization_confidence')})")
        print(f"  Impact: {result.get('impact_score')}")
        if result.get('impact_suggestion'):
            print(f"  Suggestion: {result.get('impact_suggestion')}")
