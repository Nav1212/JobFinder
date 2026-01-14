"""
Resume Generator GUI - Entry Point
Run this to launch the Resume Generator with multi-user support
"""
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.simpledialog
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from resume_gen.run_gui import ResumeGeneratorGUI


def main():
    """Launch the Resume Generator GUI"""
    root = tk.Tk()
    app = ResumeGeneratorGUI(root)
    
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
