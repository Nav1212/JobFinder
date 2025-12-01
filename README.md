# 🤖 JobFinder - Unified Job Search & Resume Platform

An intelligent job search automation tool that uses LLM-powered resume matching to find and score job opportunities, plus a resume generator with PDF import.

## 📁 Project Structure

```
JobFinderBot/
├── run_job_finder.py    # Launch Job Finder GUI
├── run_resume_gen.py    # Launch Resume Generator GUI
├── config.yaml          # Configuration (email, paths)
├── job_sources.json     # Job board API sources
│
├── core/                # Shared utilities
│   └── llm_client.py    # Ollama LLM wrapper
│
├── job_finder/          # Job Finder module
│   ├── job_finder_bot.py    # Main job search logic
│   ├── database.py          # SQLite job tracking
│   └── gui/                 # Tkinter GUI components
│
└── resume_gen/          # Resume Generator module
    ├── user_manager.py      # Multi-user data management
    ├── generator.py         # Resume generation with TF-IDF
    ├── pdf_parser.py        # PDF import with LLM analysis
    └── import_review_tab.py # PDF review interface
```

## ✨ Features

### Job Finder
- **Multi-Source Scraping**: Aggregates jobs from LinkedIn, Indeed, Google Careers, Amazon Jobs, and more
- **LLM-Powered Matching**: Uses local Ollama LLM (Qwen 2.5) to analyze job fit based on your resume
- **Granular Scoring (0-1000)**: Advanced scoring system considering:
  - Skills alignment (0-400 pts)
  - Education match (-200 to +100 pts)
  - Company prestige (0-100 pts) - FAANG, Unicorns, Major Tech
  - Salary bonus (0-100 pts)
  - Location match (0-150 pts)
  - Remote work (0-150 pts)
- **SQLite Database**: Tracks all jobs, applications, and scores
- **Email Notifications**: Sends top 5 job matches via Gmail SMTP
- **Concurrent Processing**: 8 parallel LLM workers for fast analysis

### Resume Generator
- **Multi-User Support**: Isolated sentence libraries per user
- **PDF Import**: Parse existing resumes with LLM-powered analysis
- **Three Quality Scores**: Categorization confidence, extraction quality, impact score
- **Impact Suggestions**: AI-powered rewrites for stronger bullets
- **TF-IDF + Tag Matching**: Hybrid sentence selection for tailored resumes

## 📋 Requirements

- **Python 3.8+**
- **Ollama** with `qwen2.5:3b` or `llama3.1:8b` model
- Gmail account with App Password for email notifications

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r job_requirements.txt
pip install -r resume_gen/requirements.txt
```

### 2. Install Ollama and Model

```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5:3b
ollama serve
```

### 3. Configure the Bot

```bash
# Copy the example config
cp config.example.yaml config.yaml

# Edit config.yaml with your details:
# - Gmail email and app password
# - Paths to resumes, database, logs
```

### 4. Add Your Resume

Place your resume PDF in the `../Resumes` folder (or path specified in config.yaml)

### 5. Run the Bot

```bash
# Interactive mode
python job_finder_bot.py

# Auto mode (processes all resumes)
python job_finder_bot.py --auto

# Custom thresholds
python job_finder_bot.py --auto --min-score 700 --high-threshold 850
```

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
email:
  sender: "your-email@gmail.com"
  password: "your-16-char-app-password"
  
paths:
  resumes_dir: "../Resumes"
  database: "../jobs_database.db"
  logs_dir: "../JobFinderBot_Logs"
```

### Gmail App Password Setup

1. Enable 2FA on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Use the 16-character password in config.yaml

## 📊 Scoring System

The bot uses a granular 0-1000 point system:

| Category | Points | Description |
|----------|--------|-------------|
| **Base Match** | 0-400 | Skills, experience, role fit |
| **Education** | -200 to +100 | Degree requirement match |
| **Company Prestige** | 0-100 | FAANG (+100), Unicorns (+80), Major (+50) |
| **Salary** | 0-100 | $150k+ (100), $120k+ (80), $100k+ (50) |
| **Location** | 0-150 | Toronto/GTA (+150), Other Canada (+100) |
| **Remote** | 0-150 | Fully Remote (+150), Hybrid (+100) |

**Display**: Scores are shown as `/100` in emails and logs (divided by 10 for readability)

## 🗄️ Database Schema

SQLite database with star schema:

- **jobs**: Job listings (title, company, salary, location, remote)
- **resumes**: Resume metadata and text
- **sites**: Job source websites
- **job_applications**: Fact table (scores, analysis, email status)

## 📧 Email Notifications

The bot sends an HTML email with your top 5 job matches, including:
- Match score (displayed as /100)
- Salary range
- Location and remote status
- LLM reasoning for the match
- Direct application link

## 🔧 Command Line Options

```bash
python job_finder_bot.py [OPTIONS]

Options:
  --resume PATH          Path to specific resume PDF
  --auto                 Process all resumes in folder
  --min-score N          Minimum score to save (default: 600/1000)
  --high-threshold N     Email threshold (default: 800/1000)
  --workers N            LLM worker threads (default: 8)
```

## 📁 File Structure

```
JobFinderBot/
├── job_finder_bot.py       # Main bot script
├── database.py             # Database manager
├── simple_llm_chat.py      # LLM wrapper for Ollama
├── company_scraper.py      # Web scraping utilities
├── job_sources.json        # Job source configurations
├── config.yaml             # Your config (not in git)
├── config.example.yaml     # Template config
└── .gitignore              # Excludes sensitive data

../Resumes/                 # Your resume PDFs (outside repo)
../JobFinderBot_Logs/       # Reports and logs (outside repo)
../jobs_database.db         # SQLite database (outside repo)
```

## 🔒 Privacy & Security

The `.gitignore` file excludes:
- `config.yaml` (contains credentials)
- `*.db` files (personal job data)
- `*.pdf` files (resumes)
- Job reports and results
- Logs

**Never commit** your `config.yaml` or any personal data files!

## 🤝 Contributing

This is a personal project, but feel free to fork and customize for your needs.

## 📝 License

MIT License - See LICENSE file for details

## 🐛 Troubleshooting

**LLM not initializing?**
- Ensure Ollama is running: `ollama serve`
- Check model is downloaded: `ollama list`
- Pull model if missing: `ollama pull qwen2.5:3b`

**No jobs found?**
- Check job_sources.json is configured
- Verify internet connection
- Some sites (Indeed, LinkedIn) may block automation

**Email not sending?**
- Verify Gmail app password (not account password)
- Check config.yaml has correct credentials
- Ensure 2FA is enabled on Google account

**Database errors?**
- Delete old database: `rm ../jobs_database.db`
- It will recreate on next run

## 📚 Additional Documentation

- `QUICKSTART.md` - Quick setup guide
- `READY_TO_USE.md` - Usage instructions
- `ADDING_JOB_SOURCES.md` - Add new job sites
- `IMPLEMENTATION_STATUS.md` - Feature roadmap
