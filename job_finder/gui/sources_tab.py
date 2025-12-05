"""Job Sources Management Tab"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import json


class SourcesTab:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        # Job sources at project root
        self.sources_file = Path(__file__).parent.parent.parent / 'job_sources.json'
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
            columns=('name', 'type', 'enabled', 'category'),
            show='tree headings',
            yscrollcommand=vsb.set,
            selectmode='browse'
        )
        
        self.tree.heading('#0', text='Category')
        self.tree.heading('name', text='Source Name')
        self.tree.heading('type', text='Type')
        self.tree.heading('enabled', text='Status')
        self.tree.heading('category', text='Tag')
        
        self.tree.column('#0', width=180)
        self.tree.column('name', width=180)
        self.tree.column('type', width=90)
        self.tree.column('enabled', width=90)
        self.tree.column('category', width=100)
        
        vsb.config(command=self.tree.yview)
        self.tree.pack(fill='both', expand=True)
        
        # Double-click to view details
        self.tree.bind('<Double-1>', lambda e: self.toggle_source())
        
        # Action buttons
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill='x')
        
        ttk.Button(btn_frame, text="👁️ View Details", command=self.view_source).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="🔄 Toggle Enable/Disable", command=self.toggle_source).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="➕ Add Source", command=self.add_source).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="✏️ Edit JSON", command=self.edit_json).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🔄 Reload", command=self.load_sources).pack(side='left', padx=5)
        
        # Info label
        info_frame = ttk.Frame(self.frame)
        info_frame.pack(fill='x', pady=(10, 0))
        
        info_text = "ℹ️ Sources organized by: Main (LinkedIn, Dice, APIs), Company Specific, Startups. Use '➕ Add Source' for custom sources."
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
            
            # Get category definitions
            categories_def = self.sources_data.get('categories', {
                'main': {'name': 'Main Job Sites'},
                'company_specific': {'name': 'Company Careers'},
                'startups': {'name': 'Startup Jobs'}
            })
            
            # Collect all sources with their categories
            sources_by_category = {'main': [], 'company_specific': [], 'startups': [], 'other': []}
            
            for source_type in ['api_sources', 'playwright_sources', 'scraping_sources']:
                if source_type in self.sources_data:
                    for src in self.sources_data[source_type]:
                        if not isinstance(src, dict):
                            continue
                        cat = src.get('category', 'main')
                        if cat not in sources_by_category:
                            cat = 'other'
                        sources_by_category[cat].append(src)
            
            # Category display info
            category_icons = {
                'main': '🌐 Main Job Sites',
                'company_specific': '🏢 Company Careers',
                'startups': '🚀 Startup Jobs',
                'other': '📋 Other'
            }
            
            # Add categories and sources to tree
            for cat_key in ['main', 'company_specific', 'startups', 'other']:
                sources = sources_by_category.get(cat_key, [])
                if not sources:
                    continue
                
                cat_name = category_icons.get(cat_key, cat_key)
                cat_node = self.tree.insert('', 'end', text=cat_name, values=('', '', '', ''))
                
                for source in sorted(sources, key=lambda x: x.get('name', '')):
                    source_name = source.get('name', 'Unknown')
                    source_type = source.get('type', 'unknown')
                    enabled = source.get('enabled', True)
                    status = '✅ Enabled' if enabled else '❌ Disabled'
                    
                    self.tree.insert(
                        cat_node,
                        'end',
                        text='',
                        values=(source_name, source_type, status, cat_key)
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
        
        # Find source in data
        source_config = None
        for source_type in ['api_sources', 'playwright_sources', 'scraping_sources']:
            if source_type in self.sources_data:
                for src in self.sources_data[source_type]:
                    if isinstance(src, dict) and src.get('name') == source_name:
                        source_config = src
                        break
            if source_config:
                break
        
        if not source_config:
            messagebox.showwarning("Not Found", f"Source '{source_name}' not found in data")
            return
        
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
    
    def toggle_source(self):
        """Toggle enabled/disabled status of selected source"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a job source to toggle")
            return
        
        item = self.tree.item(selection[0])
        source_name = item['values'][0] if item['values'] else None
        
        if not source_name:
            return
        
        # Find and toggle source in data
        try:
            toggled = False
            new_status = ""
            
            for source_type in ['api_sources', 'playwright_sources', 'scraping_sources']:
                if source_type in self.sources_data:
                    for src in self.sources_data[source_type]:
                        if isinstance(src, dict) and src.get('name') == source_name:
                            current_status = src.get('enabled', True)
                            src['enabled'] = not current_status
                            toggled = True
                            new_status = "enabled" if src['enabled'] else "disabled"
                            break
                if toggled:
                    break
            
            if not toggled:
                messagebox.showerror("Error", f"Could not find source '{source_name}' in data")
                return
            
            # Save changes to file
            with open(self.sources_file, 'w', encoding='utf-8') as f:
                json.dump(self.sources_data, f, indent=2)
            
            # Reload to update display
            self.load_sources()
            
            self.main_window.set_status(f"'{source_name}' {new_status}", 'success')
            
        except Exception as e:
            messagebox.showerror("Toggle Error", f"Failed to toggle source:\n{e}")
            self.main_window.set_status("Failed to toggle source", 'error')
    
    def add_source(self):
        """Add a new custom job source"""
        # Create add source dialog
        add_window = tk.Toplevel(self.frame)
        add_window.title("Add New Job Source")
        add_window.geometry("500x400")
        add_window.transient(self.frame.winfo_toplevel())
        add_window.grab_set()
        
        # Form frame
        form_frame = ttk.Frame(add_window, padding="20")
        form_frame.pack(fill='both', expand=True)
        
        ttk.Label(form_frame, text="➕ Add New Job Source", font=('Arial', 12, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=(0, 15)
        )
        
        # Name
        ttk.Label(form_frame, text="Source Name:").grid(row=1, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=1, column=1, pady=5, padx=(10, 0))
        
        # URL
        ttk.Label(form_frame, text="URL:").grid(row=2, column=0, sticky='w', pady=5)
        url_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=url_var, width=40).grid(row=2, column=1, pady=5, padx=(10, 0))
        
        # Type
        ttk.Label(form_frame, text="Type:").grid(row=3, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value="scraping")
        type_combo = ttk.Combobox(form_frame, textvariable=type_var, values=["api", "playwright", "scraping"], width=37)
        type_combo.grid(row=3, column=1, pady=5, padx=(10, 0))
        
        # Category
        ttk.Label(form_frame, text="Category:").grid(row=4, column=0, sticky='w', pady=5)
        category_var = tk.StringVar(value="startups")
        cat_combo = ttk.Combobox(form_frame, textvariable=category_var, values=["company_specific", "startups"], width=37)
        cat_combo.grid(row=4, column=1, pady=5, padx=(10, 0))
        
        # Parser (optional)
        ttk.Label(form_frame, text="Parser:").grid(row=5, column=0, sticky='w', pady=5)
        parser_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=parser_var, width=40).grid(row=5, column=1, pady=5, padx=(10, 0))
        
        # Description
        ttk.Label(form_frame, text="Description:").grid(row=6, column=0, sticky='w', pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=desc_var, width=40).grid(row=6, column=1, pady=5, padx=(10, 0))
        
        # Note
        ttk.Label(
            form_frame, 
            text="Note: New sources are added as disabled.\nYou may need to implement a parser in job_finder_bot.py",
            foreground='gray',
            font=('Arial', 8)
        ).grid(row=7, column=0, columnspan=2, pady=(15, 0))
        
        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=(20, 0))
        
        def save_source():
            name = name_var.get().strip()
            url = url_var.get().strip()
            source_type = type_var.get()
            category = category_var.get()
            parser = parser_var.get().strip() or name.lower().replace(' ', '_')
            desc = desc_var.get().strip()
            
            if not name or not url:
                messagebox.showwarning("Missing Fields", "Name and URL are required")
                return
            
            # Determine which array to add to
            type_map = {'api': 'api_sources', 'playwright': 'playwright_sources', 'scraping': 'scraping_sources'}
            array_key = type_map.get(source_type, 'scraping_sources')
            
            # Create source entry
            new_source = {
                "name": name,
                "url": url,
                "enabled": False,
                "type": source_type,
                "parser": parser,
                "category": category,
                "description": desc or f"Custom {category} source"
            }
            
            # Add to data
            if array_key not in self.sources_data:
                self.sources_data[array_key] = []
            self.sources_data[array_key].append(new_source)
            
            # Save
            try:
                with open(self.sources_file, 'w', encoding='utf-8') as f:
                    json.dump(self.sources_data, f, indent=2)
                
                self.load_sources()
                add_window.destroy()
                self.main_window.set_status(f"Added source: {name}", 'success')
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save:\n{e}")
        
        ttk.Button(btn_frame, text="💾 Add Source", command=save_source).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=add_window.destroy).pack(side='left')
