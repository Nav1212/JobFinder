"""
Simple Implementations of Abstract Classes for Testing

These are lightweight implementations that don't require LLMs,
suitable for unit testing the pipeline architecture.
"""

import re
from typing import List, Dict, Tuple, Optional, Any
from difflib import SequenceMatcher

from .abstracts import (
    IdealCandidateGenerator, UnbiasedRetriever, GapAnalyzer, IterativeGenerator,
    IdealCandidateProfile, IdealRequirement, RetrievedSkill, GapAnalysis,
    GradingFramework, GradingCriterion, OptimizationResult, MatchResult,
    MatchStrength, SkillCategory
)


class SimpleIdealGenerator(IdealCandidateGenerator):
    """
    Simple keyword-based ideal candidate generator.
    Extracts requirements from job description without LLM.
    """
    
    # Common variations of terms (for testing semantic matching)
    SYNONYMS = {
        "python": ["python", "py", "python3"],
        "javascript": ["javascript", "js", "ecmascript"],
        "machine learning": ["machine learning", "ml", "deep learning", "tensorflow", "neural"],
        "data analysis": ["data analysis", "analytics", "data analytics", "analyzed"],
        "api": ["api", "rest api", "restful", "web services", "rest"],
        "database": ["database", "sql", "db", "data storage", "nosql", "postgresql"],
        "cloud": ["cloud", "aws", "azure", "gcp", "cloud computing"],
        "leadership": ["leadership", "lead", "managing", "team lead"],
        "communication": ["communication", "communicating", "interpersonal"],
        "problem solving": ["problem solving", "troubleshooting", "debugging"],
        "react": ["react", "reactjs", "react.js"],
        "css": ["css", "styling", "stylesheets"],
        "ux": ["ux", "user experience", "user interface", "ui"],
        "kubernetes": ["kubernetes", "k8s", "container orchestration"],
        "docker": ["docker", "containerization", "containers"],
        "graphql": ["graphql", "graph ql"],
        "microservices": ["microservices", "micro-services", "service oriented"],
        "blockchain": ["blockchain", "distributed ledger", "crypto"],
        "swift": ["swift", "ios development"],
        "ios": ["ios", "iphone", "apple mobile"],
    }
    
    def generate_ideal(self, job_description: str) -> IdealCandidateProfile:
        """Extract requirements from job description text"""
        keywords = self.extract_keywords(job_description)
        
        requirements = []
        for i, kw in enumerate(keywords):
            # Priority decreases with order (first mentioned = more important)
            priority = 1.0 - (i * 0.1) if i < 10 else 0.1
            
            req = IdealRequirement(
                description=f"Proficiency in {kw}",
                category=self._guess_category(kw),
                priority=max(0.1, priority),
                keywords=[kw] + self._get_synonyms(kw),
                context=job_description
            )
            requirements.append(req)
        
        return IdealCandidateProfile(
            requirements=requirements,
            role_summary=self._extract_role_summary(job_description),
            experience_level=self._extract_experience_level(job_description),
            industry_context="technology",
            source_job_description=job_description
        )
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text using simple patterns"""
        text_lower = text.lower()
        found = []
        
        # First, check for multi-word known terms (more specific)
        multi_word_terms = [base for base in self.SYNONYMS.keys() if ' ' in base]
        for term in multi_word_terms:
            if term in text_lower:
                found.append(term)
        
        # Then check single-word known terms
        for base, variants in self.SYNONYMS.items():
            if ' ' in base:
                continue  # Already handled
            for variant in variants:
                if variant in text_lower and base not in found:
                    found.append(base)
                    break
        
        # Extract terms after specific patterns
        patterns = [
            r'experience (?:with|in) (\w+)',
            r'knowledge of (\w+)',
            r'proficient in (\w+)',
            r'skilled in (\w+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if match not in found and len(match) > 3:
                    found.append(match)
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for kw in found:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        
        return unique[:20]  # Limit to top 20
    
    def _get_synonyms(self, term: str) -> List[str]:
        """Get synonyms for a term"""
        term_lower = term.lower()
        for base, variants in self.SYNONYMS.items():
            if term_lower in variants or term_lower == base:
                return variants
        return []
    
    def _guess_category(self, keyword: str) -> SkillCategory:
        """Guess category based on keyword"""
        technical = ['python', 'javascript', 'java', 'sql', 'api', 'database', 'cloud', 'aws', 'react', 'node']
        soft = ['leadership', 'communication', 'teamwork', 'problem solving', 'analytical']
        
        kw_lower = keyword.lower()
        if any(t in kw_lower for t in technical):
            return SkillCategory.TECHNICAL
        elif any(s in kw_lower for s in soft):
            return SkillCategory.SOFT_SKILL
        return SkillCategory.TECHNICAL
    
    def _extract_role_summary(self, text: str) -> str:
        """Extract first sentence as role summary"""
        sentences = text.split('.')
        return sentences[0].strip() if sentences else "Role"
    
    def _extract_experience_level(self, text: str) -> str:
        """Guess experience level from text"""
        text_lower = text.lower()
        if 'senior' in text_lower or '5+ years' in text_lower:
            return 'senior'
        elif 'junior' in text_lower or 'entry' in text_lower:
            return 'junior'
        return 'mid-level'


class SimpleRetriever(UnbiasedRetriever):
    """
    Simple retriever that returns all skills without bias.
    Does basic filtering but no scoring/ranking.
    """
    
    def retrieve_all(
        self, 
        user_skills: List[Dict],
        job_context: str
    ) -> List[RetrievedSkill]:
        """Return all user skills as RetrievedSkill objects"""
        retrieved = []
        
        for i, skill_data in enumerate(user_skills):
            # Handle both dict and string inputs
            if isinstance(skill_data, str):
                text = skill_data
                category = self.categorize_skill(text)
                metadata = {}
            else:
                text = skill_data.get('text', skill_data.get('sentence', str(skill_data)))
                category = skill_data.get('category', self.categorize_skill(text))
                if isinstance(category, str):
                    try:
                        category = SkillCategory(category)
                    except ValueError:
                        category = SkillCategory.TECHNICAL
                metadata = {k: v for k, v in skill_data.items() if k not in ['text', 'sentence', 'category']}
            
            retrieved.append(RetrievedSkill(
                text=text,
                category=category,
                source_id=f"skill_{i}",
                metadata=metadata
            ))
        
        return retrieved
    
    def categorize_skill(self, skill_text: str) -> SkillCategory:
        """Simple keyword-based categorization"""
        text_lower = skill_text.lower()
        
        if any(w in text_lower for w in ['led', 'managed', 'supervised', 'team']):
            return SkillCategory.EXPERIENCE
        elif any(w in text_lower for w in ['built', 'developed', 'created', 'implemented']):
            return SkillCategory.PROJECT
        elif any(w in text_lower for w in ['certified', 'certification', 'degree']):
            return SkillCategory.CERTIFICATION
        elif any(w in text_lower for w in ['communication', 'leadership', 'collaboration']):
            return SkillCategory.SOFT_SKILL
        else:
            return SkillCategory.TECHNICAL


class SimpleGapAnalyzer(GapAnalyzer):
    """
    Simple gap analyzer using string similarity.
    No LLM required - uses fuzzy matching.
    """
    
    def __init__(self, match_threshold: float = 0.4):
        self.match_threshold = match_threshold
    
    def analyze(
        self, 
        ideal: IdealCandidateProfile, 
        retrieved: List[RetrievedSkill]
    ) -> GapAnalysis:
        """Compare ideal requirements against retrieved skills"""
        matches = []
        gaps = []
        
        for req in ideal.requirements:
            best_match = None
            best_strength = MatchStrength.NONE
            best_explanation = ""
            
            for skill in retrieved:
                strength, explanation = self.calculate_match_strength(req, skill)
                
                if strength.value < best_strength.value or best_match is None:
                    # Lower enum value = better match
                    if strength != MatchStrength.NONE:
                        best_match = skill
                        best_strength = strength
                        best_explanation = explanation
            
            result = MatchResult(
                requirement=req,
                user_skill=best_match,
                strength=best_strength,
                explanation=best_explanation
            )
            
            if best_strength == MatchStrength.NONE:
                gaps.append(result)
            else:
                matches.append(result)
        
        redundancies = self.detect_redundancies(retrieved)
        
        return GapAnalysis(
            matches=matches,
            gaps=gaps,
            redundancies=redundancies
        )
    
    def calculate_match_strength(
        self,
        requirement: IdealRequirement,
        skill: RetrievedSkill
    ) -> Tuple[MatchStrength, str]:
        """Calculate match using keyword overlap and string similarity"""
        skill_lower = skill.text.lower()
        req_keywords = [kw.lower() for kw in requirement.keywords]
        
        # Check for exact keyword match
        exact_matches = [kw for kw in req_keywords if kw in skill_lower]
        if exact_matches:
            if len(exact_matches) >= 2:
                return MatchStrength.EXACT, f"Contains keywords: {', '.join(exact_matches)}"
            else:
                return MatchStrength.STRONG, f"Contains keyword: {exact_matches[0]}"
        
        # Check if requirement description words appear in skill
        req_words = set(requirement.description.lower().split())
        skill_words = set(skill_lower.split())
        common_words = req_words & skill_words
        # Filter out common stop words
        stop_words = {'in', 'the', 'a', 'an', 'and', 'or', 'for', 'with', 'to', 'of'}
        meaningful_common = common_words - stop_words
        
        if len(meaningful_common) >= 2:
            return MatchStrength.PARTIAL, f"Common words: {', '.join(meaningful_common)}"
        
        return MatchStrength.NONE, "No match found"
    
    def detect_redundancies(
        self,
        skills: List[RetrievedSkill]
    ) -> List[Tuple[RetrievedSkill, RetrievedSkill, str]]:
        """Find skills that are too similar to each other"""
        redundancies = []
        
        for i, skill1 in enumerate(skills):
            for skill2 in skills[i+1:]:
                # Word-based similarity
                words1 = set(skill1.text.lower().split())
                words2 = set(skill2.text.lower().split())
                stop_words = {'in', 'the', 'a', 'an', 'and', 'or', 'for', 'with', 'to', 'of', 'using', 'built', 'developed'}
                words1 = words1 - stop_words
                words2 = words2 - stop_words
                
                if not words1 or not words2:
                    continue
                
                overlap = len(words1 & words2)
                union = len(words1 | words2)
                jaccard = overlap / union if union > 0 else 0
                
                if jaccard > 0.5:
                    redundancies.append((
                        skill1, 
                        skill2, 
                        f"High word overlap ({jaccard:.0%})"
                    ))
        
        return redundancies
    
    def create_grading_framework(
        self, 
        ideal: IdealCandidateProfile,
        gap_analysis: GapAnalysis
    ) -> GradingFramework:
        """Create grading framework from gap analysis"""
        criteria = []
        
        # Add matched requirements as satisfied criteria
        for match in gap_analysis.matches:
            criteria.append(GradingCriterion(
                name=match.requirement.keywords[0] if match.requirement.keywords else "skill",
                weight=match.requirement.priority,
                description=match.requirement.description,
                satisfied_by=match.user_skill,
                is_gap=False
            ))
        
        # Add gaps as unsatisfied criteria
        for gap in gap_analysis.gaps:
            criteria.append(GradingCriterion(
                name=gap.requirement.keywords[0] if gap.requirement.keywords else "skill",
                weight=gap.requirement.priority,
                description=gap.requirement.description,
                satisfied_by=None,
                is_gap=True
            ))
        
        return GradingFramework(
            criteria=criteria,
            gap_analysis=gap_analysis,
            ideal_reference=ideal
        )


class SimpleIterativeGenerator(IterativeGenerator):
    """
    Simple generator that assembles resume from matched skills.
    No LLM - just concatenates relevant skills.
    """
    
    def generate(
        self,
        retrieved_skills: List[RetrievedSkill],
        grading_framework: GradingFramework,
        max_iterations: int = 5
    ) -> OptimizationResult:
        """Generate resume by selecting non-redundant matched skills"""
        
        # Get matched skills (avoid redundancies)
        used_skills = set()
        resume_parts = []
        matches_report = []
        gaps_report = []
        redundancies_removed = []
        
        # Add satisfied criteria
        for criterion in grading_framework.criteria:
            if not criterion.is_gap and criterion.satisfied_by:
                skill = criterion.satisfied_by
                if skill.text not in used_skills:
                    used_skills.add(skill.text)
                    resume_parts.append(f"• {skill.text}")
                    matches_report.append({
                        "requirement": criterion.name,
                        "matched_by": skill.text,
                        "strength": "matched"
                    })
                else:
                    redundancies_removed.append(skill.text)
            elif criterion.is_gap:
                gaps_report.append({
                    "requirement": criterion.name,
                    "description": criterion.description,
                    "weight": criterion.weight
                })
        
        # Build resume text
        resume_text = "PROFESSIONAL EXPERIENCE\n\n" + "\n".join(resume_parts)
        
        # Calculate final score
        final_score = grading_framework.get_score()
        
        return OptimizationResult(
            optimized_resume=resume_text,
            matches_report=matches_report,
            gaps_report=gaps_report,
            redundancies_removed=redundancies_removed,
            iterations_used=1,  # Simple generator doesn't iterate
            final_score=final_score
        )
    
    def score_iteration(
        self,
        current_resume: str,
        grading_framework: GradingFramework
    ) -> float:
        """Score resume against grading framework"""
        # Simple: count how many criteria keywords appear in resume
        resume_lower = current_resume.lower()
        matched = 0
        total_weight = 0
        
        for criterion in grading_framework.criteria:
            total_weight += criterion.weight
            if criterion.name.lower() in resume_lower:
                matched += criterion.weight
        
        return matched / total_weight if total_weight > 0 else 0.0
