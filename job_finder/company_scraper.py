"""
Company Career Page Scraper with Self-Learning Capabilities
Uses Playwright for browser automation and LLM for code generation
"""

import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from datetime import datetime


class CompanyScraperAgent:
    """
    Self-learning web scraper that:
    1. Fetches career pages with Playwright (handles JavaScript)
    2. Analyzes HTML structure with LLM
    3. Generates domain-specific scraping code
    4. Caches generated code for reuse
    """
    
    def __init__(self, llm, cache_dir="scraper_cache"):
        """
        Initialize scraper agent
        
        Args:
            llm: LocalLLM instance for code generation
            cache_dir: Directory to cache generated scraper code
        """
        self.llm = llm
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # In-memory cache: domain -> scraper function
        self.scraper_cache = {}
        
        # Load cached scrapers from disk
        self._load_cached_scrapers()
    
    def _extract_domain(self, url):
        """Extract domain from URL for cache key"""
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain
    
    def _load_cached_scrapers(self):
        """Load previously generated scrapers from disk"""
        for cache_file in self.cache_dir.glob("*.py"):
            domain = cache_file.stem
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                # Execute cached code to load function
                namespace = {}
                exec(code, namespace)
                
                if 'scrape_jobs' in namespace:
                    self.scraper_cache[domain] = namespace['scrape_jobs']
                    print(f"  ✓ Loaded cached scraper: {domain}")
            except Exception as e:
                print(f"  ⚠ Failed to load cache for {domain}: {e}")
    
    async def scrape_company_careers(self, url, search_term=""):
        """
        Main entry point: scrape jobs from company career page
        
        Args:
            url: Career page URL
            search_term: Optional search term to filter jobs
            
        Returns:
            List of job dictionaries
        """
        domain = self._extract_domain(url)
        
        # Check if we have cached scraper for this domain
        if domain in self.scraper_cache:
            print(f"  Using cached scraper for {domain}")
            scraper_func = self.scraper_cache[domain]
        else:
            print(f"  Generating new scraper for {domain}...")
            scraper_func = await self._generate_scraper(url, domain)
            
            if not scraper_func:
                print(f"  ✗ Failed to generate scraper for {domain}")
                return []
            
            self.scraper_cache[domain] = scraper_func
        
        # Fetch page with Playwright and run scraper
        jobs = await self._run_scraper_with_playwright(url, scraper_func, search_term)
        return jobs
    
    async def _generate_scraper(self, url, domain):
        """
        Generate domain-specific scraper using LLM
        
        Args:
            url: Career page URL to analyze
            domain: Domain name for caching
            
        Returns:
            Scraper function or None if failed
        """
        try:
            # Fetch HTML with Playwright
            html_sample = await self._fetch_html_sample(url)
            
            if not html_sample:
                return None
            
            # Ask LLM to generate scraping code
            prompt = f"""Analyze this career page HTML and generate Python code to extract job listings.

HTML SAMPLE (first 8000 chars):
{html_sample[:8000]}

Generate a Python function that extracts job information from this HTML structure.
Use BeautifulSoup (already imported as 'soup' parameter).

Requirements:
- Function signature: def scrape_jobs(soup, base_url)
- Extract: title, location, url (make absolute with base_url), description
- Return list of dicts with keys: title, location, url, description
- Handle missing fields gracefully (use empty string)
- Filter out non-job items (e.g., blog posts, news)

Return ONLY the Python function code, no explanations or markdown.
Do NOT include import statements.

Example format:
def scrape_jobs(soup, base_url):
    jobs = []
    job_cards = soup.find_all('div', class_='job-card')
    for card in job_cards:
        title_elem = card.find('h3')
        if title_elem:
            jobs.append({{
                'title': title_elem.get_text(strip=True),
                'location': ...,
                'url': ...,
                'description': ...
            }})
    return jobs
"""
            
            # Generate code with LLM
            response = self.llm.generate(prompt, stream=False)
            
            # Extract code from response
            code = self._extract_code(response)
            
            if not code:
                print(f"  ✗ LLM failed to generate valid code")
                return None
            
            # Validate and execute code
            scraper_func = self._validate_and_execute(code, domain)
            
            return scraper_func
            
        except Exception as e:
            print(f"  ✗ Error generating scraper: {e}")
            return None
    
    def _extract_code(self, llm_response):
        """Extract Python code from LLM response"""
        code = llm_response.strip()
        
        # Remove markdown code blocks if present
        if '```python' in code:
            start = code.find('```python') + 9
            end = code.find('```', start)
            code = code[start:end].strip()
        elif '```' in code:
            start = code.find('```') + 3
            end = code.find('```', start)
            code = code[start:end].strip()
        
        # Ensure it starts with def scrape_jobs
        if 'def scrape_jobs' not in code:
            return None
        
        return code
    
    def _validate_and_execute(self, code, domain):
        """
        Validate and execute generated code
        
        Args:
            code: Python code string
            domain: Domain name for caching
            
        Returns:
            Scraper function or None
        """
        try:
            # Prepare namespace for execution
            namespace = {
                'urlparse': urlparse,
                'urljoin': lambda base, url: url if url.startswith('http') else base.rstrip('/') + '/' + url.lstrip('/')
            }
            
            # Execute code
            exec(code, namespace)
            
            # Check if scrape_jobs function exists
            if 'scrape_jobs' not in namespace:
                print(f"  ✗ Generated code missing scrape_jobs function")
                return None
            
            scraper_func = namespace['scrape_jobs']
            
            # Save to cache file
            cache_file = self.cache_dir / f"{domain}.py"
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(f"# Generated scraper for {domain}\n")
                f.write(f"# Created: {datetime.now().isoformat()}\n\n")
                f.write(code)
            
            print(f"  ✓ Generated and cached scraper for {domain}")
            
            return scraper_func
            
        except Exception as e:
            print(f"  ✗ Code validation failed: {e}")
            return None
    
    async def _fetch_html_sample(self, url):
        """Fetch HTML using Playwright (handles JavaScript)"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set user agent
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                # Navigate and wait for content
                await page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Get HTML content
                html = await page.content()
                
                await browser.close()
                
                return html
                
        except Exception as e:
            print(f"  ✗ Failed to fetch {url}: {e}")
            return None
    
    async def _run_scraper_with_playwright(self, url, scraper_func, search_term):
        """
        Run generated scraper function with Playwright-fetched HTML
        
        Args:
            url: URL to scrape
            scraper_func: Generated scraper function
            search_term: Optional filter term
            
        Returns:
            List of job dicts
        """
        try:
            from bs4 import BeautifulSoup
            
            # Fetch HTML with Playwright
            html = await self._fetch_html_sample(url)
            
            if not html:
                return []
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Run scraper function
            jobs = scraper_func(soup, url)
            
            # Filter by search term if provided
            if search_term and jobs:
                search_lower = search_term.lower()
                filtered_jobs = []
                for job in jobs:
                    title = job.get('title', '').lower()
                    description = job.get('description', '').lower()
                    if search_lower in title or search_lower in description:
                        filtered_jobs.append(job)
                jobs = filtered_jobs
            
            return jobs
            
        except Exception as e:
            print(f"  ✗ Scraper execution failed: {e}")
            return []
