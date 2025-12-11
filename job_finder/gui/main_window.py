"""Main GUI Window with Tabs"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from job_finder.gui.config_tab import ConfigTab
from job_finder.gui.resumes_tab import ResumesTab
from job_finder.gui.sources_tab import SourcesTab
from job_finder.gui.run_tab import RunTab


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("JobFinder Bot - Configuration Tool")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Main container
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Title
        title = ttk.Label(
            main_frame, 
            text="JobFinder Bot Configuration", 
            font=('Arial', 16, 'bold')
        )
        title.pack(pady=(0, 10))
        
        # Status bar (create BEFORE tabs so set_status() works during tab initialization)
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.pack(side='bottom', fill='x', pady=(10, 0))
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Ready", 
            relief=tk.SUNKEN, 
            anchor='w',
            padding="5"
        )
        self.status_label.pack(fill='x')
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Initialize tabs
        self.config_tab = ConfigTab(self.notebook, self)
        self.resumes_tab = ResumesTab(self.notebook, self)
        self.sources_tab = SourcesTab(self.notebook, self)
        self.run_tab = RunTab(self.notebook, self)
        
        # Add tabs to notebook
        self.notebook.add(self.config_tab.frame, text="Setup")
        self.notebook.add(self.resumes_tab.frame, text="Resumes")
        self.notebook.add(self.sources_tab.frame, text="Job Sources")
        self.notebook.add(self.run_tab.frame, text="Run")
        
        # Center window on screen
        self.center_window()
    
    def center_window(self):
        """Center the window on the screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def set_status(self, message, status_type='info'):
        """Update status bar
        
        Args:
            message: Status message to display
            status_type: 'info', 'success', 'error', 'warning'
        """
        colors = {
            'info': '#2196F3',
            'success': '#4CAF50',
            'error': '#F44336',
            'warning': '#FF9800'
        }
        
        self.status_label.config(text=message)
        # Change background color temporarily
        bg_color = colors.get(status_type, '#2196F3')
        self.status_label.config(background=bg_color, foreground='white')
        
        # Reset to default after 3 seconds
        if status_type != 'info':
            self.root.after(3000, lambda: self.status_label.config(
                background='SystemButtonFace', 
                foreground='black'
            ))


def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
