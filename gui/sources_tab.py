"""Job Sources Management Tab"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import json


class SourcesTab:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.sources_file = Path(__file__).parent.parent / 'job_sources.json'
        self.sources_data = {}
        
        # Create main frame
        self.frame = ttk.Frame(parent, padding="20")
        
        self.create_widgets()
        self.load_sources()
    
    def create_widgets(self):
        """Create job sources widgets"""
        
        # Title
        title_frame = ttk.Frame(self.frame)
        title_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(
            title_frame,
            text="Job Source Configuration",
            font=('Arial', 12, 'bold')
        ).pack(side='left')
        
        ttk.Label(
            title_frame,
            text=f"File: {self.sources_file.name}",
            foreground='gray',
            font=('Arial', 9)
        ).pack(side='right')
        
        # Sources list
        list_frame = ttk.LabelFrame(self.frame, text="Available Job Sources", padding="10")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Create treeview
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill='both', expand=True)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side='right', fill='y')
        
        self.tree = ttk.Treeview(
            tree_frame,
            columns=('name', 'type', 'enabled', 'count'),
            show='tree headings',
            yscrollcommand=vsb.set,
            selectmode='browse'
        )
        
        self.tree.heading('#0', text='Category')
        self.tree.heading('name', text='Source Name')
        self.tree.heading('type', text='Type')
        self.tree.heading('enabled', text='Status')
        self.tree.heading('count', text='URLs')
        
        self.tree.column('#0', width=150)
        self.tree.column('name', width=200)
        self.tree.column('type', width=100)
        self.tree.column('enabled', width=80)
        self.tree.column('count', width=60)
        
        vsb.config(command=self.tree.yview)
        self.tree.pack(fill='both', expand=True)
        
        # Double-click to view details
        self.tree.bind('<Double-1>', lambda e: self.view_source())
        
        # Action buttons
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill='x')
        
        ttk.Button(btn_frame, text="👁️ View Details", command=self.view_source).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="✏️ Edit JSON", command=self.edit_json).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🔄 Reload", command=self.load_sources).pack(side='left', padx=5)
        
        # Info label
        info_frame = ttk.Frame(self.frame)
        info_frame.pack(fill='x', pady=(10, 0))
        
        info_text = "ℹ️ Job sources are configured in job_sources.json. Double-click to view details or use 'Edit JSON' to modify."
        ttk.Label(
            info_frame,
            text=info_text,
            foreground='blue',
            wraplength=700,
            font=('Arial', 9)
        ).pack()
    
    def load_sources(self):
        """Load job_sources.json"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            if not self.sources_file.exists():
                self.tree.insert('', 'end', text='No job_sources.json found', values=('', '', '', ''))
                self.main_window.set_status("job_sources.json not found", 'warning')
                return
            
            with open(self.sources_file, 'r') as f:
                self.sources_data = json.load(f)
            
            total_sources = 0
            
            # Group by category
            categories = {}
            for source_name, source_config in self.sources_data.items():
                source_type = source_config.get('type', 'unknown')
                if source_type not in categories:
                    categories[source_type] = []
                categories[source_type].append((source_name, source_config))
            
            # Add to tree
            for category, sources in sorted(categories.items()):
                cat_node = self.tree.insert('', 'end', text=f"📁 {category.upper()}", values=('', '', '', ''))
                
                for source_name, source_config in sorted(sources):
                    enabled = source_config.get('enabled', True)
                    status = '✅ Enabled' if enabled else '❌ Disabled'
                    
                    urls = source_config.get('urls', [])
                    url_count = len(urls) if isinstance(urls, list) else 1
                    
                    self.tree.insert(
                        cat_node,
                        'end',
                        text='',
                        values=(source_name, category, status, url_count)
                    )
                    total_sources += 1
            
            # Expand all categories
            for item in self.tree.get_children():
                self.tree.item(item, open=True)
            
            self.main_window.set_status(f"Loaded {total_sources} job sources", 'success')
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load job sources:\n{e}")
            self.main_window.set_status("Failed to load job sources", 'error')
    
    def view_source(self):
        """View details of selected source"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a job source to view")
            return
        
        item = self.tree.item(selection[0])
        source_name = item['values'][0] if item['values'] else None
        
        if not source_name:
            return
        
        if source_name not in self.sources_data:
            messagebox.showwarning("Not Found", f"Source '{source_name}' not found in data")
            return
        
        source_config = self.sources_data[source_name]
        
        # Create details window
        details_window = tk.Toplevel(self.frame)
        details_window.title(f"Job Source: {source_name}")
        details_window.geometry("700x500")
        
        # Title
        ttk.Label(
            details_window,
            text=f"🌐 {source_name}",
            font=('Arial', 12, 'bold'),
            padding=10
        ).pack()
        
        # Details in scrolled text
        text_frame = ttk.Frame(details_window)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        text_widget.pack(fill='both', expand=True)
        
        # Format JSON with indentation
        formatted_json = json.dumps(source_config, indent=2)
        text_widget.insert('1.0', formatted_json)
        text_widget.config(state='disabled')
        
        # Close button
        ttk.Button(
            details_window,
            text="Close",
            command=details_window.destroy
        ).pack(pady=(0, 10))
    
    def edit_json(self):
        """Open JSON editor window"""
        if not self.sources_file.exists():
            messagebox.showwarning("No File", "job_sources.json not found")
            return
        
        # Create editor window
        editor_window = tk.Toplevel(self.frame)
        editor_window.title("Edit job_sources.json")
        editor_window.geometry("800x600")
        
        # Title
        ttk.Label(
            editor_window,
            text="⚠️ Edit job_sources.json (Advanced)",
            font=('Arial', 12, 'bold'),
            padding=10,
            foreground='red'
        ).pack()
        
        # Warning
        warning = ttk.Label(
            editor_window,
            text="Warning: Invalid JSON will break the job finder. Make sure to validate before saving.",
            foreground='red',
            padding=5
        )
        warning.pack()
        
        # Editor frame
        editor_frame = ttk.Frame(editor_window)
        editor_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Text widget
        text_widget = scrolledtext.ScrolledText(
            editor_frame,
            wrap=tk.NONE,
            font=('Consolas', 10)
        )
        text_widget.pack(fill='both', expand=True)
        
        # Load current content
        try:
            with open(self.sources_file, 'r') as f:
                content = f.read()
            text_widget.insert('1.0', content)
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load file:\n{e}")
            editor_window.destroy()
            return
        
        # Button frame
        btn_frame = ttk.Frame(editor_window)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        def save_json():
            """Save edited JSON"""
            content = text_widget.get('1.0', 'end-1c')
            
            # Validate JSON
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                messagebox.showerror("Invalid JSON", f"JSON syntax error:\n{e}")
                return
            
            # Save
            try:
                with open(self.sources_file, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", "job_sources.json saved successfully!")
                self.load_sources()
                editor_window.destroy()
                self.main_window.set_status("job_sources.json updated", 'success')
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save:\n{e}")
        
        def validate_json():
            """Validate JSON syntax"""
            content = text_widget.get('1.0', 'end-1c')
            try:
                json.loads(content)
                messagebox.showinfo("Valid", "✅ JSON syntax is valid!")
            except json.JSONDecodeError as e:
                messagebox.showerror("Invalid", f"❌ JSON syntax error:\n{e}")
        
        ttk.Button(btn_frame, text="💾 Save", command=save_json).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="✓ Validate", command=validate_json).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=editor_window.destroy).pack(side='right')
