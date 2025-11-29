"""
Job Finder Bot - Automated job search with LLM-based resume matching
Scrapes multiple job boards and sends email notifications for high-match opportunities
ASYNC VERSION - Uses threading for parallel API calls and LLM analysis
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import html
import re
from database import DatabaseManager

# Add LLMStuff to path for LocalLLM import
import os
llm_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LLMStuff")
sys.path.append(llm_path)
from simple_llm_chat import LocalLLM

try:
    import PyPDF2
except ImportError:
    print("PyPDF2 not installed. Install with: pip install PyPDF2")
    sys.exit(1)


class JobFinder:
    def __init__(self, resume_path, email_config=None, db_path=None):
        """
        Initialize job finder with resume and optional email configuration
        
        Args:
            resume_path: Path to PDF resume file
            email_config: Dict with 'sender', 'password', 'recipient' for Gmail SMTP
            db_path: Path to database file (optional, defaults to jobs_database.db)
        """
        self.resume_path = resume_path
        self.email_config = email_config
        self.resume_text = self.extract_resume_text(resume_path)
        
        # Initialize Database
        self.db = DatabaseManager(db_path if db_path else "jobs_database.db")
        
        # Initialize LLM for job matching
        try:
            self.llm = LocalLLM("qwen2.5:3b")
            print("✓ LLM initialized (qwen2.5:3b)")
        except Exception as e:
            print(f"Warning: Could not initialize LLM: {e}")
            print("Make sure Ollama is running: ollama serve")
            self.llm = None
        
        # Results storage
        self.jobs_found = []
        self.high_matches = []
        self.jobs_lock = threading.Lock()
        self.high_matches_lock = threading.Lock()
        
        # Job queue for async processing
        self.job_queue = queue.Queue()
        self.analysis_complete = threading.Event()
        
        # Deduplication tracking (avoid analyzing same job twice)
        self.seen_jobs = set()
        self.seen_jobs_lock = threading.Lock()
        
        # Session for better scraping
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'DNT': '1'
        })
        
        # Initialize Playwright scraper for blocked sites (lazy load)
        self.playwright_scraper = None
        
        # Extract email from resume
        self.resume_email = self.extract_email_from_resume()
        
        # Update email_config recipient with extracted email (for auto mode)
        if self.email_config and not self.email_config.get('recipient'):
            self.email_config['recipient'] = self.resume_email
            if self.resume_email:
                print(f"✓ Email recipient set to: {self.resume_email}")
        
        # Register resume in database
        resume_name = Path(resume_path).stem
        self.resume_id = self.db.get_or_create_resume(
            resume_name, 
            self.resume_email, 
            str(resume_path), 
            self.resume_text
        )
        
        # Load job sources from config file
        self.job_sources = self._load_job_sources()
        
        # North America location keywords for filtering
        self.north_america_keywords = [
            'canada', 'canadian', 'ontario', 'quebec', 'british columbia', 'alberta', 'toronto', 'vancouver', 'montreal', 'calgary', 'ottawa',
            'united states', 'usa', 'us', 'america', 'american', 'california', 'new york', 'texas', 'florida', 'washington',
            'san francisco', 'los angeles', 'chicago', 'boston', 'seattle', 'austin', 'dallas', 'houston', 'denver', 'portland',
            'mexico', 'mexican', 'mexico city', 'guadalajara', 'monterrey',
            'remote', 'remote (us)', 'remote (canada)', 'remote (north america)', 'anywhere'
        ]
    
    def _load_job_sources(self):
        """Load job sources from config file"""
        config_file = Path(__file__).parent / 'job_sources.json'
        
        if not config_file.exists():
            print(f"⚠ Config file not found: {config_file}")
            return {'api_sources': [], 'playwright_sources': [], 'scraping_sources': []}
        
        try:
            with open(config_file, 'r') as f:
                sources = json.load(f)
            
            enabled_apis = [s for s in sources.get('api_sources', []) if s.get('enabled', False)]
            enabled_playwright = [s for s in sources.get('playwright_sources', []) if s.get('enabled', False)]
            enabled_scraping = [s for s in sources.get('scraping_sources', []) if s.get('enabled', False)]
            
            print(f"✓ Loaded {len(enabled_apis)} API sources, {len(enabled_playwright)} Playwright sources, {len(enabled_scraping)} scraping sources")
            
            return sources
        except Exception as e:
            print(f"⚠ Error loading job sources config: {e}")
            return {'api_sources': [], 'playwright_sources': [], 'scraping_sources': []}
        
    def extract_email_from_resume(self):
        """Extract email address from resume text using regex"""
        if not self.resume_text:
            return None
        
        # Common email regex pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, self.resume_text)
        
        if matches:
            email = matches[0]  # Take first email found
            print(f"✓ Extracted email from resume: {email}")
            return email
        else:
            print("⚠ No email found in resume")
            return None
    
    def _is_north_america(self, location):
        """Check if job location is in North America"""
        if not location:
            return False
        
        location_lower = location.lower()
        
        # Check if any North America keyword is in the location
        return any(keyword in location_lower for keyword in self.north_america_keywords)
    
    def _queue_job_if_valid(self, job):
        """Add job to queue only if it's in North America"""
        if self._is_north_america(job.get('location', '')):
            self.job_queue.put(job)
            return True
        return False
        
    def extract_resume_text(self, pdf_path):
        """Extract text from PDF resume"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                print(f"✓ Extracted resume text ({len(text)} characters)")
                return text
        except Exception as e:
            print(f"Error reading resume PDF: {e}")
            return ""
    
    def scrape_indeed(self, search_term, location, country='ca'):
        """Scrape Indeed job listings"""
        jobs = []
        domain = 'indeed.ca' if country == 'ca' else 'indeed.com'
        
        # Indeed URL format
        url = f"https://{domain}/jobs"
        params = {
            'q': search_term,
            'l': location,
            'fromage': '7'  # Last 7 days
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        try:
            print(f"  Scraping Indeed ({domain})...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 403:
                print(f"    ⚠ Indeed blocked request (403) - site requires browser. Skipping.")
                return jobs
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Indeed job cards (structure may vary)
            job_cards = soup.find_all('div', class_='job_seen_beacon')
            
            for card in job_cards[:20]:  # Limit to 20 per search
                try:
                    title_elem = card.find('h2', class_='jobTitle')
                    company_elem = card.find('span', {'data-testid': 'company-name'})
                    location_elem = card.find('div', {'data-testid': 'text-location'})
                    snippet_elem = card.find('div', class_='job-snippet')
                    
                    if title_elem and company_elem:
                        # Extract job link
                        link_elem = title_elem.find('a')
                        job_id = link_elem.get('data-jk', '') if link_elem else ''
                        job_url = f"https://{domain}/viewjob?jk={job_id}" if job_id else ''
                        
                        jobs.append({
                            'title': title_elem.get_text(strip=True),
                            'company': company_elem.get_text(strip=True),
                            'location': location_elem.get_text(strip=True) if location_elem else location,
                            'description': snippet_elem.get_text(strip=True) if snippet_elem else '',
                            'url': job_url,
                            'source': f'Indeed {country.upper()}',
                            'scraped_at': datetime.now().isoformat()
                        })
                except Exception as e:
                    continue
            
            print(f"    Found {len(jobs)} jobs")
            
        except Exception as e:
            print(f"    Error scraping Indeed: {e}")
        
        return jobs
    
    def scrape_linkedin(self, search_term, location):
        """Scrape LinkedIn job listings"""
        jobs = []
        
        # LinkedIn job search URL
        url = "https://www.linkedin.com/jobs/search"
        params = {
            'keywords': search_term,
            'location': location,
            'f_TPR': 'r604800'  # Past week
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        try:
            print(f"  Scraping LinkedIn...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 403:
                print(f"    ⚠ LinkedIn blocked request (403) - may require login. Skipping.")
                return jobs
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # LinkedIn job cards
            job_cards = soup.find_all('div', class_='base-card')
            
            for card in job_cards[:20]:
                try:
                    title_elem = card.find('h3', class_='base-search-card__title')
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    link_elem = card.find('a', class_='base-card__full-link')
                    
                    if title_elem and company_elem:
                        jobs.append({
                            'title': title_elem.get_text(strip=True),
                            'company': company_elem.get_text(strip=True),
                            'location': location_elem.get_text(strip=True) if location_elem else location,
                            'description': '',
                            'url': link_elem['href'] if link_elem and 'href' in link_elem.attrs else '',
                            'source': 'LinkedIn',
                            'scraped_at': datetime.now().isoformat()
                        })
                except Exception as e:
                    continue
            
            print(f"    Found {len(jobs)} jobs")
            
        except Exception as e:
            print(f"    Error scraping LinkedIn: {e}")
        
        return jobs
    
    def scrape_glassdoor(self, search_term, location):
        """Scrape Glassdoor job listings"""
        jobs = []
        
        # Glassdoor job search URL
        url = "https://www.glassdoor.com/Job/jobs.htm"
        params = {
            'sc.keyword': search_term,
            'locT': 'C',
            'locId': '1',
            'locKeyword': location,
            'fromAge': 7
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.glassdoor.com/'
        }
        
        try:
            print(f"  Scraping Glassdoor...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 403:
                print(f"    ⚠ Glassdoor blocked request (403) - site requires browser/login. Skipping.")
                return jobs
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Glassdoor job cards
            job_cards = soup.find_all('li', class_='react-job-listing')
            
            for card in job_cards[:20]:
                try:
                    title_elem = card.find('a', class_='jobTitle')
                    company_elem = card.find('div', class_='employerName')
                    location_elem = card.find('div', class_='location')
                    
                    if title_elem and company_elem:
                        jobs.append({
                            'title': title_elem.get_text(strip=True),
                            'company': company_elem.get_text(strip=True),
                            'location': location_elem.get_text(strip=True) if location_elem else location,
                            'description': '',
                            'url': 'https://www.glassdoor.com' + title_elem['href'] if 'href' in title_elem.attrs else '',
                            'source': 'Glassdoor',
                            'scraped_at': datetime.now().isoformat()
                        })
                except Exception as e:
                    continue
            
            print(f"    Found {len(jobs)} jobs")
            
        except Exception as e:
            print(f"    Error scraping Glassdoor: {e}")
        
        return jobs
    
    def scrape_dice(self, search_term, location):
        """Scrape Dice.com job listings (Tech jobs)"""
        jobs = []
        
        # Dice job search URL
        url = "https://www.dice.com/jobs"
        params = {
            'q': search_term,
            'location': location,
            'radius': '30',
            'radiusUnit': 'mi',
            'page': '1',
            'pageSize': '20'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': 'https://www.dice.com/'
        }
        
        try:
            print(f"  Scraping Dice.com...")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 403:
                print(f"    ⚠ Dice blocked request (403) - site requires browser. Skipping.")
                return jobs
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Dice job cards
            job_cards = soup.find_all('div', {'data-cy': 'card-list-item'})
            
            for card in job_cards[:20]:
                try:
                    title_elem = card.find('a', {'data-cy': 'card-title-link'})
                    company_elem = card.find('a', {'data-cy': 'card-company'})
                    location_elem = card.find('span', {'data-cy': 'card-location'})
                    description_elem = card.find('div', {'data-cy': 'card-summary'})
                    
                    if title_elem and company_elem:
                        jobs.append({
                            'title': title_elem.get_text(strip=True),
                            'company': company_elem.get_text(strip=True),
                            'location': location_elem.get_text(strip=True) if location_elem else location,
                            'description': description_elem.get_text(strip=True) if description_elem else '',
                            'url': 'https://www.dice.com' + title_elem['href'] if 'href' in title_elem.attrs else '',
                            'source': 'Dice',
                            'scraped_at': datetime.now().isoformat()
                        })
                except Exception as e:
                    continue
            
            print(f"    Found {len(jobs)} jobs")
            
        except Exception as e:
            print(f"    Error scraping Dice: {e}")
        
        return jobs
    
    def scrape_remotive_api(self, search_term):
        """Scrape Remotive.io API - reliable, no blocking, remote jobs"""
        jobs = []
        
        # Remotive has a free public API
        url = "https://remotive.com/api/remote-jobs"
        
        try:
            print(f"  Fetching from Remotive API (remote jobs)...")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            all_jobs = data.get('jobs', [])
            
            # Filter by search term
            search_lower = search_term.lower()
            for job in all_jobs[:50]:  # Limit to recent 50
                title = job.get('title', '').lower()
                category = job.get('category', '').lower()
                description = job.get('description', '').lower()
                
                # Check if search term matches
                if (search_lower in title or 
                    search_lower in category or
                    any(word in title for word in search_lower.split())):
                    
                    jobs.append({
                        'title': job.get('title', ''),
                        'company': job.get('company_name', ''),
                        'location': 'Remote',
                        'description': job.get('description', '')[:500],  # Truncate long descriptions
                        'url': job.get('url', ''),
                        'source': 'Remotive (Remote Jobs)',
                        'scraped_at': datetime.now().isoformat()
                    })
            
            print(f"    Found {len(jobs)} remote jobs")
            
        except Exception as e:
            print(f"    Error fetching Remotive API: {e}")
        
        return jobs
    
    def scrape_arbeitnow_api(self, search_term):
        """Scrape Arbeitnow API - free, no auth required, tech jobs"""
        jobs = []
        
        url = "https://www.arbeitnow.com/api/job-board-api"
        
        try:
            print(f"  Fetching from Arbeitnow API...")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            all_jobs = data.get('data', [])
            
            # Filter by search term
            search_lower = search_term.lower()
            for job in all_jobs[:50]:
                title = job.get('title', '').lower()
                tags = ' '.join(job.get('tags', [])).lower()
                
                if (search_lower in title or 
                    any(word in title for word in search_lower.split()) or
                    search_lower in tags):
                    
                    jobs.append({
                        'title': job.get('title', ''),
                        'company': job.get('company_name', ''),
                        'location': job.get('location', 'Remote'),
                        'description': job.get('description', '')[:500],
                        'url': job.get('url', ''),
                        'source': 'Arbeitnow',
                        'scraped_at': datetime.now().isoformat()
                    })
            
            print(f"    Found {len(jobs)} jobs")
            
        except Exception as e:
            print(f"    Error fetching Arbeitnow API: {e}")
        
        return jobs
    
    async def fetch_api_async(self, session, url, search_term, source_name):
        """Async API fetcher for concurrent requests - feeds queue directly"""
        jobs = []
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                data = await response.json()
                
                if source_name == 'Remotive':
                    all_jobs = data.get('jobs', [])
                    search_lower = search_term.lower()
                    
                    for job in all_jobs[:50]:
                        title = job.get('title', '').lower()
                        category = job.get('category', '').lower()
                        
                        if (search_lower in title or 
                            search_lower in category or
                            any(word in title for word in search_lower.split())):
                            
                            job_data = {
                                'title': job.get('title', ''),
                                'company': job.get('company_name', ''),
                                'location': 'Remote',
                                'description': job.get('description', '')[:500],
                                'url': job.get('url', ''),
                                'source': 'Remotive (Remote Jobs)',
                                'scraped_at': datetime.now().isoformat()
                            }
                            jobs.append(job_data)
                            # Feed queue immediately if location is North America
                            self._queue_job_if_valid(job_data)
                
                elif source_name == 'Arbeitnow':
                    all_jobs = data.get('data', [])
                    search_lower = search_term.lower()
                    
                    for job in all_jobs[:50]:
                        title = job.get('title', '').lower()
                        tags = ' '.join(job.get('tags', [])).lower()
                        
                        if (search_lower in title or 
                            any(word in title for word in search_lower.split()) or
                            search_lower in tags):
                            
                            job_data = {
                                'title': job.get('title', ''),
                                'company': job.get('company_name', ''),
                                'location': job.get('location', 'Remote'),
                                'description': job.get('description', '')[:500],
                                'url': job.get('url', ''),
                                'source': 'Arbeitnow',
                                'scraped_at': datetime.now().isoformat()
                            }
                            jobs.append(job_data)
                            self._queue_job_if_valid(job_data)
                
                elif source_name == 'RemoteOK':
                    # RemoteOK - Large remote job board, no auth
                    all_jobs = data if isinstance(data, list) else []
                    search_lower = search_term.lower()
                    
                    for job in all_jobs[:50]:
                        if isinstance(job, dict):
                            title = job.get('position', '').lower()
                            tags_list = job.get('tags', [])
                            tags_str = ' '.join(tags_list).lower() if isinstance(tags_list, list) else ''
                            
                            if (search_lower in title or 
                                any(word in title for word in search_lower.split()) or
                                search_lower in tags_str):
                                
                                job_data = {
                                    'title': job.get('position', ''),
                                    'company': job.get('company', ''),
                                    'location': job.get('location', 'Remote'),
                                    'description': job.get('description', '')[:500],
                                    'url': job.get('url', ''),
                                    'source': 'RemoteOK',
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job_data)
                                self._queue_job_if_valid(job_data)
                
                elif source_name == 'Himalayas':
                    # Himalayas.app - Remote jobs, free API
                    all_jobs = data.get('jobs', []) if isinstance(data, dict) else []
                    search_lower = search_term.lower()
                    
                    for job in all_jobs[:50]:
                        title = job.get('title', '').lower()
                        
                        if search_lower in title or any(word in title for word in search_lower.split()):
                            job_data = {
                                'title': job.get('title', ''),
                                'company': job.get('company_name', ''),
                                'location': job.get('location', 'Remote'),
                                'description': job.get('description', '')[:500],
                                'url': job.get('url', ''),
                                'source': 'Himalayas',
                                'scraped_at': datetime.now().isoformat()
                            }
                            jobs.append(job_data)
                            self._queue_job_if_valid(job_data)
                
                elif source_name == 'Microsoft Careers API':
                    # Microsoft Careers API
                    all_jobs = data.get('operationResult', {}).get('result', {}).get('jobs', [])
                    search_lower = search_term.lower()
                    
                    for job in all_jobs[:50]:
                        title = job.get('title', '').lower()
                        
                        if search_lower in title or any(word in title for word in search_lower.split()):
                            job_data = {
                                'title': job.get('title', ''),
                                'company': 'Microsoft',
                                'location': job.get('location', 'See listing'),
                                'description': job.get('descriptionTeaser', '')[:500],
                                'url': f"https://careers.microsoft.com/professionals/us/en/job/{job.get('jobId', '')}",
                                'source': 'Microsoft Careers API',
                                'scraped_at': datetime.now().isoformat()
                            }
                            jobs.append(job_data)
                            self._queue_job_if_valid(job_data)
                
                print(f"  ✓ {source_name}: {len(jobs)} jobs → queue")
                
        except Exception as e:
            print(f"  ✗ {source_name} error: {e}")
        
        return jobs
    
    async def fetch_all_apis_async(self, search_terms):
        """Fetch from all APIs concurrently"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for search_term in search_terms:
                # Remotive API
                tasks.append(self.fetch_api_async(
                    session, 
                    'https://remotive.com/api/remote-jobs',
                    search_term,
                    'Remotive'
                ))
                
                # Arbeitnow API
                tasks.append(self.fetch_api_async(
                    session,
                    'https://www.arbeitnow.com/api/job-board-api',
                    search_term,
                    'Arbeitnow'
                ))
                
                # Findwork.dev API (no auth required)
                tasks.append(self.fetch_api_async(
                    session,
                    'https://findwork.dev/api/jobs/',
                    search_term,
                    'Findwork'
                ))
                
                # DevITjobs API (free, no auth)
                tasks.append(self.fetch_api_async(
                    session,
                    'https://www.devitjobs.com/api/jobs',
                    search_term,
                    'DevITjobs'
                ))
            
            # Run all API calls concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Flatten results
            all_jobs = []
            for result in results:
                if isinstance(result, list):
                    all_jobs.extend(result)
            
            return all_jobs
    
    async def scrape_with_playwright_async(self, url, search_term, location, source_name):
        """
        Scrape job site using Playwright (for sites that block automated requests)
        
        Args:
            url: Base URL to scrape
            search_term: Job search query
            location: Location filter
            source_name: Name of the job site
        """
        try:
            from playwright.async_api import async_playwright
            from bs4 import BeautifulSoup
            
            jobs = []
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set user agent to look like real browser
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                
                # Build URL with query params
                if 'indeed' in url.lower():
                    domain = 'indeed.ca' if 'CA' in source_name else 'indeed.com'
                    full_url = f"https://{domain}/jobs?q={search_term}&l={location}&fromage=7"
                elif 'linkedin' in url.lower():
                    full_url = f"https://www.linkedin.com/jobs/search?keywords={search_term}&location={location}&f_TPR=r604800"
                elif 'glassdoor' in url.lower():
                    full_url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={search_term}&locKeyword={location}&fromAge=7"
                elif 'google' in url.lower() and 'career' in url.lower():
                    # Google Careers
                    full_url = f"https://www.google.com/about/careers/applications/jobs/results/?q={search_term}"
                elif 'microsoft' in url.lower() and 'career' in url.lower():
                    # Microsoft Careers
                    full_url = f"https://careers.microsoft.com/professionals/us/en/search-results?keywords={search_term}"
                elif 'amazon' in url.lower() and 'job' in url.lower():
                    # Amazon Jobs
                    full_url = f"https://www.amazon.jobs/en/search?base_query={search_term}&loc_query={location}"
                else:
                    full_url = url
                
                # Navigate and wait for content
                try:
                    print(f"  Navigating to {source_name}...")
                    await page.goto(full_url, wait_until='domcontentloaded', timeout=60000)
                    
                    # Wait longer for Microsoft's dynamic content
                    if 'microsoft' in source_name.lower():
                        await asyncio.sleep(5)
                    else:
                        await asyncio.sleep(3)
                    
                    print(f"  ✓ {source_name} page loaded")
                except Exception as e:
                    await browser.close()
                    print(f"  ✗ {source_name} Playwright navigation error: {e}")
                    return
                
                # Get HTML
                html = await page.content()
                
                # Debug: Save HTML for Microsoft if no jobs found
                if 'microsoft' in source_name.lower():
                    debug_file = f"debug_microsoft.html"
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(html)
                
                await browser.close()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract jobs based on source
                if 'indeed' in source_name.lower():
                    # Try multiple selectors for Indeed
                    job_cards = (
                        soup.find_all('div', class_='job_seen_beacon') or
                        soup.find_all('div', class_='jobsearch-ResultsList') or
                        soup.find_all('div', attrs={'data-testid': 'job-result'}) or
                        soup.find_all('td', class_='resultContent') or
                        soup.find_all('a', class_='jcs-JobTitle')
                    )
                    domain = 'indeed.ca' if 'CA' in source_name else 'indeed.com'
                    print(f"  Found {len(job_cards)} Indeed job cards")
                    
                    # Debug: Save HTML if no jobs found
                    if len(job_cards) == 0:
                        debug_file = f"debug_indeed_{source_name.replace(' ', '_')}.html"
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            f.write(html)
                        print(f"  📄 Saved HTML to {debug_file} for debugging")
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('h2', class_='jobTitle')
                            company_elem = card.find('span', {'data-testid': 'company-name'})
                            location_elem = card.find('div', {'data-testid': 'text-location'})
                            snippet_elem = card.find('div', class_='job-snippet')
                            
                            if title_elem and company_elem:
                                link_elem = title_elem.find('a')
                                job_id = link_elem.get('data-jk', '') if link_elem else ''
                                job_url = f"https://{domain}/viewjob?jk={job_id}" if job_id else ''
                                
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': company_elem.get_text(strip=True),
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': snippet_elem.get_text(strip=True) if snippet_elem else '',
                                    'url': job_url,
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'linkedin' in source_name.lower():
                    job_cards = soup.find_all('div', class_='base-card')
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('h3', class_='base-search-card__title')
                            company_elem = card.find('h4', class_='base-search-card__subtitle')
                            location_elem = card.find('span', class_='job-search-card__location')
                            link_elem = card.find('a', class_='base-card__full-link')
                            
                            if title_elem and company_elem:
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': company_elem.get_text(strip=True),
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': '',
                                    'url': link_elem['href'] if link_elem and 'href' in link_elem.attrs else '',
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'glassdoor' in source_name.lower():
                    job_cards = soup.find_all('li', class_='react-job-listing')
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('a', class_='jobTitle')
                            company_elem = card.find('div', class_='employerName')
                            location_elem = card.find('div', class_='location')
                            
                            if title_elem and company_elem:
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': company_elem.get_text(strip=True),
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': '',
                                    'url': 'https://www.glassdoor.com' + title_elem['href'] if 'href' in title_elem.attrs else '',
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'google' in source_name.lower():
                    # Google Careers - look for job cards
                    job_cards = soup.find_all('li', class_='lLd3Je') or soup.find_all('div', attrs={'role': 'listitem'})
                    
                    for card in job_cards[:20]:
                        try:
                            # Google uses different structure
                            title_elem = card.find('h3') or card.find('div', class_='KLsYvd')
                            company_elem = card.find('span', string='Google') or card.find('div', class_='Xsxa1e')
                            location_elem = card.find('span', class_='r0wTof') or card.find('div', class_='uqxHd')
                            link_elem = card.find('a')
                            
                            if title_elem:
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': 'Google',
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': '',
                                    'url': 'https://www.google.com' + link_elem['href'] if link_elem and 'href' in link_elem.attrs else '',
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'microsoft' in source_name.lower():
                    # Microsoft Careers - try multiple selectors for their dynamic content
                    # Method 1: Look for job result cards
                    job_cards = (
                        soup.find_all('div', attrs={'data-automation-id': 'jobPostingCard'}) or
                        soup.find_all('li', class_='ms-List-cell') or
                        soup.find_all('div', class_='jobs-search-two-pane__job-card-container') or
                        soup.find_all('article') or
                        soup.find_all('div', class_='ms-Stack')
                    )
                    
                    print(f"  Found {len(job_cards)} Microsoft job cards")
                    
                    for card in job_cards[:20]:
                        try:
                            # Try multiple selectors
                            title_elem = (
                                card.find('h2') or 
                                card.find('h3') or
                                card.find('a', attrs={'data-automation-id': 'jobTitle'}) or
                                card.find('span', class_='job-title')
                            )
                            
                            location_elem = (
                                card.find('span', attrs={'data-automation-id': 'jobLocation'}) or
                                card.find('div', class_='location') or
                                card.find('span', class_='job-location')
                            )
                            
                            link_elem = card.find('a')
                            
                            if title_elem:
                                job_url = ''
                                if link_elem and 'href' in link_elem.attrs:
                                    job_url = link_elem['href']
                                    if not job_url.startswith('http'):
                                        job_url = 'https://careers.microsoft.com' + job_url
                                
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': 'Microsoft',
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': '',
                                    'url': job_url,
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'amazon' in source_name.lower():
                    # Amazon Jobs
                    job_cards = soup.find_all('div', class_='job') or soup.find_all('div', class_='job-tile')
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('h3', class_='job-title') or card.find('a', class_='job-link')
                            location_elem = card.find('span', class_='location-and-id') or card.find('div', class_='location')
                            link_elem = card.find('a')
                            
                            if title_elem:
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': 'Amazon',
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': '',
                                    'url': link_elem['href'] if link_elem and 'href' in link_elem.attrs else '',
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                # Ensure full URL
                                if job['url'] and not job['url'].startswith('http'):
                                    job['url'] = 'https://www.amazon.jobs' + job['url']
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                if jobs:
                    print(f"  ✓ {source_name} (Playwright): {len(jobs)} jobs → queue")
                else:
                    print(f"  ⚠ {source_name} (Playwright): No jobs found (may be blocked or wrong selectors)")
                    
        except Exception as e:
            print(f"  ✗ {source_name} Playwright error: {e}")
    
    async def scrape_website_async(self, session, url, params, search_term, location, source_name):
        """Async web scraper for job sites - feeds queue directly"""
        jobs = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'DNT': '1'
        }
        
        try:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 403:
                    print(f"  ⚠ {source_name} blocked (403)")
                    return
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Parse based on source
                if 'indeed' in source_name.lower():
                    job_cards = soup.find_all('div', class_='job_seen_beacon')
                    domain = 'indeed.ca' if 'CA' in source_name else 'indeed.com'
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('h2', class_='jobTitle')
                            company_elem = card.find('span', {'data-testid': 'company-name'})
                            location_elem = card.find('div', {'data-testid': 'text-location'})
                            snippet_elem = card.find('div', class_='job-snippet')
                            
                            if title_elem and company_elem:
                                link_elem = title_elem.find('a')
                                job_id = link_elem.get('data-jk', '') if link_elem else ''
                                job_url = f"https://{domain}/viewjob?jk={job_id}" if job_id else ''
                                
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': company_elem.get_text(strip=True),
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': snippet_elem.get_text(strip=True) if snippet_elem else '',
                                    'url': job_url,
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                # Feed queue immediately
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'linkedin' in source_name.lower():
                    job_cards = soup.find_all('div', class_='base-card')
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('h3', class_='base-search-card__title')
                            company_elem = card.find('h4', class_='base-search-card__subtitle')
                            location_elem = card.find('span', class_='job-search-card__location')
                            link_elem = card.find('a', class_='base-card__full-link')
                            
                            if title_elem and company_elem:
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': company_elem.get_text(strip=True),
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': '',
                                    'url': link_elem['href'] if link_elem and 'href' in link_elem.attrs else '',
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'glassdoor' in source_name.lower():
                    job_cards = soup.find_all('li', class_='react-job-listing')
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('a', class_='jobTitle')
                            company_elem = card.find('div', class_='employerName')
                            location_elem = card.find('div', class_='location')
                            
                            if title_elem and company_elem:
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': company_elem.get_text(strip=True),
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': '',
                                    'url': 'https://www.glassdoor.com' + title_elem['href'] if 'href' in title_elem.attrs else '',
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                elif 'dice' in source_name.lower():
                    job_cards = soup.find_all('div', {'data-cy': 'card-list-item'})
                    
                    for card in job_cards[:20]:
                        try:
                            title_elem = card.find('a', {'data-cy': 'card-title-link'})
                            company_elem = card.find('a', {'data-cy': 'card-company'})
                            location_elem = card.find('span', {'data-cy': 'card-location'})
                            description_elem = card.find('div', {'data-cy': 'card-summary'})
                            
                            if title_elem and company_elem:
                                job = {
                                    'title': title_elem.get_text(strip=True),
                                    'company': company_elem.get_text(strip=True),
                                    'location': location_elem.get_text(strip=True) if location_elem else location,
                                    'description': description_elem.get_text(strip=True) if description_elem else '',
                                    'url': 'https://www.dice.com' + title_elem['href'] if 'href' in title_elem.attrs else '',
                                    'source': source_name,
                                    'scraped_at': datetime.now().isoformat()
                                }
                                jobs.append(job)
                                self._queue_job_if_valid(job)
                        except:
                            continue
                
                if jobs:
                    print(f"  ✓ {source_name}: {len(jobs)} jobs → queue")
                
        except asyncio.TimeoutError:
            print(f"  ✗ {source_name} timeout")
        except Exception as e:
            print(f"  ✗ {source_name} error: {type(e).__name__}")
    
    async def scrape_all_websites_async(self, search_terms, locations, countries):
        """Scrape all job sites concurrently - jobs fed to queue in real-time"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for search_term in search_terms:
                for location in locations:
                    # Indeed CA - DISABLED (403 blocked)
                    # if 'ca' in countries:
                    #     tasks.append(self.scrape_website_async(
                    #         session,
                    #         'https://indeed.ca/jobs',
                    #         {'q': search_term, 'l': location, 'fromage': '7'},
                    #         search_term,
                    #         location,
                    #         'Indeed CA'
                    #     ))
                    
                    # Indeed US - DISABLED (403 blocked)
                    # if 'us' in countries:
                    #     tasks.append(self.scrape_website_async(
                    #         session,
                    #         'https://indeed.com/jobs',
                    #         {'q': search_term, 'l': location, 'fromage': '7'},
                    #         search_term,
                    #         location,
                    #         'Indeed US'
                    #     ))
                    
                    # LinkedIn - DISABLED (links blocked by LinkedIn)
                    # tasks.append(self.scrape_website_async(
                    #     session,
                    #     'https://www.linkedin.com/jobs/search',
                    #     {'keywords': search_term, 'location': location, 'f_TPR': 'r604800'},
                    #     search_term,
                    #     location,
                    #     'LinkedIn'
                    # ))
                    
                    # Glassdoor - DISABLED (403 blocked)
                    # tasks.append(self.scrape_website_async(
                    #     session,
                    #     'https://www.glassdoor.com/Job/jobs.htm',
                    #     {'sc.keyword': search_term, 'locKeyword': location, 'fromAge': 7},
                    #     search_term,
                    #     location,
                    #     'Glassdoor'
                    # ))
                    
                    # Dice (for tech jobs)
                    if any(kw in search_term.lower() for kw in ['engineer', 'developer', 'data', 'software']):
                        tasks.append(self.scrape_website_async(
                            session,
                            'https://www.dice.com/jobs',
                            {'q': search_term, 'location': location},
                            search_term,
                            location,
                            'Dice'
                        ))
            
            # Run all scraping concurrently (jobs added to queue as they're found)
            print(f"\n  Launching {len(tasks)} concurrent scraping tasks...")
            print(f"  Jobs will stream to LLM workers as they're found...\n")
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def analyze_job_match(self, job):
        """Use LLM to analyze job match and extract details (Unified Prompt)"""
        if not self.llm or not self.resume_text:
            return {
                'match_score': 0, 
                'reasoning': 'LLM not available', 
                'salary_min': 100000, 
                'salary_max': 100000, 
                'location': job.get('location', ''), 
                'is_remote': False
            }
        
        prompt = f"""
