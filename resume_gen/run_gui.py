"""
Resume Generator - GUI Application
Simplified UI with user management, sentence library, settings, and RAG scoring view.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from resume_gen.user_manager import UserManager
from resume_gen.generator import ResumeGenerator
from resume_gen.import_review_tab import ImportReviewTab
from resume_gen.settings_tab import SettingsTab
from resume_gen.gui.rag_tab import RAGTab
from resume_gen.gui.rag_audit_tab import RAGAuditTab


class ResumeGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Resume Generator - Multi-User")
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)
        
        self.user_manager = UserManager()
        self.current_user = None
        self.generator = None  # Lazy init when a user is selected
        
        style = ttk.Style()
        style.theme_use('clam')
        
        self.create_widgets()
        self.refresh_user_list()
    
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(
            main_frame,
            text="Resume Generator",
            font=('Arial', 16, 'bold')
        ).pack(pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Select or create a user to begin")
        
        # Notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # User tab
        self.user_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.user_tab, text="Users")
        self.create_user_tab()
        
        # Sentences tab
        self.sentences_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.sentences_tab, text="Sentences")
        self.create_sentences_tab()
        
        # Generate tab (placeholder)
        self.generate_tab = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(self.generate_tab, text="Generate")
        self.create_generate_tab()
        
        # Import Review tab
        self.import_tab = ImportReviewTab(
            self.notebook, 
            self.user_manager,
            status_callback=lambda msg: self.status_var.set(msg)
        )
        self.notebook.add(self.import_tab, text="Import PDF")
        
        # Settings tab
        self.settings_tab = SettingsTab(
            self.notebook,
            status_callback=lambda msg: self.status_var.set(msg)
        )
        self.notebook.add(self.settings_tab, text="Settings")

        # RAG Scoring tab
        self.rag_tab = RAGTab(
            self.notebook,
            status_callback=lambda msg: self.status_var.set(msg)
        )
        self.notebook.add(self.rag_tab.frame, text="RAG Scoring")
        
        # RAG Audit tab (embedding accuracy)
        self.rag_audit_tab = RAGAuditTab(
            self.notebook,
            self.user_manager,
            status_callback=lambda msg: self.status_var.set(msg)
        )
        self.notebook.add(self.rag_audit_tab.frame, text="RAG Audit")
        
        # Status bar
        self.status_label = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor='w',
            padding="5"
        )
        self.status_label.pack(fill='x', pady=(10, 0))
    
    # ---------------- User tab ----------------
    def create_user_tab(self):
        left_frame = ttk.LabelFrame(self.user_tab, text="Users", padding="10")
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        self.user_listbox = tk.Listbox(left_frame, font=('Arial', 11), height=15)
        self.user_listbox.pack(fill='both', expand=True)
        self.user_listbox.bind('<<ListboxSelect>>', self.on_user_select)
        
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="New User", command=self.create_user).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Delete", command=self.delete_user).pack(side='left', padx=(0, 5))
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_user_list).pack(side='right')
        
        right_frame = ttk.LabelFrame(self.user_tab, text="Profile", padding="10")
        right_frame.pack(side='right', fill='both', expand=True)
        
        ttk.Label(right_frame, text="Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.profile_name_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.profile_name_var, width=30).grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(right_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
        self.profile_email_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.profile_email_var, width=30).grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Button(right_frame, text="Save Profile", command=self.save_profile).grid(row=2, column=1, pady=10, sticky='e')
        
        self.stats_label = ttk.Label(right_frame, text="Select a user to see stats", foreground='gray')
        self.stats_label.grid(row=3, column=0, columnspan=2, pady=5)
    
    def refresh_user_list(self):
        users = self.user_manager.list_users()
        self.user_listbox.delete(0, tk.END)
        for u in users:
            self.user_listbox.insert(tk.END, u)
        if users:
            self.user_listbox.selection_set(0)
            self.on_user_select()
        else:
            self.current_user = None
            self.set_status("No users. Create one to begin.")
            self.refresh_sentences_table()
    
    def on_user_select(self, event=None):
        sel = self.user_listbox.curselection()
        if not sel:
            return
        self.current_user = self.user_listbox.get(sel[0])
        user = self.user_manager.get_user(self.current_user)
        if user:
            profile = user.get("profile", {})
            self.profile_name_var.set(profile.get("name", ""))
            self.profile_email_var.set(profile.get("email", ""))
            stats = self.user_manager.get_rag_index_stats(self.current_user) or {}
            self.stats_label.config(text=f"Sentences: {len(self.user_manager.get_sentences_flat(self.current_user))} | RAG: {stats.get('total_sentences','?')} vectors")
            self.set_status(f"Selected user: {self.current_user}")
            self.refresh_sentences_table()
    
    def create_user(self):
        name = simpledialog.askstring("New User", "Enter username:")
        if not name:
            return
        if self.user_manager.create_user(name):
            self.set_status(f"Created user {name}")
            self.refresh_user_list()
        else:
            messagebox.showerror("Exists", f"User '{name}' already exists.")
    
    def delete_user(self):
        if not self.current_user:
            return
        if messagebox.askyesno("Confirm", f"Delete user '{self.current_user}'?"):
            self.user_manager.delete_user(self.current_user)
            self.set_status(f"Deleted user {self.current_user}")
            self.refresh_user_list()
    
    def save_profile(self):
        if not self.current_user:
            return
        profile = {
            "name": self.profile_name_var.get(),
            "email": self.profile_email_var.get()
        }
        self.user_manager.update_user_profile(self.current_user, profile)
        self.set_status("Profile saved")
    
    # ---------------- Sentences tab ----------------
    def create_sentences_tab(self):
        add_frame = ttk.LabelFrame(self.sentences_tab, text="Add Sentence", padding="10")
        add_frame.pack(fill='x', pady=(0, 10))
        
        type_frame = ttk.Frame(add_frame)
        type_frame.pack(fill='x', pady=5)
        ttk.Label(type_frame, text="Type:").pack(side='left')
        self.sentence_type_var = tk.StringVar(value="skills")
        ttk.Combobox(type_frame, textvariable=self.sentence_type_var, width=15,
                     values=["skills", "experience", "achievements", "education", "certifications", "projects"]).pack(side='left', padx=5)
        
        ttk.Label(type_frame, text="Category:").pack(side='left', padx=(15, 0))
        self.sentence_category_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.sentence_category_var, width=15).pack(side='left', padx=5)
        
        ttk.Label(type_frame, text="Tags (comma):").pack(side='left', padx=(15, 0))
        self.sentence_tags_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.sentence_tags_var, width=20).pack(side='left', padx=5)
        
        text_frame = ttk.Frame(add_frame)
        text_frame.pack(fill='x', pady=5)
        ttk.Label(text_frame, text="Sentence:").pack(side='left')
        self.sentence_text_var = tk.StringVar()
        ttk.Entry(text_frame, textvariable=self.sentence_text_var, width=80).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(text_frame, text="Add", command=self.add_sentence).pack(side='right')
        
        list_frame = ttk.LabelFrame(self.sentences_tab, text="Sentence Library", padding="10")
        list_frame.pack(fill='both', expand=True)
        
        columns = ('type', 'tags', 'text')
        self.sentences_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        self.sentences_tree.heading('type', text='Type')
        self.sentences_tree.heading('tags', text='Tags')
        self.sentences_tree.heading('text', text='Sentence')
        self.sentences_tree.column('type', width=100)
        self.sentences_tree.column('tags', width=150)
        self.sentences_tree.column('text', width=550)
        self.sentences_tree.pack(side='left', fill='both', expand=True)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.sentences_tree.yview)
        self.sentences_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
    
    def refresh_sentences_table(self):
        for item in self.sentences_tree.get_children():
            self.sentences_tree.delete(item)
        if not self.current_user:
            return
        flat = self.user_manager.get_sentences_flat(self.current_user)
        for entry in flat:
            self.sentences_tree.insert(
                '', 'end',
                values=(entry.get("type"), ", ".join(entry.get("tags", [])), entry.get("text"))
            )
    
    def add_sentence(self):
        if not self.current_user:
            messagebox.showwarning("No user", "Select a user first.")
            return
        text = self.sentence_text_var.get().strip()
        if not text:
            return
        stype = self.sentence_type_var.get()
        category = self.sentence_category_var.get().strip() or None
        tags = [t.strip() for t in self.sentence_tags_var.get().split(',') if t.strip()]
        ok = self.user_manager.add_sentence(self.current_user, stype, text, category=category, tags=tags)
        if ok:
            self.set_status("Sentence added")
            self.sentence_text_var.set("")
            self.refresh_sentences_table()
        else:
            messagebox.showerror("Error", "Failed to add sentence.")
    
    # ---------------- Generate tab ----------------
    def create_generate_tab(self):
        ttk.Label(self.generate_tab, text="Resume generation placeholder", font=('Arial', 12)).pack(pady=10)
        ttk.Button(self.generate_tab, text="Generate (stub)", command=lambda: self.set_status("Generation not implemented in this simplified UI")).pack()
    
    # ---------------- Helpers ----------------
    def set_status(self, msg):
        self.status_var.set(msg)


def main():
    root = tk.Tk()
    app = ResumeGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
