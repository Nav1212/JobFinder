# Job Finder Bot - Quick Start

## ✅ Files Created
- `job_finder_bot.py` - Main bot script (690 lines)
- `run_daily.bat` - Daily scheduler batch file
- `job_requirements.txt` - Python dependencies
- `JOB_FINDER_SETUP.md` - Full setup guide

## ✅ Dependencies Installed
All Python packages are already installed:
- requests 2.32.5
- beautifulsoup4 4.14.2
- PyPDF2 3.0.1

---

## 🚀 Next Steps

### 1. Install Ollama (Local LLM)
The bot uses Ollama for resume matching. Install it:

```powershell
# Run the setup script from LLMStuff folder
cd LLMStuff
py setup_local_llm.py
```

This will:
- Download and install Ollama
- Pull the llama3.1:8b model (4.7GB)
- Test the installation

**Alternative:** Download manually from https://ollama.com/download/windows

After installation, verify:
```powershell
ollama list
```

### 2. Configure Email Notifications

**Get Gmail App Password:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Go to https://myaccount.google.com/apppasswords
4. Create password for "Mail" + "Windows Computer"
5. Copy the 16-character password (e.g., "abcd efgh ijkl mnop")

**Update job_finder_bot.py:**
Open `job_finder_bot.py` and find line 560:

```python
email_config = {
    'sender': 'your-email@gmail.com',      # CHANGE THIS
    'password': 'your-app-password',        # CHANGE THIS (remove spaces!)
    'recipient': 'your-email@gmail.com'    # CHANGE THIS
}
```

Example:
```python
email_config = {
    'sender': 'john.doe@gmail.com',
    'password': 'abcdefghijklmnop',  # 16 chars, no spaces
    'recipient': 'john.doe@gmail.com'
}
```

### 3. Add Your Resume

Place your resume PDF in the Resumes folder:
```
C:\Users\User\Desktop\VibeCoding\Resumes\resume_data_scientist.pdf
```

Or use a different name and update line 558 in `job_finder_bot.py`:
```python
resume_path = r"C:\Users\User\Desktop\VibeCoding\Resumes\YOUR_RESUME.pdf"
```

### 4. Test the Bot

**Interactive Test (recommended first):**
```powershell
cd C:\Users\User\Desktop\VibeCoding
py job_finder_bot.py
```

This will:
- Let you select a resume
- Ask if you want email notifications
- Show real-time progress
- Save results to JSON and text files

**Auto Mode Test (simulates scheduled run):**
```powershell
py job_finder_bot.py --auto
```

This simulates the daily scheduled run with default settings.

### 5. Set Up Daily Automation

**Option A: Windows Task Scheduler**

1. Open Task Scheduler: Press `Win + R`, type `taskschd.msc`
2. Click "Create Basic Task"
3. Name: `Job Finder Bot`
4. Trigger: Daily at 11:00 AM
5. Action: Start program
   - Program: `C:\Users\User\Desktop\VibeCoding\run_daily.bat`
6. Finish and test by right-clicking → Run

**Option B: Manual Runs**
Just double-click `run_daily.bat` whenever you want to search for jobs.

---

## 📊 What the Bot Does

1. **Scrapes 5 job boards:**
   - Indeed Canada
   - Indeed USA
   - LinkedIn
   - Glassdoor
   - Dice.com

2. **Search terms:**
   - Data scientist
   - Machine learning engineer
   - Software engineer

3. **Locations:**
   - Toronto, ON
   - Vancouver, BC
   - New York, NY
   - San Francisco, CA

4. **LLM Analysis:**
   - Extracts text from your resume PDF
   - Compares each job to your resume
   - Scores 0-100 with reasoning
   - Identifies key skill matches and gaps

5. **Notifications:**
   - Saves all jobs with 60+ score to JSON/text files
   - Emails jobs with 80+ score (high matches)

---

## 📁 Output Files

Each run creates:
- `job_results_YYYYMMDD_HHMMSS.json` - Complete data
- `job_report_YYYYMMDD_HHMMSS.txt` - Human-readable report
- `job_finder.log` - Run history (via run_daily.bat)

---

## 🔧 Customization

**Change search terms** (line 513 in job_finder_bot.py):
```python
search_terms = ['your', 'job', 'titles']
locations = ['Your', 'Cities']
```

**Adjust scoring thresholds:**
```powershell
py job_finder_bot.py --auto --min-score 70 --high-threshold 85
```

**Use different LLM model** (line 33):
```python
self.llm = LocalLLM("phi3:medium")  # or "mistral:7b"
```

---

## 🐛 Troubleshooting

**"Could not initialize LLM"**
→ Ollama not running. Start it: `ollama serve` or install via `setup_local_llm.py`

**"Error sending email"**
→ Use App Password, not regular Gmail password. Enable 2-Step Verification first.

**"Resume not found"**
→ Check path in job_finder_bot.py line 558 or create Resumes folder

**No jobs found**
→ Job board HTML may have changed. Sites frequently update their structure.

**Task Scheduler not running**
→ Check that run_daily.bat path is absolute and Ollama is set to auto-start

---

## 💡 Pro Tips

1. **Start with interactive mode** to see how it works before scheduling
2. **Review job_report_*.txt** files to understand scoring patterns
3. **Adjust search terms** based on jobs you're actually interested in
4. **Check email spam folder** for first notification (Gmail may filter it)
5. **Run manually on weekends** to catch Sunday/Monday postings

---

## 📚 Full Documentation

See `JOB_FINDER_SETUP.md` for:
- Detailed email setup instructions
- Advanced customization options
- Multiple resume configurations
- Webhook integration (Slack/Discord)
- Database storage for tracking

---

**Ready to start?** Run `py setup_local_llm.py` in the LLMStuff folder, then test with `py job_finder_bot.py`

Good luck with your job search! 🎯
