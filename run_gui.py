"""Job Finder Bot GUI - Entry Point"""
import tkinter as tk
from tkinter import ttk, messagebox
from gui.main_window import MainWindow
import sys
from pathlib import Path


def main():
    """Launch the Job Finder Bot GUI"""
    
    # Verify we're in the right directory
    required_files = ['job_finder_bot.py', 'config.example.yaml']
    missing_files = [f for f in required_files if not Path(f).exists()]
    
    if missing_files:
        messagebox.showerror(
            "Missing Files",
            f"Cannot start GUI - missing required files:\n{', '.join(missing_files)}\n\n"
            f"Please run this script from the JobFinderBot directory."
        )
        sys.exit(1)
    
    # Create and run application
    root = tk.Tk()
    app = MainWindow(root)
    
    # Center window
    root.update_idletasks()
    
    # Run application
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
