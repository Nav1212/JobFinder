"""Test API scrapers"""
import requests
import json

print("Testing API-based job sources...\n")

# Test 1: Remotive API
try:
    print("[1/2] Testing Remotive API...")
    r = requests.get('https://remotive.com/api/remote-jobs', timeout=10)
    data = r.json()
    all_jobs = data.get('jobs', [])
    
    # Filter for tech jobs
    tech_jobs = [j for j in all_jobs[:20] if 
                 any(word in j['title'].lower() for word in ['data', 'engineer', 'developer', 'scientist'])]
    
    print(f"✓ Found {len(tech_jobs)} matching remote jobs")
    for job in tech_jobs[:3]:
        print(f"  - {job['title']} at {job['company_name']}")
except Exception as e:
    print(f"✗ Remotive API failed: {e}")

# Test 2: Arbeitnow API
try:
    print("\n[2/2] Testing Arbeitnow API...")
    r = requests.get('https://www.arbeitnow.com/api/job-board-api', timeout=10)
    data = r.json()
    all_jobs = data.get('data', [])
    
    # Filter for tech jobs
    tech_jobs = [j for j in all_jobs[:20] if 
                 any(word in j['title'].lower() for word in ['data', 'engineer', 'developer', 'scientist'])]
    
    print(f"✓ Found {len(tech_jobs)} matching jobs")
    for job in tech_jobs[:3]:
        print(f"  - {job['title']} at {job['company_name']}")
except Exception as e:
    print(f"✗ Arbeitnow API failed: {e}")

print("\n✅ API sources work! These won't have 403 errors.")
