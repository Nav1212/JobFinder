"""
Sentence Parser - Dedicated sentence extraction using small LLM
Separates sentence parsing from grading for better accuracy and speed
"""

import re
import json
import requests
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractedSentence:
    """A sentence extracted from raw text"""
    text: str
    original_text: str
    sentence_type: str  # bullet_point, paragraph, list_item, header
    source_line: int
    confidence: float  # 0.0-1.0 how confident the extraction is clean


@dataclass
class ParseResult:
    """Result of parsing raw text into sentences"""
    sentences: List[ExtractedSentence]
    raw_text: str
    parse_errors: List[str]
    stats: Dict[str, int]  # e.g., {"bullets": 5, "paragraphs": 2}


class SentenceParser:
    """
    Parses raw text into clean sentences using a small, fast LLM.
    
    This is a dedicated step before grading/scoring:
    1. Takes raw PDF text (often messy from OCR)
    2. Uses small LLM to identify and clean sentence boundaries
    3. Outputs structured sentences ready for grading
    
    Uses a small model (1B-3B params) since this is a structural task.
    """
    
    def __init__(
        self, 
        model: str = "llama3.2:1b",
        base_url: str = "http://localhost:11434",
        batch_size: int = 20
    ):
        self.model = model
        self.base_url = base_url
        self.batch_size = batch_size
    
    def parse(self, raw_text: str) -> ParseResult:
        """
        Parse raw text into clean sentences.
        
        Args:
            raw_text: Raw text extracted from PDF (may have OCR errors)
            
        Returns:
            ParseResult with extracted sentences
        """
        errors = []
        stats = {"bullets": 0, "paragraphs": 0, "headers": 0, "total": 0}
        
        # Step 1: Pre-process with regex (fast, no LLM)
        rough_segments = self._preprocess_text(raw_text)
        
        if not rough_segments:
            return ParseResult(
                sentences=[],
                raw_text=raw_text,
                parse_errors=["No text segments found"],
                stats=stats
            )
        
        # Step 2: Use LLM to clean and identify sentence boundaries
        sentences = []
        
        # Process in batches
        for i in range(0, len(rough_segments), self.batch_size):
            batch = rough_segments[i:i + self.batch_size]
            batch_results, batch_errors = self._parse_batch(batch, start_line=i)
            sentences.extend(batch_results)
            errors.extend(batch_errors)
        
        # Update stats
        for s in sentences:
            stats["total"] += 1
            if s.sentence_type == "bullet_point":
                stats["bullets"] += 1
            elif s.sentence_type == "paragraph":
                stats["paragraphs"] += 1
            elif s.sentence_type == "header":
                stats["headers"] += 1
        
        return ParseResult(
            sentences=sentences,
            raw_text=raw_text,
            parse_errors=errors,
            stats=stats
        )
    
    def _preprocess_text(self, text: str) -> List[Tuple[int, str]]:
        """
        Fast regex-based pre-processing to split text into rough segments.
        
        Returns:
            List of (line_number, text) tuples
        """
        segments = []
        
        for line_num, line in enumerate(text.split('\n')):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip very short lines (likely noise)
            if len(line) < 5:
                continue
            
            segments.append((line_num, line))
        
        return segments
    
    def _parse_batch(
        self, 
        segments: List[Tuple[int, str]], 
        start_line: int = 0
    ) -> Tuple[List[ExtractedSentence], List[str]]:
        """
        Use LLM to clean a batch of text segments.
        
        Returns:
            Tuple of (sentences, errors)
        """
        if not segments:
            return [], []
        
        # Build prompt
        prompt = """You are cleaning resume text. For each line:
1. Fix any OCR errors or typos you can detect
2. Identify the type: bullet_point, paragraph, list_item, or header
3. Clean up formatting (remove stray characters, fix spacing)
4. Rate your confidence (0.0-1.0) that the text is correctly extracted

Return ONLY a JSON array with one object per line:
[{"text": "cleaned text", "type": "bullet_point", "confidence": 0.9}, ...]

Skip lines that are:
- Just headers/section titles (unless meaningful)
- Contact info (email, phone, address)
- Dates alone
- Page numbers

Lines to process:
"""
        for i, (line_num, text) in enumerate(segments):
            prompt += f"\n{i+1}. {text}"
        
        prompt += "\n\nJSON array:"
        
        # Call LLM
        response = self._call_llm(prompt)
        
        if response.startswith("LLM_ERROR:"):
            # Fallback: return segments as-is with low confidence
            fallback = [
                ExtractedSentence(
                    text=text,
                    original_text=text,
                    sentence_type="unknown",
                    source_line=line_num,
                    confidence=0.5
                )
                for line_num, text in segments
            ]
            return fallback, [response]
        
        # Parse JSON response
        sentences = []
        errors = []
        
        try:
            # Find JSON array in response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                
                for i, item in enumerate(parsed):
                    if i < len(segments):
                        line_num, original = segments[i]
                        sentences.append(ExtractedSentence(
                            text=item.get("text", original),
                            original_text=original,
                            sentence_type=item.get("type", "unknown"),
                            source_line=line_num,
                            confidence=float(item.get("confidence", 0.7))
                        ))
            else:
                errors.append("No JSON array found in LLM response")
                # Fallback
                for line_num, text in segments:
                    sentences.append(ExtractedSentence(
                        text=text,
                        original_text=text,
                        sentence_type="unknown",
                        source_line=line_num,
                        confidence=0.5
                    ))
                    
        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {e}")
            # Fallback
            for line_num, text in segments:
                sentences.append(ExtractedSentence(
                    text=text,
                    original_text=text,
                    sentence_type="unknown",
                    source_line=line_num,
                    confidence=0.5
                ))
        
        return sentences, errors
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API"""
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1  # Low temperature for consistent parsing
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=60)
            
            if response.status_code != 200:
                return f"LLM_ERROR: HTTP {response.status_code}"
            
            result = response.json()
            
            if 'error' in result:
                return f"LLM_ERROR: {result['error']}"
            
            return result.get('response', '')
            
        except requests.exceptions.Timeout:
            return "LLM_ERROR: Request timed out"
        except requests.exceptions.ConnectionError:
            return "LLM_ERROR: Connection refused - is Ollama running?"
        except Exception as e:
            return f"LLM_ERROR: {type(e).__name__}: {str(e)}"
    
    def parse_single(self, text: str) -> ExtractedSentence:
        """Parse a single line of text (for re-parsing after edits)"""
        prompt = f"""Clean this resume text line:
1. Fix any typos or OCR errors
2. Identify type: bullet_point, paragraph, list_item, or header
3. Rate confidence (0.0-1.0)

Line: {text}

Return JSON: {{"text": "cleaned", "type": "...", "confidence": 0.9}}"""
        
        response = self._call_llm(prompt)
        
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return ExtractedSentence(
                    text=parsed.get("text", text),
                    original_text=text,
                    sentence_type=parsed.get("type", "unknown"),
                    source_line=0,
                    confidence=float(parsed.get("confidence", 0.7))
                )
        except:
            pass
        
        return ExtractedSentence(
            text=text,
            original_text=text,
            sentence_type="unknown",
            source_line=0,
            confidence=0.5
        )


def load_parser_from_config() -> SentenceParser:
    """Create SentenceParser using config.yaml settings"""
    import yaml
    
    config_path = Path(__file__).parent.parent / 'config.yaml'
    
    model = "llama3.2:1b"  # Default
    base_url = "http://localhost:11434"
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            models = config.get('models', {})
            model = models.get('parsing_model', model)
            base_url = models.get('ollama_url', base_url)
    except:
        pass
    
    return SentenceParser(model=model, base_url=base_url)