Analyze this job for a candidate.

RESUME: {self.resume_text[:3000]}

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Description: {job['description'][:3000]}

TASK:
1. Extract Salary (use 100000 if missing). If range, use min/max. If single number, use as both.
2. Extract Location (city/state). If not found, use job location.
3. Determine Remote Status (Remote/Hybrid/Onsite).
4. CAREFULLY identify candidate's ACTUAL education from resume (Bachelor's/Master's/PhD/None).
5. Check job's Education Requirements (PhD/Masters/Bachelor's/None specified).
6. Identify Company Prestige Tier.
7. Score Match (0-1000 points) based on:

   Base Match (0-400 points):
   - Skills alignment with job requirements
   - Experience level match
   - Role fit and domain expertise

   Education Match (-200 to +100 points):
   - FIRST: Determine candidate's highest degree from resume
   - THEN: Compare to job requirement
   - +100: Candidate exceeds requirement (has PhD, requires Bachelor's)
   - +50: Candidate meets requirement exactly
   - +0: Job has no education requirement specified
   - -100: Candidate missing one degree level (requires Masters, has Bachelor's)
   - -200: Candidate missing two+ degree levels (requires PhD, has Bachelor's or no degree)

   Company Prestige Bonus (0-100 points):
   - +100: FAANG (Google, Amazon, Meta, Apple, Microsoft, Netflix)
   - +80: Tech unicorns (Stripe, Databricks, OpenAI, Anthropic, SpaceX, Tesla)
   - +50: Major tech companies (Shopify, Square, Snap, Uber, Airbnb, Twitter/X, Reddit)
   - +30: Well-known companies (Fortune 500, established tech)
   - +0: Unknown/small companies

   Salary Bonus (0-100 points):
   - +100: Average salary >= $150k
   - +80: Average salary >= $120k
   - +50: Average salary >= $100k
   - +25: Average salary >= $80k
   - +0: Below $80k

   Location Bonus (0-150 points):
   - +150: Toronto or GTA (Greater Toronto Area)
   - +100: Other major Canadian cities (Vancouver, Montreal, Ottawa)
   - +50: Major US tech hubs (SF Bay Area, NYC, Seattle, Austin, Boston)
   - +0: Other locations

   Remote Bonus (0-150 points):
   - +150: Fully Remote
   - +100: Hybrid (2-3 days remote)
   - +50: Flexible/occasional remote
   - +0: Onsite only

IMPORTANT:
- Max score is 1000 points
- If job requires Staff/Principal level (8+ years) but candidate lacks seniority: cap at 400
- If job requires Senior level (5+ years) but candidate is mid-level: cap at 600
- Missing critical required skills: below 500

Return JSON ONLY:
{{
  "salary_min": number,
  "salary_max": number,
  "location": "City, State",
  "is_remote": boolean,
  "education_required": "PhD/Masters/Bachelor's/None",
  "company_prestige": "FAANG/Unicorn/Major/Well-known/Unknown",
  "match_score": 0-1000,
  "reasoning": "brief explanation including education match and company prestige"
}}
"""

        try:
            response = self.llm.generate(prompt, stream=False)
            
            # Parse JSON from response - try multiple strategies
            analysis = None
            
            # Strategy 1: Extract JSON between first { and last }
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                try:
                    analysis = json.loads(json_str)
                except json.JSONDecodeError:
                    # Strategy 2: Try to find JSON in code block
                    if '```json' in response:
                        json_start = response.find('```json') + 7
                        json_end = response.find('```', json_start)
                        if json_end > json_start:
                            json_str = response[json_start:json_end].strip()
                            try:
                                analysis = json.loads(json_str)
                            except:
                                pass
                    
                    # Strategy 3: Try cleaning common issues
                    if not analysis:
                        json_str = json_str.replace('\n', ' ').replace('\r', '')
                        json_str = json_str.replace(',]', ']').replace(',}', '}')  # Remove trailing commas
                        try:
                            analysis = json.loads(json_str)
                        except:
                            pass
            
            # Validate analysis has required fields
            if analysis and isinstance(analysis, dict):
                # Ensure defaults and None checks
                salary_min = analysis.get('salary_min')
                salary_max = analysis.get('salary_max')
                
                # Handle None values for salary
                if salary_min is None or not isinstance(salary_min, (int, float)):
                    salary_min = 0
                if salary_max is None or not isinstance(salary_max, (int, float)):
                    salary_max = 0
                
                analysis['salary_min'] = int(salary_min)
                analysis['salary_max'] = int(salary_max)
                analysis.setdefault('location', job.get('location', ''))
                analysis.setdefault('is_remote', False)
                analysis.setdefault('match_score', 0)
                analysis.setdefault('reasoning', 'No reasoning provided')
                
                return analysis
            
            # All strategies failed - use fallback
            return {
                'match_score': 0, 
                'reasoning': 'Failed to parse LLM response', 
                'salary_min': 100000, 
                'salary_max': 100000, 
                'location': job.get('location', ''), 
                'is_remote': False
            }
                
        except Exception as e:
            print(f"    LLM analysis error: {e}")
            return {
                'match_score': 0, 
                'reasoning': f'Error: {e}', 
                'salary_min': 100000, 
                'salary_max': 100000, 
                'location': job.get('location', ''), 
                'is_remote': False
            }
    
    def _basic_match_analysis(self, job):
        """Fallback basic keyword matching if LLM fails"""
        resume_lower = self.resume_text.lower()
        job_text = f"{job['title']} {job['description']}".lower()
        
        # Common tech skills to check
        skills = ['python', 'java', 'javascript', 'react', 'node', 'sql', 'aws', 
                  'docker', 'kubernetes', 'machine learning', 'data science', 
                  'api', 'rest', 'agile', 'git']
        
        matches = [skill for skill in skills if skill in resume_lower and skill in job_text]
        score = min(len(matches) * 10, 100)
        
        return {
            'score': score,
            'reasoning': f"Basic keyword match: {len(matches)} skills found",
            'key_matches': matches,
            'gaps': []
        }
    
    def analyze_and_email_worker(self, min_match_score, high_match_threshold, worker_id):
        """Worker thread: analyzes jobs from queue and saves to database"""
        print(f"  [Worker {worker_id}] Started")
        
        while not self.analysis_complete.is_set() or not self.job_queue.empty():
            try:
                # Get job from queue with timeout
                job = self.job_queue.get(timeout=1)
                
                # Start timing
                start_time = time.time()
                
                # Analyze job
                analysis = self.analyze_job_match(job)
                job['analysis'] = analysis
                
                # Calculate time taken
                analysis_time = time.time() - start_time
                
                # Save to database
                try:
                    # Ensure site exists
                    site_id = self.db.get_or_create_site(job.get('source', 'Unknown'), 'unknown', 'unknown')
                    
                    # Add job to jobs table
                    job_data = {
                        'title': job['title'],
                        'company': job['company'],
                        'url': job['url'],
                        'description': job.get('description', ''),
                        'salary_min': analysis.get('salary_min', 0),
                        'salary_max': analysis.get('salary_max', 0),
                        'location': analysis.get('location', job.get('location', '')),
                        'is_remote': analysis.get('is_remote', False)
                    }
                    job_id = self.db.add_job(job_data)
                    
                    # Add application
                    if job_id:
                        self.db.add_application(
                            job_id, 
                            site_id, 
                            self.resume_id, 
                            analysis.get('match_score', 0), 
                            analysis.get('reasoning', '')
                        )
                except Exception as e:
                    print(f"  [Worker {worker_id}] Database error: {e}")
                
                # Log result
                score = analysis.get('match_score', 0)
                display_score = score // 10  # Show as 0-100 for readability
                queue_remaining = self.job_queue.qsize()
                
                if score >= min_match_score:
                    with self.jobs_lock:
                        self.jobs_found.append(job)
                    
                    # Check if it's a high match
                    if score >= high_match_threshold:
                        with self.high_matches_lock:
                            self.high_matches.append(job)
                    
                    print(f"  [Worker {worker_id}] ✓ {job['title']} at {job['company']}: {display_score}/100 ({analysis_time:.1f}s) (Queue: {queue_remaining})")
                else:
                    print(f"  [Worker {worker_id}] ✗ {job['title']}: {display_score}/100 ({analysis_time:.1f}s) (Queue: {queue_remaining})")
                
                self.job_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"  [Worker {worker_id}] Error: {e}")
                self.job_queue.task_done()
        
        print(f"  [Worker {worker_id}] Finished")
    
    def send_top_jobs_email(self):
        """Send email with top 5 jobs for this resume"""
        if not self.email_config:
            print("⚠ No email configuration provided. Skipping email.")
            return
            
        top_jobs = self.db.get_top_jobs_for_resume(self.resume_id, limit=5)
        
        if not top_jobs:
            print("No new jobs to email.")
            return
            
        print(f"Sending email with top {len(top_jobs)} jobs...")
        
        msg = MIMEMultipart()
        msg['From'] = self.email_config['sender']
        msg['To'] = self.email_config['recipient']
        msg['Subject'] = f"Top {len(top_jobs)} Job Matches for {Path(self.resume_path).stem}"
        
        # Build HTML body
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .job-card {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; background-color: #f9f9f9; }}
                .job-title {{ font-size: 18px; font-weight: bold; color: #2c3e50; }}
                .company {{ font-weight: bold; color: #7f8c8d; }}
                .score {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-weight: bold; color: white; }}
                .score-high {{ background-color: #27ae60; }}
                .score-med {{ background-color: #f39c12; }}
                .details {{ margin-top: 10px; font-size: 14px; }}
                .apply-btn {{ display: inline-block; background-color: #3498db; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; margin-top: 10px; }}
            </style>
        </head>
        <body>
            <h2>Top Job Matches</h2>
            <p>Here are the top {len(top_jobs)} jobs found for your resume based on skills, salary, location, and remote options.</p>
        """
        
        job_urls = []
        
        for i, job in enumerate(top_jobs, 1):
            score = job.get('score', 0)
            display_score = score // 10  # Convert 0-1000 to 0-100 for display
            score_class = "score-high" if display_score >= 80 else "score-med"
            
            # Handle None values for salary
            salary_min = job.get('salary_min') or 0
            salary_max = job.get('salary_max') or 0
            salary_text = f"${salary_min:,} - ${salary_max:,}" if salary_min > 0 else "Not listed"
            remote_text = "Remote/Hybrid" if job.get('is_remote') else "On-site"
            
            html_body += f"""
            <div class="job-card">
                <div class="job-title">{i}. {html.escape(job['title'])} <span class="score {score_class}">{display_score}/100</span></div>
                <div class="company">{html.escape(job['company'])} - {html.escape(job['location'])}</div>
                <div class="details">
                    <strong>Salary:</strong> {salary_text} | <strong>Type:</strong> {remote_text} | <strong>Source:</strong> {job['source']}
                </div>
                <div class="details">
                    <em>{html.escape(job['analysis_text'])}</em>
                </div>
                <a href="{job['url']}" class="apply-btn">Apply Now</a>
            </div>
            """
            job_urls.append(job['url'])
            
        html_body += """
            <p>Generated by JobFinderBot</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.email_config['sender'], self.email_config['password'])
                server.send_message(msg)
            print(f"✓ Email sent successfully to {self.email_config['recipient']}")
            
            # Mark jobs as emailed in database
            self.db.mark_jobs_emailed(self.resume_id, job_urls)
            
        except Exception as e:
            print(f"✗ Failed to send email: {e}")

    def format_email_html(self, high_matches):
        """Format high-match jobs as HTML email"""
        html = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .job {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .high-match {{ background-color: #e8f5e9; }}
        .score {{ font-size: 24px; font-weight: bold; color: #2e7d32; }}
        .title {{ font-size: 18px; font-weight: bold; color: #1976d2; }}
        .company {{ color: #666; }}
        .matches {{ color: #2e7d32; }}
        .gaps {{ color: #c62828; }}
    </style>
</head>
<body>
    <h1>🎯 High-Match Job Opportunities Found!</h1>
    <p>Found {len(high_matches)} jobs matching your resume with 80+ match score:</p>
"""
        
        for job in high_matches:
            analysis = job.get('analysis', {})
            html += f"""
    <div class="job high-match">
        <div class="score">Match Score: {analysis.get('score', 0)}/100</div>
        <div class="title">{html.escape(job['title'])}</div>
        <div class="company">{html.escape(job['company'])} - {html.escape(job['location'])}</div>
        <div style="margin: 10px 0;">
            <strong>Source:</strong> {job['source']}<br>
            <strong>URL:</strong> {'<a href="' + job['url'] + '" target="_blank">View Job Posting</a>' if job.get('url') and job['url'].startswith('http') and not any(blocked in job['source'].lower() for blocked in ['indeed', 'linkedin', 'glassdoor']) else '<em>Link not available (site blocks automation)</em>'}
        </div>
        <div style="margin: 10px 0;">
            <strong>Reasoning:</strong> {html.escape(analysis.get('reasoning', 'N/A'))}
        </div>
        <div class="matches">
            <strong>✓ Key Matches:</strong> {html.escape(', '.join(analysis.get('key_matches', [])))}
        </div>
        <div class="gaps">
            <strong>✗ Gaps:</strong> {html.escape(', '.join(analysis.get('gaps', [])) or 'None identified')}
        </div>
    </div>
"""
        
        html += """
    <p>Run by Job Finder Bot</p>
</body>
</html>
"""
        return html
    
    def find_jobs(self, search_terms=None, locations=None, countries=None, 
                  min_match_score=60, high_match_threshold=80, num_workers=8):
        """
        Main job finding pipeline - STREAMING VERSION
        Scrapers feed queue while LLM workers process in real-time
        
        Args:
            search_terms: List of job search terms
            locations: List of locations
            countries: List of countries for Indeed
            min_match_score: Minimum score to save job
            high_match_threshold: Score threshold for email notifications
            num_workers: Number of parallel LLM analysis threads (default: 8)
        
        Returns:
            List of all jobs found with match scores
        """
        # Default search parameters
        if search_terms is None:
            search_terms = ['data scientist', 'machine learning engineer', 'software engineer']
        if locations is None:
            locations = ['Toronto, ON', 'Vancouver, BC', 'New York, NY', 'San Francisco, CA']
        if countries is None:
            countries = ['ca', 'us']
        
        print(f"\n{'='*60}")
        print(f"JOB FINDER BOT (STREAMING) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        print("Architecture: Scrapers → Queue → LLM Workers → Email")
        print("Jobs analyzed in real-time as they're found!\n")
        
        start_time = time.time()
        total_jobs_scraped = 0
        
        # Step 1: Start LLM worker threads FIRST
        print(f"Starting {num_workers} LLM worker threads...")
        workers = []
        for i in range(num_workers):
            worker = threading.Thread(
                target=self.analyze_and_email_worker,
                args=(min_match_score, high_match_threshold, i+1),
                daemon=True
            )
            worker.start()
            workers.append(worker)
        print(f"✓ Workers ready and waiting for jobs\n")
        
        # Step 2: Scrape APIs and websites concurrently (they feed queue as they go)
        print("="*60)
        print("Fetching jobs from all sources (concurrent)...")
        print("="*60)
        
        async def scrape_all_sources():
            """Run all scraping concurrently - loads from config file"""
            async with aiohttp.ClientSession() as session:
                tasks = []
                
                # API tasks - Load from config
                for source in self.job_sources.get('api_sources', []):
                    if source.get('enabled', False):
                        for search_term in search_terms:
                            tasks.append(self.fetch_api_async(
                                session,
                                source['url'],
                                search_term,
                                source['name']
                            ))
                
                # Website scraping tasks - Load from config
                for search_term in search_terms:
                    for location in locations:
                        # Playwright sources
                        for source in self.job_sources.get('playwright_sources', []):
                            if source.get('enabled', False):
                                # Check country restrictions
                                if 'countries' in source:
                                    # Only add if any required country is in the countries list
                                    if not any(c in countries for c in source['countries']):
                                        continue
                                
                                tasks.append(self.scrape_with_playwright_async(
                                    source['url'],
                                    search_term,
                                    location,
                                    source['name']
                                ))
                        
                        # Regular scraping sources
                        for source in self.job_sources.get('scraping_sources', []):
                            if source.get('enabled', False):
                                # Check if keywords match (for tech-specific sites like Dice)
                                if 'keywords' in source:
                                    if not any(kw in search_term.lower() for kw in source['keywords']):
                                        continue
                                
                                tasks.append(self.scrape_website_async(
                                    session,
                                    source['url'],
                                    {'q': search_term, 'location': location},
                                    search_term,
                                    location,
                                    source['name']
                                ))
                
                print(f"\nLaunching {len(tasks)} concurrent scraping tasks...")
                print(f"Jobs stream to LLM workers as they're found...\n")
                
                # Run all scraping concurrently
                await asyncio.gather(*tasks, return_exceptions=True)
        
        # Run the async scraping
        scrape_start = time.time()
        asyncio.run(scrape_all_sources())
        scrape_time = time.time() - scrape_start
        
        print(f"\n✓ All scraping complete in {scrape_time:.1f}s")
        print(f"  Queue size: {self.job_queue.qsize()} jobs pending analysis\n")
        
        # Step 3: Wait for all jobs in queue to be processed
        print("="*60)
        print("Waiting for LLM workers to finish analyzing...")
        print("="*60 + "\n")
        
        self.job_queue.join()
        
        # Step 4: Signal workers to stop and wait for them
        self.analysis_complete.set()
        for worker in workers:
            worker.join()
        
        total_time = time.time() - start_time
        analysis_time = total_time - scrape_time
        
        # Remove duplicates from results
        unique_jobs = {}
        for job in self.jobs_found:
            key = (job['title'].lower(), job['company'].lower())
            if key not in unique_jobs:
                unique_jobs[key] = job
        
        self.jobs_found = list(unique_jobs.values())
        
        # Sort by score
        self.jobs_found.sort(key=lambda x: x['analysis'].get('match_score', 0), reverse=True)
        self.high_matches.sort(key=lambda x: x['analysis'].get('match_score', 0), reverse=True)
        
        print(f"\n{'='*60}")
        print(f"FINAL Results Summary:")
        print(f"  Scraping time: {scrape_time:.1f}s")
        print(f"  Analysis time: {analysis_time:.1f}s (overlapped with scraping!)")
        print(f"  Total time: {total_time:.1f}s")
        print(f"\n  Jobs analyzed: {len(self.jobs_found)}")
        print(f"  Jobs meeting minimum score ({min_match_score}+): {len(self.jobs_found)}")
        print(f"  High matches ({high_match_threshold}+): {len(self.high_matches)}")
        print(f"{'='*60}\n")
        
        # Save results
        self.save_results()
        
        # Send top jobs email
        self.send_top_jobs_email()
        
        return self.jobs_found
    
    def save_results(self):
        """Save results to JSON and text files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON
        json_file = f"job_results_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_jobs': len(self.jobs_found),
                'high_matches': len(self.high_matches),
                'jobs': self.jobs_found
            }, f, indent=2)
        print(f"✓ Saved results to database and {json_file}")
        
        # Save text report
        txt_file = f"job_report_{timestamp}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"JOB FINDER REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total Jobs Found: {len(self.jobs_found)}\n")
            f.write(f"High Matches (80+): {len(self.high_matches)}\n\n")
            
            if self.high_matches:
                f.write("HIGH MATCH JOBS:\n")
                f.write("=" * 80 + "\n\n")
                for job in self.high_matches:
                    analysis = job['analysis']
                    f.write(f"SCORE: {analysis.get('match_score', 0)}/100\n")
                    f.write(f"Title: {job['title']}\n")
                    f.write(f"Company: {job['company']}\n")
                    f.write(f"Location: {analysis.get('location', job['location'])}\n")
                    f.write(f"Source: {job['source']}\n")
                    f.write(f"URL: {job['url']}\n")
                    f.write(f"Salary: ${analysis.get('salary_min', 0):,} - ${analysis.get('salary_max', 0):,}\n")
                    f.write(f"Remote: {'Yes' if analysis.get('is_remote') else 'No'}\n")
                    f.write(f"Reasoning: {analysis.get('reasoning', 'N/A')}\n")
                    f.write("-" * 80 + "\n\n")
            
            if self.jobs_found:
                f.write("\nALL MATCHING JOBS:\n")
                f.write("=" * 80 + "\n\n")
                for job in self.jobs_found:
                    analysis = job['analysis']
                    f.write(f"{analysis.get('match_score', 0)}/100 - {job['title']} at {job['company']} ({job['source']})\n")
        
        print(f"✓ Saved report to database and {txt_file}")


def main():
    parser = argparse.ArgumentParser(description='Job Finder Bot with LLM Resume Matching')
    parser.add_argument('--resume', type=str, help='Path to resume PDF file')
    parser.add_argument('--auto', action='store_true', help='Auto mode for scheduled runs (processes all resumes in Resumes folder)')
    parser.add_argument('--min-score', type=int, default=600, help='Minimum match score to save (default: 600/1000 = 60/100)')
    parser.add_argument('--high-threshold', type=int, default=800, help='High match threshold for email (default: 800/1000 = 80/100)')
    parser.add_argument('--workers', type=int, default=8, help='Number of parallel LLM worker threads (default: 8, max: 12)')
    
    args = parser.parse_args()
    
    # Load configuration from config.yaml
    config_path = Path(__file__).parent / 'config.yaml'
    if not config_path.exists():
        print("Error: config.yaml not found!")
        print("Please copy config.example.yaml to config.yaml and fill in your details.")
        return
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Email configuration
    email_config = {
        'sender': config['email']['sender'],
        'password': config['email']['password'],
        'recipient': None  # Will be extracted from each resume
    }
    
    # Determine which resumes to process
    resumes_to_process = []
    
    if args.auto:
        # Auto mode: process ALL resumes in Resumes folder
        resumes_dir = Path(__file__).parent / config['paths']['resumes_dir']
        if resumes_dir.exists():
            resumes_to_process = list(resumes_dir.glob("*.pdf"))
            print(f"\n{'='*60}")
            print(f"AUTO MODE: Found {len(resumes_to_process)} resumes to process")
            print(f"{'='*60}\n")
        else:
            print(f"Error: Resumes directory not found at {resumes_dir}")
            return
    elif args.resume:
        # Single resume specified
        resume_path = Path(args.resume)
        if resume_path.exists():
            resumes_to_process = [resume_path]
        else:
            print(f"Error: Resume not found at {args.resume}")
            return
    else:
        # Interactive mode
        print("\nAvailable resumes:")
        resumes_dir = Path(__file__).parent / config['paths']['resumes_dir']
        if resumes_dir.exists():
            resumes = list(resumes_dir.glob("*.pdf"))
            for i, resume in enumerate(resumes, 1):
                print(f"  {i}. {resume.name}")
            
            choice = input("\nSelect resume number (or 'all' to process all, Enter for first): ").strip().lower()
            if choice == 'all':
                resumes_to_process = resumes
            elif choice and choice.isdigit() and 1 <= int(choice) <= len(resumes):
                resumes_to_process = [resumes[int(choice) - 1]]
            else:
                resumes_to_process = [resumes[0]] if resumes else []
        else:
            print(f"Error: Resumes directory not found")
            return
        
        # Prompt for email in interactive mode
        send_email = input("\nSend email notifications? (y/n): ").strip().lower()
        if send_email == 'y':
            sender = input("Gmail address: ").strip()
            password = input("Gmail App Password (16 chars): ").strip()
            email_config = {
                'sender': sender,
                'password': password,
                'recipient': None  # Will be extracted from resume
            }
        else:
            email_config = None
    
    if not resumes_to_process:
        print("No resumes to process")
        return
    
    # Process each resume
    total_high_matches = 0
    for idx, resume_path in enumerate(resumes_to_process, 1):
        print(f"\n{'='*60}")
        print(f"Processing resume {idx}/{len(resumes_to_process)}: {resume_path.name}")
        print(f"{'='*60}\n")
        
        try:
            # Initialize job finder for this resume
            db_path = Path(__file__).parent / config['paths']['database']
            finder = JobFinder(str(resume_path), email_config, str(db_path))
            
            # Run job search
            results = finder.find_jobs(
                min_match_score=args.min_score,
                high_match_threshold=args.high_threshold,
                num_workers=args.workers
            )
            
            total_high_matches += len(finder.high_matches)
            
            print(f"\n{'='*60}")
            print(f"Completed: {resume_path.name}")
            print(f"  High matches: {len(finder.high_matches)}")
            print(f"  Total jobs: {len(finder.jobs_found)}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n✗ Error processing {resume_path.name}: {e}\n")
            continue
    
    print(f"\n{'='*60}")
    print(f"ALL RESUMES PROCESSED!")
    print(f"  Total resumes: {len(resumes_to_process)}")
    print(f"  Total high matches across all resumes: {total_high_matches}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

