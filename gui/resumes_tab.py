"""Resumes Management Tab"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import shutil
import PyPDF2


class ResumesTab:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.resumes_dir = Path(__file__).parent.parent.parent / 'Resumes'
        
        # Create main frame
        self.frame = ttk.Frame(parent, padding="20")
        
        self.create_widgets()
        self.refresh_resumes()
    
    def create_widgets(self):
        """Create resume management widgets"""
        
        # Title and info
        title_frame = ttk.Frame(self.frame)
        title_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(
            title_frame, 
            text="Manage Your Resumes",
            font=('Arial', 12, 'bold')
        ).pack(side='left')
        
        ttk.Label(
            title_frame,
            text=f"Location: {self.resumes_dir}",
            foreground='gray',
            font=('Arial', 9)
        ).pack(side='right')
        
        # Resumes list section
        list_frame = ttk.LabelFrame(self.frame, text="Available Resumes", padding="10")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Create treeview for resumes
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill='both', expand=True)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side='right', fill='y')
        
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.pack(side='bottom', fill='x')
        
        # Treeview
        self.tree = ttk.Treeview(
            tree_frame,
            columns=('name', 'size', 'modified'),
            show='headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode='browse'
        )
        
        self.tree.heading('name', text='Resume Name')
        self.tree.heading('size', text='Size')
        self.tree.heading('modified', text='Last Modified')
        
        self.tree.column('name', width=300)
        self.tree.column('size', width=80)
        self.tree.column('modified', width=150)
        
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        self.tree.pack(fill='both', expand=True)
        
        # Double-click to preview
        self.tree.bind('<Double-1>', lambda e: self.preview_resume())
        
        # Action buttons
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill='x')
        
        ttk.Button(btn_frame, text="➕ Add Resume", command=self.add_resume).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="🗑️ Remove", command=self.remove_resume).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="👁️ Preview", command=self.preview_resume).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🔄 Refresh", command=self.refresh_resumes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="📂 Open Folder", command=self.open_folder).pack(side='right')
    
    def refresh_resumes(self):
        """Refresh the list of resumes"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Ensure directory exists
        self.resumes_dir.mkdir(parents=True, exist_ok=True)
        
        # Load resumes
        resumes = list(self.resumes_dir.glob('*.pdf'))
        
        if not resumes:
            self.tree.insert('', 'end', values=('No resumes found', '', ''))
            self.main_window.set_status(f"No resumes in {self.resumes_dir}", 'warning')
            return
        
        for resume in sorted(resumes):
            stat = resume.stat()
            size_kb = stat.st_size / 1024
            modified = Path(resume).stat().st_mtime
            from datetime import datetime
            modified_str = datetime.fromtimestamp(modified).strftime('%Y-%m-%d %H:%M')
            
            self.tree.insert('', 'end', values=(
                resume.name,
                f"{size_kb:.1f} KB",
                modified_str
            ))
        
        self.main_window.set_status(f"Found {len(resumes)} resume(s)", 'success')
    
    def add_resume(self):
        """Add a new resume via file picker"""
        file_path = filedialog.askopenfilename(
            title="Select Resume PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            initialdir=Path.home() / "Documents"
        )
        
        if not file_path:
            return
        
        source = Path(file_path)
        
        # Validate it's a PDF
        if source.suffix.lower() != '.pdf':
            messagebox.showwarning("Invalid File", "Please select a PDF file")
            return
        
        # Check if already exists
        dest = self.resumes_dir / source.name
        if dest.exists():
            if not messagebox.askyesno("File Exists", f"{source.name} already exists.\n\nOverwrite?"):
                return
        
        try:
            # Copy to resumes directory
            shutil.copy2(source, dest)
            messagebox.showinfo("Success", f"Resume added: {source.name}")
            self.refresh_resumes()
            self.main_window.set_status(f"Added resume: {source.name}", 'success')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add resume:\n{e}")
            self.main_window.set_status("Failed to add resume", 'error')
    
    def remove_resume(self):
        """Remove selected resume"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a resume to remove")
            return
        
        item = self.tree.item(selection[0])
        resume_name = item['values'][0]
        
        if resume_name == 'No resumes found':
            return
        
        if not messagebox.askyesno("Confirm Delete", f"Delete {resume_name}?"):
            return
        
        try:
            resume_path = self.resumes_dir / resume_name
            resume_path.unlink()
            messagebox.showinfo("Deleted", f"Removed: {resume_name}")
            self.refresh_resumes()
            self.main_window.set_status(f"Removed resume: {resume_name}", 'success')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove resume:\n{e}")
            self.main_window.set_status("Failed to remove resume", 'error')
    
    def preview_resume(self):
        """Preview selected resume text"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a resume to preview")
            return
        
        item = self.tree.item(selection[0])
        resume_name = item['values'][0]
        
        if resume_name == 'No resumes found':
            return
        
        try:
            resume_path = self.resumes_dir / resume_name
            
            # Extract text from PDF
            with open(resume_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
            
            # Create preview window
            preview_window = tk.Toplevel(self.frame)
            preview_window.title(f"Preview: {resume_name}")
            preview_window.geometry("700x600")
            
            # Title
            ttk.Label(
                preview_window,
                text=f"📄 {resume_name}",
                font=('Arial', 12, 'bold'),
                padding=10
            ).pack()
            
            # Text widget with scrollbar
            text_frame = ttk.Frame(preview_window)
            text_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            text_widget = scrolledtext.ScrolledText(
                text_frame,
                wrap=tk.WORD,
                font=('Consolas', 10)
            )
            text_widget.pack(fill='both', expand=True)
            text_widget.insert('1.0', text)
            text_widget.config(state='disabled')
            
            # Close button
            ttk.Button(
                preview_window,
                text="Close",
                command=preview_window.destroy
            ).pack(pady=(0, 10))
            
        except Exception as e:
            messagebox.showerror("Preview Error", f"Failed to preview resume:\n{e}")
    
    def open_folder(self):
        """Open resumes folder in file explorer"""
        import subprocess
        import sys
        
        try:
            if sys.platform == 'win32':
                subprocess.run(['explorer', str(self.resumes_dir)])
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(self.resumes_dir)])
            else:  # Linux
                subprocess.run(['xdg-open', str(self.resumes_dir)])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder:\n{e}")
