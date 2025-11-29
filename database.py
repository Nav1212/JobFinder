import sqlite3
import json
from datetime import datetime
import os

class DatabaseManager:
    def __init__(self, db_path="jobs_database.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the star schema database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Sites Dimension
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sites (
            site_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            type TEXT,
            parser TEXT
        )
        ''')

        # Resumes Dimension
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            email TEXT,
            file_path TEXT,
            text TEXT,
            created_at TEXT
        )
        ''')

        # Jobs Dimension (Fact-like but stores job details)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            company TEXT,
            url TEXT UNIQUE,
            description TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            location TEXT,
            is_remote BOOLEAN,
            scraped_at TEXT
        )
        ''')

        # Job Applications Fact Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            site_id INTEGER,
            resume_id INTEGER,
            score INTEGER,
            analysis_text TEXT,
            emailed_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (job_id),
            FOREIGN KEY (site_id) REFERENCES sites (site_id),
            FOREIGN KEY (resume_id) REFERENCES resumes (resume_id),
            UNIQUE(job_id, resume_id)
        )
        ''')

        conn.commit()
        conn.close()

    def get_or_create_site(self, name, type, parser):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO sites (name, type, parser) VALUES (?, ?, ?)", (name, type, parser))
            conn.commit()
            cursor.execute("SELECT site_id FROM sites WHERE name = ?", (name,))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_or_create_resume(self, name, email, file_path, text):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO resumes (name, email, file_path, text, created_at) 
                VALUES (?, ?, ?, ?, ?)
            """, (name, email, file_path, text, datetime.now().isoformat()))
            conn.commit()
            cursor.execute("SELECT resume_id FROM resumes WHERE name = ?", (name,))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def add_job(self, job_data):
        """Add job to jobs table if it doesn't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Check if job exists by URL
            cursor.execute("SELECT job_id FROM jobs WHERE url = ?", (job_data['url'],))
            result = cursor.fetchone()
            
            if result:
                return result[0]
            
            cursor.execute("""
                INSERT INTO jobs (title, company, url, description, salary_min, salary_max, location, is_remote, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_data['title'],
                job_data['company'],
                job_data['url'],
                job_data.get('description', ''),
                job_data.get('salary_min', 0),
                job_data.get('salary_max', 0),
                job_data.get('location', ''),
                job_data.get('is_remote', False),
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error adding job: {e}")
            return None
        finally:
            conn.close()

    def add_application(self, job_id, site_id, resume_id, score, analysis):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO job_applications (job_id, site_id, resume_id, score, analysis_text, emailed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (job_id, site_id, resume_id, score, analysis, None))
            conn.commit()
        finally:
            conn.close()

    def check_already_applied(self, url, resume_id):
        """Check if this resume has already processed this job URL"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 1 FROM job_applications ja
                JOIN jobs j ON ja.job_id = j.job_id
                WHERE j.url = ? AND ja.resume_id = ?
            """, (url, resume_id))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_top_jobs_for_resume(self, resume_id, limit=5):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT j.title, j.company, j.url, j.location, j.salary_min, j.salary_max, j.is_remote, ja.score, ja.analysis_text, s.name as source
                FROM job_applications ja
                JOIN jobs j ON ja.job_id = j.job_id
                JOIN sites s ON ja.site_id = s.site_id
                WHERE ja.resume_id = ? AND ja.emailed_at IS NULL
                ORDER BY ja.score DESC
                LIMIT ?
            """, (resume_id, limit))
            
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
        finally:
            conn.close()

    def mark_jobs_emailed(self, resume_id, job_urls):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            now = datetime.now().isoformat()
            placeholders = ','.join(['?'] * len(job_urls))
            cursor.execute(f"""
                UPDATE job_applications 
                SET emailed_at = ? 
                WHERE resume_id = ? AND job_id IN (SELECT job_id FROM jobs WHERE url IN ({placeholders}))
            """, (now, resume_id, *job_urls))
            conn.commit()
        finally:
            conn.close()
