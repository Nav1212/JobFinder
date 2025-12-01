"""Run Tab - Execute Job Finder Bot"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import subprocess
import threading
import queue
import sys
import os


class RunTab:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.bot_script = Path(__file__).parent.parent / 'job_finder_bot.py'
        self.process = None
        self.output_queue = queue.Queue()
        self.is_running = False
        
        # Create main frame
        self.frame = ttk.Frame(parent, padding="20")
        
        # Register cleanup on widget destroy
        self.frame.bind('<Destroy>', self._on_destroy)
        
        self.create_widgets()
    
    def _on_destroy(self, event):
        """Cleanup when widget is destroyed"""
        if event.widget == self.frame:
            self.stop_bot()
    
    def create_widgets(self):
        """Create run tab widgets"""
        
        # Title
        ttk.Label(
            self.frame,
            text="Run Job Finder Bot",
            font=('Arial', 12, 'bold')
        ).pack(pady=(0, 10))
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.frame, text="Run Settings", padding="15")
        settings_frame.pack(fill='x', pady=(0, 10))
        
        # Min Score slider
        score_frame = ttk.Frame(settings_frame)
        score_frame.pack(fill='x', pady=5)
        
        ttk.Label(score_frame, text="Minimum Score:", width=15).pack(side='left')
        self.min_score_var = tk.IntVar(value=600)
        self.min_score_label = ttk.Label(score_frame, text="60/100 (600/1000)")
        self.min_score_label.pack(side='right', padx=(10, 0))
        
        self.min_score_scale = ttk.Scale(
            score_frame,
            from_=0,
            to=1000,
            orient='horizontal',
            variable=self.min_score_var,
            command=self.update_score_labels
        )
        self.min_score_scale.pack(side='left', fill='x', expand=True, padx=(10, 10))
        
        # High Threshold slider
        threshold_frame = ttk.Frame(settings_frame)
        threshold_frame.pack(fill='x', pady=5)
        
        ttk.Label(threshold_frame, text="High Threshold:", width=15).pack(side='left')
        self.high_threshold_var = tk.IntVar(value=800)
        self.high_threshold_label = ttk.Label(threshold_frame, text="80/100 (800/1000)")
        self.high_threshold_label.pack(side='right', padx=(10, 0))
        
        self.high_threshold_scale = ttk.Scale(
            threshold_frame,
            from_=0,
            to=1000,
            orient='horizontal',
            variable=self.high_threshold_var,
            command=self.update_score_labels
        )
        self.high_threshold_scale.pack(side='left', fill='x', expand=True, padx=(10, 10))
        
        # Workers slider
        workers_frame = ttk.Frame(settings_frame)
        workers_frame.pack(fill='x', pady=5)
        
        ttk.Label(workers_frame, text="LLM Workers:", width=15).pack(side='left')
        self.workers_var = tk.IntVar(value=8)
        self.workers_label = ttk.Label(workers_frame, text="8 workers")
        self.workers_label.pack(side='right', padx=(10, 0))
        
        self.workers_scale = ttk.Scale(
            workers_frame,
            from_=1,
            to=12,
            orient='horizontal',
            variable=self.workers_var,
            command=self.update_score_labels
        )
        self.workers_scale.pack(side='left', fill='x', expand=True, padx=(10, 10))
        
        # Control buttons
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        
        self.start_btn = ttk.Button(
            btn_frame,
            text="▶️ Start Job Search",
            command=self.start_bot,
            style='Accent.TButton'
        )
        self.start_btn.pack(side='left', padx=(0, 10))
        
        self.stop_btn = ttk.Button(
            btn_frame,
            text="⏹️ Stop",
            command=self.stop_bot,
            state='disabled'
        )
        self.stop_btn.pack(side='left')
        
        ttk.Button(
            btn_frame,
            text="🗑️ Clear Output",
            command=self.clear_output
        ).pack(side='right')
        
        # Progress bar
        self.progress = ttk.Progressbar(
            self.frame,
            mode='indeterminate',
            length=300
        )
        self.progress.pack(fill='x', pady=(0, 10))
        
        # Output console
        console_frame = ttk.LabelFrame(self.frame, text="Console Output", padding="10")
        console_frame.pack(fill='both', expand=True)
        
        self.console = scrolledtext.ScrolledText(
            console_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white',
            state='normal'  # Allow text selection and copying
        )
        self.console.pack(fill='both', expand=True)
        
        # Enable text selection (readonly but copyable)
        self.console.bind('<Control-c>', lambda e: None)  # Allow Ctrl+C
        
        # Configure tags for colored output
        self.console.tag_config('success', foreground='#4ec9b0')
        self.console.tag_config('error', foreground='#f48771')
        self.console.tag_config('warning', foreground='#dcdcaa')
        self.console.tag_config('info', foreground='#9cdcfe')
    
    def update_score_labels(self, *args):
        """Update score labels when sliders change"""
        min_score = self.min_score_var.get()
        high_threshold = self.high_threshold_var.get()
        workers = self.workers_var.get()
        
        self.min_score_label.config(text=f"{min_score//10}/100 ({min_score}/1000)")
        self.high_threshold_label.config(text=f"{high_threshold//10}/100 ({high_threshold}/1000)")
        self.workers_label.config(text=f"{workers} workers")
    
    def start_bot(self):
        """Start the job finder bot in subprocess"""
        if self.is_running:
            messagebox.showwarning("Already Running", "Bot is already running")
            return
        
        # Validate config exists
        config_path = Path(__file__).parent.parent / 'config.yaml'
        if not config_path.exists():
            messagebox.showerror(
                "Config Missing",
                "config.yaml not found!\n\nPlease configure email and paths in the Setup tab first."
            )
            return
        
        # Build command
        min_score = self.min_score_var.get()
        high_threshold = self.high_threshold_var.get()
        workers = self.workers_var.get()
        
        cmd = [
            sys.executable,
            str(self.bot_script),
            '--auto',
            '--min-score', str(min_score),
            '--high-threshold', str(high_threshold),
            '--workers', str(workers)
        ]
        
        self.log(f"Starting: {' '.join(cmd)}", 'info')
        self.log("=" * 70, 'info')
        
        # Update UI
        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.progress.start(10)
        self.main_window.set_status("Job finder running...", 'info')
        
        # Start subprocess in thread
        thread = threading.Thread(target=self.run_subprocess, args=(cmd,), daemon=True)
        thread.start()
        
        # Start output reader
        self.read_output()
    
    def run_subprocess(self, cmd):
        """Run subprocess and capture output"""
        try:
            # Set environment for unbuffered output
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
                encoding='utf-8',
                errors='replace'  # Replace invalid chars instead of crashing
            )
            
            # Read output line by line
            for line in self.process.stdout:
                self.output_queue.put(('stdout', line))
            
            # Wait for completion
            self.process.wait()
            
            # Check return code
            if self.process.returncode == 0:
                self.output_queue.put(('done', 'success'))
            else:
                self.output_queue.put(('done', f'error: exit code {self.process.returncode}'))
                
        except Exception as e:
            self.output_queue.put(('error', str(e)))
    
    def read_output(self):
        """Read output from queue and display (line-by-line)"""
        try:
            # Process all available lines immediately
            while True:
                try:
                    msg_type, msg = self.output_queue.get_nowait()
                    
                    if msg_type == 'stdout':
                        # Determine tag based on content
                        if '✓' in msg or 'success' in msg.lower():
                            tag = 'success'
                        elif '✗' in msg or 'error' in msg.lower():
                            tag = 'error'
                        elif '⚠' in msg or 'warning' in msg.lower():
                            tag = 'warning'
                        else:
                            tag = 'info'
                        
                        self.log(msg.rstrip(), tag)
                        
                    elif msg_type == 'done':
                        if msg == 'success':
                            self.log("\n" + "=" * 70, 'success')
                            self.log("✓ Job search completed successfully!", 'success')
                            self.main_window.set_status("Job search completed!", 'success')
                        else:
                            self.log("\n" + "=" * 70, 'error')
                            self.log(f"✗ Job search failed: {msg}", 'error')
                            self.main_window.set_status("Job search failed", 'error')
                        
                        self.cleanup_after_run()
                        return  # Stop polling
                        
                    elif msg_type == 'error':
                        self.log(f"✗ Error: {msg}", 'error')
                        self.cleanup_after_run()
                        return  # Stop polling
                        
                except queue.Empty:
                    break
            
            # Force GUI update
            self.console.update_idletasks()
                        
        except Exception as e:
            print(f"Error in read_output: {e}")
        
        # Continue reading if still running (fast polling for real-time feel)
        if self.is_running:
            self.frame.after(5, self.read_output)  # 5ms = very responsive
    
    def stop_bot(self):
        """Stop the running bot"""
        if not self.is_running or not self.process:
            return
        
        try:
            # Try graceful termination first
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                self.process.kill()
            self.log("\n⏹️ Stopped by user", 'warning')
            self.main_window.set_status("Job search stopped", 'warning')
        except Exception as e:
            self.log(f"Error stopping process: {e}", 'error')
        
        self.cleanup_after_run()
    
    def cleanup_after_run(self):
        """Reset UI after bot finishes"""
        self.is_running = False
        self.process = None
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.progress.stop()
    
    def log(self, message, tag='info'):
        """Add message to console"""
        self.console.insert('end', message + '\n', tag)
        self.console.see('end')
        self.console.update_idletasks()  # Force immediate GUI refresh
    
    def clear_output(self):
        """Clear console output"""
        self.console.delete('1.0', 'end')
