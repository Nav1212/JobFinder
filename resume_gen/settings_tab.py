"""
Settings Tab - Configuration editor for Resume Generator
Provides GUI editing for config.yaml settings
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import yaml


class SettingsTab(ttk.Frame):
    def __init__(self, parent, status_callback=None):
        super().__init__(parent, padding="15")
        self.status_callback = status_callback or (lambda msg: None)
        
        # Config file path
        self.config_path = Path(__file__).parent.parent / 'config.yaml'
        self.password_visible = False
        
        self.create_widgets()
        self.load_config()
    
    def create_widgets(self):
        """Create settings widgets"""
        # Scrollable canvas
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)
        
        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # ==================== Email Section ====================
        email_frame = ttk.LabelFrame(content_frame, text="📧 Email Configuration", padding="15")
        email_frame.pack(fill='x', pady=(0, 15), padx=5)
        
        # Email Address
        ttk.Label(email_frame, text="Gmail Address:").grid(row=0, column=0, sticky='w', pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=self.email_var, width=35).grid(
            row=0, column=1, columnspan=2, sticky='ew', padx=(10, 0), pady=5
        )
        
        # Password
        ttk.Label(email_frame, text="App Password:").grid(row=1, column=0, sticky='w', pady=5)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(email_frame, textvariable=self.password_var, show='*', width=35)
        self.password_entry.grid(row=1, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        self.show_btn = ttk.Button(email_frame, text="👁", width=3, command=self.toggle_password)
        self.show_btn.grid(row=1, column=2, padx=(5, 0), pady=5)
        
        # Help text
        help_label = ttk.Label(
            email_frame, 
            text="Get Gmail App Password: https://myaccount.google.com/apppasswords",
            foreground='blue',
            font=('Arial', 8)
        )
        help_label.grid(row=2, column=0, columnspan=3, sticky='w', pady=(5, 0))
        
        email_frame.columnconfigure(1, weight=1)
        
        # ==================== Paths Section ====================
        paths_frame = ttk.LabelFrame(content_frame, text="📁 File Paths", padding="15")
        paths_frame.pack(fill='x', pady=(0, 15), padx=5)
        
        # Resumes Directory
        ttk.Label(paths_frame, text="Resumes Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.resumes_var = tk.StringVar()
        ttk.Entry(paths_frame, textvariable=self.resumes_var, width=35).grid(
            row=0, column=1, sticky='ew', padx=(10, 5), pady=5
        )
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_folder(self.resumes_var)).grid(
            row=0, column=2, pady=5
        )
        
        # Database Path
        ttk.Label(paths_frame, text="Database File:").grid(row=1, column=0, sticky='w', pady=5)
        self.database_var = tk.StringVar()
        ttk.Entry(paths_frame, textvariable=self.database_var, width=35).grid(
            row=1, column=1, sticky='ew', padx=(10, 5), pady=5
        )
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_file(self.database_var)).grid(
            row=1, column=2, pady=5
        )
        
        # Logs Directory
        ttk.Label(paths_frame, text="Logs Folder:").grid(row=2, column=0, sticky='w', pady=5)
        self.logs_var = tk.StringVar()
        ttk.Entry(paths_frame, textvariable=self.logs_var, width=35).grid(
            row=2, column=1, sticky='ew', padx=(10, 5), pady=5
        )
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_folder(self.logs_var)).grid(
            row=2, column=2, pady=5
        )
        
        # RAG Indexes Directory
        ttk.Label(paths_frame, text="RAG Indexes:").grid(row=3, column=0, sticky='w', pady=5)
        self.rag_var = tk.StringVar()
        ttk.Entry(paths_frame, textvariable=self.rag_var, width=35).grid(
            row=3, column=1, sticky='ew', padx=(10, 5), pady=5
        )
        ttk.Button(paths_frame, text="Browse", command=lambda: self.browse_folder(self.rag_var)).grid(
            row=3, column=2, pady=5
        )
        
        paths_frame.columnconfigure(1, weight=1)
        
        # ==================== RAG Settings Section ====================
        rag_frame = ttk.LabelFrame(content_frame, text="🧠 RAG Settings", padding="15")
        rag_frame.pack(fill='x', pady=(0, 15), padx=5)
        
        # Embedding Model
        ttk.Label(rag_frame, text="Embedding Model:").grid(row=0, column=0, sticky='w', pady=5)
        self.embedding_model_var = tk.StringVar()
        model_combo = ttk.Combobox(
            rag_frame, 
            textvariable=self.embedding_model_var, 
            width=25,
            values=["mxbai-embed-large", "nomic-embed-text", "all-minilm"]
        )
        model_combo.grid(row=0, column=1, sticky='w', padx=(10, 0), pady=5)
        
        # Similarity Threshold
        ttk.Label(rag_frame, text="Similarity Threshold:").grid(row=1, column=0, sticky='w', pady=5)
        self.similarity_var = tk.DoubleVar(value=0.85)
        threshold_frame = ttk.Frame(rag_frame)
        threshold_frame.grid(row=1, column=1, sticky='w', padx=(10, 0), pady=5)
        
        self.threshold_scale = ttk.Scale(
            threshold_frame, 
            from_=0.5, 
            to=1.0, 
            variable=self.similarity_var,
            orient='horizontal',
            length=150,
            command=lambda v: self.threshold_label.config(text=f"{float(v):.2f}")
        )
        self.threshold_scale.pack(side='left')
        self.threshold_label = ttk.Label(threshold_frame, text="0.85", width=5)
        self.threshold_label.pack(side='left', padx=(5, 0))
        
        # Top K
        ttk.Label(rag_frame, text="Top K Results:").grid(row=2, column=0, sticky='w', pady=5)
        self.topk_var = tk.IntVar(value=10)
        ttk.Spinbox(rag_frame, textvariable=self.topk_var, from_=1, to=50, width=10).grid(
            row=2, column=1, sticky='w', padx=(10, 0), pady=5
        )
        
        # Help text
        ttk.Label(
            rag_frame,
            text="RAG settings control duplicate detection and sentence matching",
            foreground='gray',
            font=('Arial', 8)
        ).grid(row=3, column=0, columnspan=2, sticky='w', pady=(10, 0))
        
        rag_frame.columnconfigure(1, weight=1)
        
        # ==================== Action Buttons ====================
        btn_frame = ttk.Frame(content_frame)
        btn_frame.pack(fill='x', pady=(15, 0), padx=5)
        
        ttk.Button(btn_frame, text="💾 Save Settings", command=self.save_config).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="🔄 Reload", command=self.load_config).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="↩️ Reset to Defaults", command=self.reset_defaults).pack(side='left')
    
    def toggle_password(self):
        """Toggle password visibility"""
        if self.password_visible:
            self.password_entry.config(show='*')
            self.show_btn.config(text='👁')
            self.password_visible = False
        else:
            self.password_entry.config(show='')
            self.show_btn.config(text='🙈')
            self.password_visible = True
    
    def browse_folder(self, var):
        """Open folder browser"""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            # Try to make relative path
            try:
                base = self.config_path.parent
                rel = Path(folder).relative_to(base.parent)
                var.set(f"../{rel}")
            except ValueError:
                var.set(folder)
    
    def browse_file(self, var):
        """Open file browser"""
        file = filedialog.asksaveasfilename(
            title="Select File",
            filetypes=[("Database", "*.db"), ("All Files", "*.*")]
        )
        if file:
            try:
                base = self.config_path.parent
                rel = Path(file).relative_to(base.parent)
                var.set(f"../{rel}")
            except ValueError:
                var.set(file)
    
    def load_config(self):
        """Load config.yaml"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                
                # Email
                email = config.get('email', {})
                self.email_var.set(email.get('sender', ''))
                self.password_var.set(email.get('password', ''))
                
                # Paths
                paths = config.get('paths', {})
                self.resumes_var.set(paths.get('resumes_dir', '../Resumes'))
                self.database_var.set(paths.get('database', '../jobs_database.db'))
                self.logs_var.set(paths.get('logs_dir', '../JobFinderBot_Logs'))
                self.rag_var.set(paths.get('rag_indexes_dir', 'resume_gen/indexes'))
                
                # RAG
                rag = config.get('rag', {})
                self.embedding_model_var.set(rag.get('embedding_model', 'mxbai-embed-large'))
                self.similarity_var.set(rag.get('similarity_threshold', 0.85))
                self.topk_var.set(rag.get('top_k', 10))
                
                # Update threshold label
                self.threshold_label.config(text=f"{self.similarity_var.get():.2f}")
                
                self.status_callback("Settings loaded")
            else:
                self.reset_defaults()
                self.status_callback("No config found - using defaults")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config:\n{e}")
    
    def save_config(self):
        """Save settings to config.yaml"""
        try:
            # Load existing config to preserve any extra fields
            existing = {}
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    existing = yaml.safe_load(f) or {}
            
            # Update with GUI values
            config = {
                'email': {
                    'sender': self.email_var.get(),
                    'password': self.password_var.get()
                },
                'paths': {
                    'resumes_dir': self.resumes_var.get(),
                    'database': self.database_var.get(),
                    'logs_dir': self.logs_var.get(),
                    'rag_indexes_dir': self.rag_var.get()
                },
                'rag': {
                    'embedding_model': self.embedding_model_var.get(),
                    'similarity_threshold': round(self.similarity_var.get(), 2),
                    'top_k': self.topk_var.get()
                }
            }
            
            # Merge with existing (preserve unknown keys)
            for key in existing:
                if key not in config:
                    config[key] = existing[key]
            
            # Write with comment
            with open(self.config_path, 'w') as f:
                f.write("# Job Finder Bot Configuration\n\n")
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            messagebox.showinfo("Success", "Settings saved successfully!")
            self.status_callback("Settings saved")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config:\n{e}")
    
    def reset_defaults(self):
        """Reset to default values"""
        self.email_var.set('')
        self.password_var.set('')
        self.resumes_var.set('../Resumes')
        self.database_var.set('../jobs_database.db')
        self.logs_var.set('../JobFinderBot_Logs')
        self.rag_var.set('resume_gen/indexes')
        self.embedding_model_var.set('mxbai-embed-large')
        self.similarity_var.set(0.85)
        self.topk_var.set(10)
        self.threshold_label.config(text="0.85")
        self.status_callback("Reset to defaults")
