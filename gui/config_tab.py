"""Configuration Tab - Email and Path Settings"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import yaml
import smtplib
from email.mime.text import MIMEText


class ConfigTab:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.config_path = Path(__file__).parent.parent / 'config.yaml'
        self.password_visible = False
        
        # Create main frame
        self.frame = ttk.Frame(parent, padding="20")
        
        # Create scrollable canvas for content
        canvas = tk.Canvas(self.frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        self.content_frame = ttk.Frame(canvas)
        
        self.content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.create_widgets()
        self.load_config()
    
    def create_widgets(self):
        """Create all configuration widgets"""
        
        # Email Configuration Section
        email_frame = ttk.LabelFrame(self.content_frame, text="Email Configuration", padding="15")
        email_frame.pack(fill='x', pady=(0, 15))
        
        # Email Address
        ttk.Label(email_frame, text="Gmail Address:").grid(row=0, column=0, sticky='w', pady=5)
        self.email_var = tk.StringVar()
        email_entry = ttk.Entry(email_frame, textvariable=self.email_var, width=40)
        email_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=(10, 0), pady=5)
        
        # Password (masked)
        ttk.Label(email_frame, text="App Password:").grid(row=1, column=0, sticky='w', pady=5)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(email_frame, textvariable=self.password_var, show='*', width=40)
        self.password_entry.grid(row=1, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        # Show/Hide password button
        self.show_btn = ttk.Button(email_frame, text="👁", width=3, command=self.toggle_password)
        self.show_btn.grid(row=1, column=2, padx=(5, 0), pady=5)
        
        # Test Email button
        test_btn = ttk.Button(email_frame, text="Test Email Connection", command=self.test_email)
        test_btn.grid(row=2, column=1, sticky='w', padx=(10, 0), pady=(10, 0))
        
        # Help text
        help_text = ttk.Label(
            email_frame, 
            text="Get Gmail App Password: https://myaccount.google.com/apppasswords",
            foreground='blue',
            cursor='hand2',
            font=('Arial', 8)
        )
        help_text.grid(row=3, column=0, columnspan=3, sticky='w', pady=(5, 0))
        help_text.bind('<Button-1>', lambda e: self.open_url('https://myaccount.google.com/apppasswords'))
        
        email_frame.columnconfigure(1, weight=1)
        
        # Paths Configuration Section
        paths_frame = ttk.LabelFrame(self.content_frame, text="File Paths", padding="15")
        paths_frame.pack(fill='x', pady=(0, 15))
        
        # Resumes Directory
        ttk.Label(paths_frame, text="Resumes Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.resumes_var = tk.StringVar()
        resumes_entry = ttk.Entry(paths_frame, textvariable=self.resumes_var, width=40)
        resumes_entry.grid(row=0, column=1, sticky='ew', padx=(10, 5), pady=5)
        ttk.Button(paths_frame, text="Browse...", command=lambda: self.browse_folder(self.resumes_var)).grid(row=0, column=2, pady=5)
        
        # Database Path
        ttk.Label(paths_frame, text="Database File:").grid(row=1, column=0, sticky='w', pady=5)
        self.database_var = tk.StringVar()
        db_entry = ttk.Entry(paths_frame, textvariable=self.database_var, width=40)
        db_entry.grid(row=1, column=1, sticky='ew', padx=(10, 5), pady=5)
        ttk.Button(paths_frame, text="Browse...", command=lambda: self.browse_file(self.database_var, [("Database", "*.db"), ("All Files", "*.*")])).grid(row=1, column=2, pady=5)
        
        # Logs Directory
        ttk.Label(paths_frame, text="Logs Folder:").grid(row=2, column=0, sticky='w', pady=5)
        self.logs_var = tk.StringVar()
        logs_entry = ttk.Entry(paths_frame, textvariable=self.logs_var, width=40)
        logs_entry.grid(row=2, column=1, sticky='ew', padx=(10, 5), pady=5)
        ttk.Button(paths_frame, text="Browse...", command=lambda: self.browse_folder(self.logs_var)).grid(row=2, column=2, pady=5)
        
        paths_frame.columnconfigure(1, weight=1)
        
        # Action Buttons
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(btn_frame, text="Save Configuration", command=self.save_config, style='Accent.TButton').pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Reset to Default", command=self.reset_config).pack(side='left')
    
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
        """Open folder browser dialog"""
        initial_dir = var.get() or str(Path.home())
        folder = filedialog.askdirectory(initialdir=initial_dir, title="Select Folder")
        if folder:
            # Convert to relative path if possible
            try:
                base_path = Path(__file__).parent.parent
                rel_path = Path(folder).relative_to(base_path.parent)
                var.set(f"../{rel_path}")
            except ValueError:
                var.set(folder)
    
    def browse_file(self, var, filetypes):
        """Open file browser dialog"""
        initial_dir = Path(var.get()).parent if var.get() else Path.home()
        file = filedialog.asksaveasfilename(initialdir=initial_dir, title="Select File", filetypes=filetypes)
        if file:
            # Convert to relative path if possible
            try:
                base_path = Path(__file__).parent.parent
                rel_path = Path(file).relative_to(base_path.parent)
                var.set(f"../{rel_path}")
            except ValueError:
                var.set(file)
    
    def load_config(self):
        """Load config.yaml into fields"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                self.email_var.set(config.get('email', {}).get('sender', ''))
                self.password_var.set(config.get('email', {}).get('password', ''))
                self.resumes_var.set(config.get('paths', {}).get('resumes_dir', '../Resumes'))
                self.database_var.set(config.get('paths', {}).get('database', '../jobs_database.db'))
                self.logs_var.set(config.get('paths', {}).get('logs_dir', '../JobFinderBot_Logs'))
                
                self.main_window.set_status("Configuration loaded", 'success')
            else:
                # Set defaults
                self.resumes_var.set('../Resumes')
                self.database_var.set('../jobs_database.db')
                self.logs_var.set('../JobFinderBot_Logs')
                self.main_window.set_status("No config found - using defaults", 'warning')
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load config:\n{e}")
    
    def save_config(self):
        """Save fields to config.yaml"""
        try:
            config = {
                'email': {
                    'sender': self.email_var.get(),
                    'password': self.password_var.get()
                },
                'paths': {
                    'resumes_dir': self.resumes_var.get(),
                    'database': self.database_var.get(),
                    'logs_dir': self.logs_var.get()
                }
            }
            
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            messagebox.showinfo("Success", "Configuration saved successfully!")
            self.main_window.set_status("Configuration saved", 'success')
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save config:\n{e}")
            self.main_window.set_status("Save failed", 'error')
    
    def test_email(self):
        """Test email connection"""
        email = self.email_var.get()
        password = self.password_var.get()
        
        if not email or not password:
            messagebox.showwarning("Missing Info", "Please enter both email and password")
            return
        
        try:
            self.main_window.set_status("Testing email connection...", 'info')
            
            # Create test message
            msg = MIMEText("Test email from JobFinder Bot Configuration Tool")
            msg['Subject'] = "JobFinder Bot - Test Email"
            msg['From'] = email
            msg['To'] = email
            
            # Send via Gmail SMTP
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(email, password)
                server.send_message(msg)
            
            messagebox.showinfo("Success", f"Test email sent successfully to {email}!\nCheck your inbox.")
            self.main_window.set_status("Email test successful", 'success')
        except Exception as e:
            messagebox.showerror("Email Error", f"Failed to send test email:\n{e}\n\nMake sure:\n- 2FA is enabled\n- You're using an App Password\n- Password has no spaces")
            self.main_window.set_status("Email test failed", 'error')
    
    def reset_config(self):
        """Reset to default values"""
        if messagebox.askyesno("Reset", "Reset all configuration to defaults?"):
            self.email_var.set('')
            self.password_var.set('')
            self.resumes_var.set('../Resumes')
            self.database_var.set('../jobs_database.db')
            self.logs_var.set('../JobFinderBot_Logs')
            self.main_window.set_status("Configuration reset to defaults", 'info')
    
    def open_url(self, url):
        """Open URL in browser"""
        import webbrowser
        webbrowser.open(url)
