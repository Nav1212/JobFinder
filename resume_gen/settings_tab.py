"""
Settings Tab - Configuration editor for Resume Generator
Provides GUI editing for config.yaml settings
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import yaml
import threading
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.model_manager import get_model_manager, ModelType, KNOWN_MODELS


class SettingsTab(ttk.Frame):
    def __init__(self, parent, status_callback=None):
        super().__init__(parent, padding="15")
        self.status_callback = status_callback or (lambda msg: None)
        
        # Config file path
        self.config_path = Path(__file__).parent.parent / 'config.yaml'
        self.password_visible = False
        self.model_manager = get_model_manager()
        
        # Track installing models
        self._installing = False
        
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
        
        # ==================== LLM Models Section ====================
        models_frame = ttk.LabelFrame(content_frame, text="🤖 LLM Models", padding="15")
        models_frame.pack(fill='x', pady=(0, 15), padx=5)
        
        # Get available models
        gen_models = [info.name for info in KNOWN_MODELS.values() if info.model_type == ModelType.GENERATION]
        
        # Parsing Model
        ttk.Label(models_frame, text="Parsing Model:").grid(row=0, column=0, sticky='w', pady=5)
        self.parsing_model_var = tk.StringVar()
        self.parsing_combo = ttk.Combobox(
            models_frame, 
            textvariable=self.parsing_model_var, 
            width=20,
            values=gen_models
        )
        self.parsing_combo.grid(row=0, column=1, sticky='w', padx=(10, 0), pady=5)
        self.parsing_combo.bind('<<ComboboxSelected>>', lambda e: self._on_model_selected('parsing'))
        self.parsing_status = ttk.Label(models_frame, text="", width=3)
        self.parsing_status.grid(row=0, column=2, padx=(5, 0), pady=5)
        
        ttk.Label(
            models_frame, 
            text="Small model for sentence extraction (fast)",
            foreground='gray',
            font=('Arial', 8)
        ).grid(row=0, column=3, sticky='w', padx=(10, 0), pady=5)
        
        # Grading Model
        ttk.Label(models_frame, text="Grading Model:").grid(row=1, column=0, sticky='w', pady=5)
        self.grading_model_var = tk.StringVar()
        self.grading_combo = ttk.Combobox(
            models_frame, 
            textvariable=self.grading_model_var, 
            width=20,
            values=gen_models
        )
        self.grading_combo.grid(row=1, column=1, sticky='w', padx=(10, 0), pady=5)
        self.grading_combo.bind('<<ComboboxSelected>>', lambda e: self._on_model_selected('grading'))
        self.grading_status = ttk.Label(models_frame, text="", width=3)
        self.grading_status.grid(row=1, column=2, padx=(5, 0), pady=5)
        
        ttk.Label(
            models_frame, 
            text="Medium model for scoring sentences",
            foreground='gray',
            font=('Arial', 8)
        ).grid(row=1, column=3, sticky='w', padx=(10, 0), pady=5)
        
        # Polishing Model
        ttk.Label(models_frame, text="Polishing Model:").grid(row=2, column=0, sticky='w', pady=5)
        self.polishing_model_var = tk.StringVar()
        self.polishing_combo = ttk.Combobox(
            models_frame, 
            textvariable=self.polishing_model_var, 
            width=20,
            values=gen_models
        )
        self.polishing_combo.grid(row=2, column=1, sticky='w', padx=(10, 0), pady=5)
        self.polishing_combo.bind('<<ComboboxSelected>>', lambda e: self._on_model_selected('polishing'))
        self.polishing_status = ttk.Label(models_frame, text="", width=3)
        self.polishing_status.grid(row=2, column=2, padx=(5, 0), pady=5)
        
        ttk.Label(
            models_frame, 
            text="Larger model for rewriting text",
            foreground='gray',
            font=('Arial', 8)
        ).grid(row=2, column=3, sticky='w', padx=(10, 0), pady=5)
        
        # Warning frame for same model
        self.same_model_warning = ttk.Frame(models_frame)
        self.same_model_warning.grid(row=3, column=0, columnspan=4, sticky='w', pady=(10, 0))
        
        self.warning_icon = ttk.Label(
            self.same_model_warning, 
            text="⚠️", 
            foreground='orange',
            font=('Arial', 12)
        )
        self.warning_icon.pack(side='left')
        
        self.warning_label = ttk.Label(
            self.same_model_warning,
            text="Grading and Polishing use the same model",
            foreground='orange',
            font=('Arial', 9)
        )
        self.warning_label.pack(side='left', padx=(5, 0))
        
        # Tooltip on hover
        self.warning_tooltip = (
            "Using the same model for grading and polishing can be suboptimal:\n"
            "• Grading needs consistent scoring (medium model works well)\n"
            "• Polishing benefits from larger models for better rewrites\n"
            "• Different models reduce bias in evaluation"
        )
        self.warning_icon.bind('<Enter>', self._show_warning_tooltip)
        self.warning_icon.bind('<Leave>', self._hide_warning_tooltip)
        self.warning_label.bind('<Enter>', self._show_warning_tooltip)
        self.warning_label.bind('<Leave>', self._hide_warning_tooltip)
        
        # Initially hide warning
        self.same_model_warning.grid_remove()
        
        # Ollama URL
        ttk.Label(models_frame, text="Ollama URL:").grid(row=4, column=0, sticky='w', pady=(15, 5))
        self.ollama_url_var = tk.StringVar(value="http://localhost:11434")
        ttk.Entry(models_frame, textvariable=self.ollama_url_var, width=30).grid(
            row=4, column=1, columnspan=2, sticky='w', padx=(10, 0), pady=(15, 5)
        )
        
        # Check Ollama status button
        ttk.Button(
            models_frame, 
            text="🔍 Check Models", 
            command=self._refresh_model_status
        ).grid(row=4, column=3, sticky='w', padx=(10, 0), pady=(15, 5))
        
        models_frame.columnconfigure(3, weight=1)
        
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
                
                # Models
                models = config.get('models', {})
                self.parsing_model_var.set(models.get('parsing_model', 'llama3.2:1b'))
                self.grading_model_var.set(models.get('grading_model', 'llama3.1:8b'))
                self.polishing_model_var.set(models.get('polishing_model', 'llama3.1:8b'))
                self.ollama_url_var.set(models.get('ollama_url', 'http://localhost:11434'))
                
                # Update threshold label
                self.threshold_label.config(text=f"{self.similarity_var.get():.2f}")
                
                # Update model status and warning
                self._refresh_model_status()
                self._check_same_model_warning()
                
                self.status_callback("Settings loaded")
            else:
                self.reset_defaults()
                self.status_callback("No config found - using defaults")
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load config:\n{e}\n\nCheck console for details.")
    
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
                },
                'models': {
                    'parsing_model': self.parsing_model_var.get(),
                    'grading_model': self.grading_model_var.get(),
                    'polishing_model': self.polishing_model_var.get(),
                    'ollama_url': self.ollama_url_var.get()
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
        
        # Model defaults
        self.parsing_model_var.set('llama3.2:1b')
        self.grading_model_var.set('llama3.1:8b')
        self.polishing_model_var.set('llama3.1:8b')
        self.ollama_url_var.set('http://localhost:11434')
        
        self._check_same_model_warning()
        self.status_callback("Reset to defaults")
    
    # ==================== Model Management Methods ====================
    
    def _on_model_selected(self, model_type: str):
        """Handle model selection from combobox"""
        if model_type == 'parsing':
            model = self.parsing_model_var.get()
        elif model_type == 'grading':
            model = self.grading_model_var.get()
        else:
            model = self.polishing_model_var.get()
        
        # Check if model is installed
        if not self.model_manager.is_model_installed(model):
            self._prompt_install_model(model, model_type)
        else:
            self._update_model_status(model_type, installed=True)
        
        # Check same model warning
        self._check_same_model_warning()
    
    def _prompt_install_model(self, model: str, model_type: str):
        """Prompt user to install a model that's not installed"""
        info = self.model_manager.get_model_info(model)
        
        if info:
            size_str = info.size_display()
            desc = info.description
            msg = f"Model '{model}' is not installed.\n\n{desc}\nSize: {size_str}\n\nDo you want to install it now?"
        else:
            msg = f"Model '{model}' is not installed.\n\nDo you want to install it now?"
        
        if messagebox.askyesno("Install Model", msg):
            self._install_model(model, model_type)
        else:
            self._update_model_status(model_type, installed=False)
    
    def _install_model(self, model: str, model_type: str):
        """Install a model in background"""
        if self._installing:
            messagebox.showinfo("Please Wait", "Another model is currently installing.")
            return
        
        self._installing = True
        self._update_model_status(model_type, installing=True)
        self.status_callback(f"Installing {model}...")
        
        # Create progress window
        progress_win = tk.Toplevel(self)
        progress_win.title(f"Installing {model}")
        progress_win.geometry("400x150")
        progress_win.resizable(False, False)
        
        ttk.Label(progress_win, text=f"Installing {model}...", font=('Arial', 10, 'bold')).pack(pady=10)
        
        progress_text = tk.Text(progress_win, height=5, width=50, state='disabled')
        progress_text.pack(pady=5, padx=10, fill='both', expand=True)
        
        def on_progress(msg):
            # Thread-safe UI update
            def update():
                try:
                    if progress_win.winfo_exists():
                        progress_text.config(state='normal')
                        progress_text.insert('end', msg + '\n')
                        progress_text.see('end')
                        progress_text.config(state='disabled')
                except:
                    pass
            self.after(0, update)
        
        def on_complete(success, msg):
            # Thread-safe UI update
            def finish():
                self._installing = False
                try:
                    if success:
                        self._update_model_status(model_type, installed=True)
                        self.status_callback(f"Installed {model}")
                        # Refresh cache after successful install
                        self.model_manager._installed_cache = None
                        messagebox.showinfo("Success", msg)
                    else:
                        self._update_model_status(model_type, installed=False)
                        self.status_callback(f"Failed to install {model}")
                        messagebox.showerror("Installation Failed", msg)
                    
                    if progress_win.winfo_exists():
                        progress_win.destroy()
                except Exception as e:
                    print(f"Error in install completion: {e}")
            self.after(0, finish)
        
        # Start installation in background
        self.model_manager.install_model(model, on_progress, on_complete)
    
    def _update_model_status(self, model_type: str, installed: bool = None, installing: bool = False):
        """Update the status indicator for a model"""
        if model_type == 'parsing':
            label = self.parsing_status
        elif model_type == 'grading':
            label = self.grading_status
        else:
            label = self.polishing_status
        
        if installing:
            label.config(text="⏳", foreground='blue')
        elif installed:
            label.config(text="✓", foreground='green')
        elif installed is False:
            label.config(text="✗", foreground='red')
        else:
            label.config(text="")
    
    def _refresh_model_status(self):
        """Refresh status indicators for all models"""
        self.model_manager._installed_cache = None  # Force refresh
        
        if not self.model_manager.is_ollama_running():
            self.status_callback("Ollama is not running")
            self._update_model_status('parsing', installed=False)
            self._update_model_status('grading', installed=False)
            self._update_model_status('polishing', installed=False)
            messagebox.showwarning("Ollama Not Running", 
                "Ollama server is not running.\nStart it with: ollama serve")
            return
        
        # Check each model
        for model_type, var in [
            ('parsing', self.parsing_model_var),
            ('grading', self.grading_model_var),
            ('polishing', self.polishing_model_var)
        ]:
            model = var.get()
            installed = self.model_manager.is_model_installed(model)
            self._update_model_status(model_type, installed=installed)
        
        # Check embedding model too
        emb_model = self.embedding_model_var.get()
        if not self.model_manager.is_model_installed(emb_model):
            self.status_callback(f"Embedding model {emb_model} not installed")
        
        self.status_callback("Model status refreshed")
    
    def _check_same_model_warning(self):
        """Show/hide warning if grading and polishing use same model"""
        grading = self.grading_model_var.get()
        polishing = self.polishing_model_var.get()
        
        if grading and polishing and grading == polishing:
            self.same_model_warning.grid()
        else:
            self.same_model_warning.grid_remove()
    
    def _show_warning_tooltip(self, event):
        """Show tooltip on hover"""
        x, y, _, _ = self.warning_icon.bbox("insert") if hasattr(self.warning_icon, 'bbox') else (0, 0, 0, 0)
        x += self.warning_icon.winfo_rootx() + 25
        y += self.warning_icon.winfo_rooty() + 25
        
        self._tooltip = tk.Toplevel(self)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.wm_geometry(f"+{x}+{y}")
        
        label = ttk.Label(
            self._tooltip, 
            text=self.warning_tooltip,
            background='lightyellow',
            relief='solid',
            borderwidth=1,
            padding=5,
            font=('Arial', 9)
        )
        label.pack()
    
    def _hide_warning_tooltip(self, event):
        """Hide tooltip"""
        if hasattr(self, '_tooltip') and self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None
