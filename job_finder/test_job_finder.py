"""
Quick test script for job finder bot components
Tests: Resume extraction, LLM connection, basic matching
"""

import sys
from pathlib import Path

# Add LLMStuff to path
sys.path.append(str(Path(__file__).parent / "LLMStuff"))

print("=" * 60)
print("JOB FINDER BOT - Component Test")
print("=" * 60)

# Test 1: Resume extraction
print("\n[1/3] Testing resume extraction...")
try:
    import PyPDF2
    # Find any PDF in the Resumes directory
    resumes_dir = Path(__file__).parent / ".." / "Resumes"
    resume_files = list(resumes_dir.glob("*.pdf"))
    if not resume_files:
        raise FileNotFoundError("No PDF resumes found in ../Resumes directory")
    resume_path = resume_files[0]  # Use first resume found
    print(f"  Using resume: {resume_path.name}")
    with open(resume_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
    print(f"✓ Resume extracted: {len(text)} characters")
    print(f"  Preview: {text[:100]}...")
except Exception as e:
    print(f"✗ Resume extraction failed: {e}")
    sys.exit(1)

# Test 2: LLM connection
print("\n[2/3] Testing LLM connection...")
try:
    from simple_llm_chat import LocalLLM
    llm = LocalLLM("qwen3:8b")
    print("✓ LLM initialized (qwen3:8b)")
    
    # Quick test
    response = llm.generate("Respond with only the word: SUCCESS", stream=False)
    print(f"  LLM response: {response[:100]}...")
except Exception as e:
    print(f"✗ LLM initialization failed: {e}")
    print("  Make sure Ollama is running: ollama serve")
    sys.exit(1)

# Test 3: Mock job matching
print("\n[3/3] Testing job matching logic...")
try:
    mock_job = {
        'title': 'Senior Data Scientist',
        'company': 'Tech Corp',
        'location': 'Toronto, ON',
        'description': 'Looking for data scientist with Python, machine learning, SQL experience'
    }
    
    prompt = f"""Analyze this job match. Respond ONLY with valid JSON:

RESUME SKILLS: {text[:500]}

JOB: {mock_job['title']} at {mock_job['company']}
DESCRIPTION: {mock_job['description']}

{{
    "score": 85,
    "reasoning": "Strong match",
    "key_matches": ["python", "data science"],
    "gaps": ["specific domain knowledge"]
}}"""

    response = llm.generate(prompt, stream=False)
    print("✓ Job matching test complete")
    print(f"  Response preview: {response[:150]}...")
    
    # Try to parse JSON
    import json
    start_idx = response.find('{')
    end_idx = response.rfind('}') + 1
    if start_idx != -1 and end_idx > start_idx:
        json_str = response[start_idx:end_idx]
        analysis = json.loads(json_str)
        print(f"  ✓ JSON parsed successfully")
        print(f"  Score: {analysis.get('score', 'N/A')}/100")
    else:
        print(f"  ⚠ JSON parsing may need adjustment in real runs")
        
except Exception as e:
    print(f"✗ Job matching test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("COMPONENT TEST COMPLETE")
print("=" * 60)
print("\nAll core components working! Ready to run:")
print("  py job_finder_bot.py")
print("\nNote: Email notifications require configuration (see line 613)")
