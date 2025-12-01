"""
Job Finder Bot GUI - Entry Point
Run this to launch the Job Finder configuration and search tool
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from job_finder.gui.main_window import MainWindow


def main():
    """Launch the Job Finder Bot GUI"""
    
    # Verify required files exist
    required_files = ['config.example.yaml', 'job_sources.json']
    missing_files = [f for f in required_files if not (project_root / f).exists()]
    
    if missing_files:
        messagebox.showerror(
            "Missing Files",
            f"Cannot start GUI - missing required files:\n{', '.join(missing_files)}\n\n"
            f"Please ensure you're running from the JobFinderBot directory."
        )
        sys.exit(1)
    
    # Create and run application
    root = tk.Tk()
    app = MainWindow(root)
    
    # Center window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'+{x}+{y}')
    
    root.mainloop()


if __name__ == "__main__":
    main()
