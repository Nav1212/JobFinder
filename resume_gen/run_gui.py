"""
Resume Generator - GUI Application
Multi-user resume generation with hybrid TF-IDF + tag matching
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from resume_gen.user_manager import UserManager
from resume_gen.generator import ResumeGenerator
from resume_gen.import_review_tab import ImportReviewTab


class ResumeGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Resume Generator - Multi-User")
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)
        
        self.user_manager = UserManager()
        self.current_user = None
        self.generator = None
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.create_widgets()
        self.refresh_user_list()
    
    def create_widgets(self):
        """Create main GUI layout"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(
            main_frame,
            text="📄 Resume Generator",
            font=('Arial', 16, 'bold')
        ).pack(pady=(0, 10))
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Tab 1: User Management
        self.user_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.user_tab, text="👤 Users")
        self.create_user_tab()
        
        # Tab 2: Sentence Library
        self.sentences_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.sentences_tab, text="📝 Sentences")
        self.create_sentences_tab()
        
        # Tab 3: Generate Resume
        self.generate_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.generate_tab, text="🎯 Generate")
        self.create_generate_tab()
        
        # Tab 4: Import Review
        self.import_tab = ImportReviewTab(
            self.notebook, 
            self.user_manager,
            status_callback=lambda msg: self.status_var.set(msg)
        )
        self.notebook.add(self.import_tab, text="📥 Import PDF")
        
        # Status bar
        self.status_var = tk.StringVar(value="Select or create a user to begin")
        self.status_label = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor='w',
            padding="5"
        )
        self.status_label.pack(fill='x', pady=(10, 0))
    
    def create_user_tab(self):
        """Create user management tab"""
        # Left side: user list
        left_frame = ttk.LabelFrame(self.user_tab, text="Users", padding="10")
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # User listbox
        self.user_listbox = tk.Listbox(left_frame, font=('Arial', 11), height=15)
        self.user_listbox.pack(fill='both', expand=True)
        self.user_listbox.bind('<<ListboxSelect>>', self.on_user_select)
        
        # User buttons
        user_btn_frame = ttk.Frame(left_frame)
        user_btn_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(user_btn_frame, text="➕ New User", command=self.create_user).pack(side='left', padx=(0, 5))
        ttk.Button(user_btn_frame, text="🗑️ Delete", command=self.delete_user).pack(side='left')
        ttk.Button(user_btn_frame, text="🔄 Refresh", command=self.refresh_user_list).pack(side='right')
        
        # Right side: user profile
        right_frame = ttk.LabelFrame(self.user_tab, text="Profile", padding="10")
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Profile fields
        ttk.Label(right_frame, text="Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.profile_name_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.profile_name_var, width=30).grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(right_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
        self.profile_email_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.profile_email_var, width=30).grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Button(right_frame, text="💾 Save Profile", command=self.save_profile).grid(row=2, column=1, pady=15, sticky='e')
        
        # Stats
        ttk.Separator(right_frame, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)
        
        self.stats_label = ttk.Label(right_frame, text="Select a user to see stats", foreground='gray')
        self.stats_label.grid(row=4, column=0, columnspan=2, pady=5)
    
    def create_sentences_tab(self):
        """Create sentence library tab"""
        # Top: add sentence
        add_frame = ttk.LabelFrame(self.sentences_tab, text="Add Sentence", padding="10")
        add_frame.pack(fill='x', pady=(0, 10))
        
        # Type dropdown
        type_frame = ttk.Frame(add_frame)
        type_frame.pack(fill='x', pady=5)
        
        ttk.Label(type_frame, text="Type:").pack(side='left')
        self.sentence_type_var = tk.StringVar(value="skills")
        type_combo = ttk.Combobox(type_frame, textvariable=self.sentence_type_var, width=15,
                                   values=["skills", "experience", "achievements", "projects", "education", "certifications"])
        type_combo.pack(side='left', padx=5)
        
        ttk.Label(type_frame, text="Category:").pack(side='left', padx=(15, 0))
        self.sentence_category_var = tk.StringVar()
        self.category_entry = ttk.Entry(type_frame, textvariable=self.sentence_category_var, width=15)
        self.category_entry.pack(side='left', padx=5)
        
        ttk.Label(type_frame, text="Tags (comma-sep):").pack(side='left', padx=(15, 0))
        self.sentence_tags_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.sentence_tags_var, width=20).pack(side='left', padx=5)
        
        # Sentence text
        text_frame = ttk.Frame(add_frame)
        text_frame.pack(fill='x', pady=5)
        
        ttk.Label(text_frame, text="Sentence:").pack(side='left')
        self.sentence_text_var = tk.StringVar()
        ttk.Entry(text_frame, textvariable=self.sentence_text_var, width=80).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(text_frame, text="➕ Add", command=self.add_sentence).pack(side='right')
        
        # Bottom: sentence list
        list_frame = ttk.LabelFrame(self.sentences_tab, text="Sentence Library", padding="10")
        list_frame.pack(fill='both', expand=True)
        
        # Treeview for sentences
        columns = ('type', 'category', 'tags', 'text')
        self.sentences_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        self.sentences_tree.heading('type', text='Type')
        self.sentences_tree.heading('category', text='Category')
        self.sentences_tree.heading('tags', text='Tags')
        self.sentences_tree.heading('text', text='Sentence')
        
        self.sentences_tree.column('type', width=80)
        self.sentences_tree.column('category', width=100)
        self.sentences_tree.column('tags', width=120)
        self.sentences_tree.column('text', width=450)
        
        # Scrollbar
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.sentences_tree.yview)
        self.sentences_tree.configure(yscrollcommand=vsb.set)
        
        self.sentences_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        # Sentence buttons
        sent_btn_frame = ttk.Frame(self.sentences_tab)
        sent_btn_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(sent_btn_frame, text="🗑️ Delete Selected", command=self.delete_sentence).pack(side='left')
        ttk.Button(sent_btn_frame, text="🔄 Refresh", command=self.refresh_sentences).pack(side='right')
    
    def create_generate_tab(self):
        """Create resume generation tab"""
        # Left: job description input
        left_frame = ttk.LabelFrame(self.generate_tab, text="Job Description", padding="10")
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        self.job_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, font=('Arial', 10), height=20)
        self.job_text.pack(fill='both', expand=True)
        
        # Generate button
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(btn_frame, text="🎯 Generate Resume", command=self.generate_resume).pack(side='left')
        ttk.Button(btn_frame, text="📋 Paste from Clipboard", command=self.paste_job).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="🗑️ Clear", command=lambda: self.job_text.delete('1.0', 'end')).pack(side='right')
        
        # Right: generated resume
        right_frame = ttk.LabelFrame(self.generate_tab, text="Generated Resume", padding="10")
        right_frame.pack(side='right', fill='both', expand=True)
        
        self.resume_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=('Consolas', 10), height=20)
        self.resume_text.pack(fill='both', expand=True)
        
        # Export button
        export_frame = ttk.Frame(right_frame)
        export_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(export_frame, text="💾 Save to File", command=self.save_resume).pack(side='left')
        ttk.Button(export_frame, text="📋 Copy to Clipboard", command=self.copy_resume).pack(side='left', padx=10)
    
    # ==================== User Operations ====================
    
    def refresh_user_list(self):
        """Refresh the user listbox"""
        self.user_listbox.delete(0, tk.END)
        for user in self.user_manager.list_users():
            self.user_listbox.insert(tk.END, user)
    
    def on_user_select(self, event):
        """Handle user selection"""
        selection = self.user_listbox.curselection()
        if not selection:
            return
        
        username = self.user_listbox.get(selection[0])
        self.current_user = username
        
        # Load user data
        user = self.user_manager.get_user(username)
        if user:
            profile = user.get("profile", {})
            self.profile_name_var.set(profile.get("name", ""))
            self.profile_email_var.set(profile.get("email", ""))
            
            # Update stats
            sentences = self.user_manager.get_sentences_flat(username)
            tags = self.user_manager.get_all_tags(username)
            self.stats_label.config(text=f"Sentences: {len(sentences)} | Tags: {len(tags)}")
        
        # Initialize generator
        try:
            self.generator = ResumeGenerator(username)
            self.status_var.set(f"Loaded user: {username}")
        except Exception as e:
            self.status_var.set(f"Error loading user: {e}")
        
        # Update import tab with current user
        self.import_tab.set_current_user(username)
        
        # Refresh sentences
        self.refresh_sentences()
    
    def create_user(self):
        """Create a new user"""
        username = tk.simpledialog.askstring("New User", "Enter username:")
        if not username:
            return
        
        username = username.strip().lower().replace(" ", "_")
        
        if self.user_manager.user_exists(username):
            messagebox.showerror("Error", f"User '{username}' already exists")
            return
        
        self.user_manager.create_user(username)
        self.refresh_user_list()
        self.status_var.set(f"Created user: {username}")
        
        # Select the new user
        users = self.user_manager.list_users()
        if username in users:
            idx = users.index(username)
            self.user_listbox.selection_clear(0, tk.END)
            self.user_listbox.selection_set(idx)
            self.user_listbox.event_generate('<<ListboxSelect>>')
    
    def delete_user(self):
        """Delete selected user"""
        if not self.current_user:
            messagebox.showwarning("No Selection", "Select a user first")
            return
        
        if messagebox.askyesno("Confirm Delete", f"Delete user '{self.current_user}' and all their data?"):
            self.user_manager.delete_user(self.current_user)
            self.current_user = None
            self.generator = None
            self.refresh_user_list()
            self.profile_name_var.set("")
            self.profile_email_var.set("")
            self.stats_label.config(text="Select a user to see stats")
            self.status_var.set("User deleted")
    
    def save_profile(self):
        """Save user profile"""
        if not self.current_user:
            messagebox.showwarning("No Selection", "Select a user first")
            return
        
        self.user_manager.update_user_profile(self.current_user, {
            "name": self.profile_name_var.get(),
            "email": self.profile_email_var.get()
        })
        self.status_var.set("Profile saved")
    
    # ==================== Sentence Operations ====================
    
    def refresh_sentences(self):
        """Refresh sentence list for current user"""
        # Clear tree
        for item in self.sentences_tree.get_children():
            self.sentences_tree.delete(item)
        
        if not self.current_user:
            return
        
        sentences = self.user_manager.get_sentences_flat(self.current_user)
        
        for s in sentences:
            tags_str = ", ".join(s.get("tags", []))
            text = s.get("text", "")[:80] + ("..." if len(s.get("text", "")) > 80 else "")
            
            # Extract category from first tag if available
            tags = s.get("tags", [])
            category = tags[0] if tags else ""
            other_tags = ", ".join(tags[1:]) if len(tags) > 1 else ""
            
            self.sentences_tree.insert('', 'end', values=(
                s.get("type", ""),
                category,
                other_tags,
                text
            ))
    
    def add_sentence(self):
        """Add a sentence to current user's library"""
        if not self.current_user:
            messagebox.showwarning("No User", "Select a user first")
            return
        
        text = self.sentence_text_var.get().strip()
        if not text:
            messagebox.showwarning("Empty", "Enter a sentence")
            return
        
        sentence_type = self.sentence_type_var.get()
        category = self.sentence_category_var.get().strip() or None
        tags_str = self.sentence_tags_var.get().strip()
        tags = [t.strip() for t in tags_str.split(",")] if tags_str else None
        
        self.user_manager.add_sentence(self.current_user, sentence_type, text, category, tags)
        
        # Clear inputs
        self.sentence_text_var.set("")
        self.sentence_tags_var.set("")
        
        # Refresh
        self.refresh_sentences()
        
        # Reload generator
        if self.generator:
            self.generator.reload_sentences()
        
        self.status_var.set("Sentence added")
    
    def delete_sentence(self):
        """Delete selected sentence"""
        selection = self.sentences_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a sentence to delete")
            return
        
        # Note: This is a simplified delete - in practice you'd want to track sentence IDs
        messagebox.showinfo("Info", "Delete functionality requires sentence tracking. Use JSON editor for now.")
    
    # ==================== Generation Operations ====================
    
    def paste_job(self):
        """Paste job description from clipboard"""
        try:
            text = self.root.clipboard_get()
            self.job_text.delete('1.0', 'end')
            self.job_text.insert('1.0', text)
        except:
            messagebox.showwarning("Clipboard", "Could not paste from clipboard")
    
    def generate_resume(self):
        """Generate resume from job description"""
        if not self.generator:
            messagebox.showwarning("No User", "Select a user first")
            return
        
        job_desc = self.job_text.get('1.0', 'end-1c').strip()
        if not job_desc:
            messagebox.showwarning("Empty", "Enter a job description")
            return
        
        self.status_var.set("Generating resume...")
        self.root.update()
        
        try:
            resume = self.generator.generate_resume(job_desc)
            formatted = self.generator.format_resume_text(resume)
            
            self.resume_text.delete('1.0', 'end')
            self.resume_text.insert('1.0', formatted)
            
            self.status_var.set(f"Generated resume with {sum(len(v) for v in resume.values())} bullet points")
        except Exception as e:
            messagebox.showerror("Error", f"Generation failed: {e}")
            self.status_var.set("Generation failed")
    
    def save_resume(self):
        """Save resume to file"""
        text = self.resume_text.get('1.0', 'end-1c')
        if not text.strip():
            messagebox.showwarning("Empty", "Generate a resume first")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
            self.status_var.set(f"Saved to {filepath}")
    
    def copy_resume(self):
        """Copy resume to clipboard"""
        text = self.resume_text.get('1.0', 'end-1c')
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Copied to clipboard")


def main():
    # Need simpledialog for user creation
    import tkinter.simpledialog
    
    root = tk.Tk()
    app = ResumeGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
