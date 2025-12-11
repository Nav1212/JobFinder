"""RAG Scoring Visualization Tab for Resume Generator"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path

from core import resume_rag


class _Tooltip:
    """Lightweight tooltip for tree rows."""
    def __init__(self, widget):
        self.widget = widget
        self.tip = None

    def show(self, text, x, y):
        self.hide()
        if not text:
            return
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x+15}+{y+15}")
        label = tk.Label(
            tw, text=text, justify='left',
            relief='solid', borderwidth=1,
            background="#ffffe0", font=("Arial", 9)
        )
        label.pack(ipadx=4, ipady=2)

    def hide(self):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class RAGTab:
    """Tab to run RAG retrieval + LLM judge scoring and visualize by tag/category."""

    def __init__(self, parent, status_callback=None):
        self.parent = parent
        self.status_callback = status_callback or (lambda msg: None)
        self.indexes_dir = Path(__file__).parent.parent / 'indexes'

        self.frame = ttk.Frame(parent, padding="15")
        self.tooltip = _Tooltip(self.frame)
        self.reason_by_item = {}

        self._build_ui()
        self._load_users()

    def _build_ui(self):
        header = ttk.Label(self.frame, text="RAG Judge Scoring", font=('Arial', 12, 'bold'))
        header.pack(anchor='w', pady=(0, 10))

        form = ttk.Frame(self.frame)
        form.pack(fill='x', pady=(0, 10))

        ttk.Label(form, text="User / Index:", width=14).grid(row=0, column=0, sticky='w', pady=4)
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(form, textvariable=self.user_var, state='readonly', width=30)
        self.user_combo.grid(row=0, column=1, sticky='w', pady=4, padx=(5, 0))

        ttk.Label(form, text="Top K:", width=14).grid(row=0, column=2, sticky='e', pady=4, padx=(10, 0))
        self.topk_var = tk.IntVar(value=10)
        ttk.Entry(form, textvariable=self.topk_var, width=6).grid(row=0, column=3, sticky='w', pady=4)

        ttk.Label(form, text="Job / Query:", width=14).grid(row=1, column=0, sticky='nw', pady=4)
        self.query_text = scrolledtext.ScrolledText(form, height=5, width=70, wrap='word')
        self.query_text.grid(row=1, column=1, columnspan=3, sticky='we', pady=4, padx=(5, 0))

        ttk.Button(form, text="Score with RAG Judge", command=self.run_scoring).grid(
            row=2, column=1, sticky='w', pady=8
        )

        form.columnconfigure(1, weight=1)

        # Results table
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill='both', expand=True)

        cols = ('tag', 'score', 'sentence')
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings', selectmode='browse')
        self.tree.heading('tag', text='Tag/Category')
        self.tree.heading('score', text='Judge Score')
        self.tree.heading('sentence', text='Sentence')
        self.tree.column('tag', width=140, anchor='w')
        self.tree.column('score', width=90, anchor='center')
        self.tree.column('sentence', width=600, anchor='w')
        self.tree.pack(fill='both', expand=True, side='left')

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", lambda e: self.tooltip.hide())

        self.status_label = ttk.Label(self.frame, text="Ready", foreground='gray')
        self.status_label.pack(anchor='w', pady=(6, 0))

    def _on_motion(self, event):
        """Show tooltip with judge_reason when hovering a row."""
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            self.tooltip.hide()
            return
        reason = self.reason_by_item.get(row_id, "")
        if reason:
            x = self.tree.winfo_rootx() + event.x
            y = self.tree.winfo_rooty() + event.y
            self.tooltip.show(reason, x, y)
        else:
            self.tooltip.hide()

    def _set_status(self, msg):
        self.status_label.config(text=msg)
        self.status_callback(msg)

    def _load_users(self):
        """Populate user dropdown from existing RAG indexes."""
        if not self.indexes_dir.exists():
            self.user_combo['values'] = []
            return
        users = [p.stem.replace('_rag', '') for p in self.indexes_dir.glob("*_rag.pkl")]
        self.user_combo['values'] = users
        if users:
            self.user_combo.current(0)

    def run_scoring(self):
        """Retrieve + judge score sentences for the given query."""
        self.reason_by_item.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        user = self.user_var.get().strip()
        if not user:
            messagebox.showwarning("Missing user", "Select a RAG index user first.")
            return
        query = self.query_text.get("1.0", "end").strip()
        if not query:
            messagebox.showwarning("Missing query", "Enter a job description or query text.")
            return

        try:
            idx = resume_rag.UserRAGIndex(user, str(self.indexes_dir))
            if not idx.exists():
                messagebox.showerror("Index not found", f"No index found for user '{user}'.")
                return
            top_k = max(1, min(int(self.topk_var.get()), 50))
            results = idx.retrieve(query, top_k=top_k)
            judged = idx.judge_relevance(query, results, max_items=top_k)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run judge scoring: {e}")
            self._set_status("Error running judge scoring")
            return

        # Populate table grouped by category/tag
        for item in judged:
            meta = item.get('metadata', {}) or {}
            tag = meta.get('category') or meta.get('section') or 'unknown'
            score = item.get('judge_score', 0)
            sent = item.get('text', '')
            reason = item.get('judge_reason', '')
            row_id = self.tree.insert('', 'end', values=(tag, f"{score}/100", sent))
            self.reason_by_item[row_id] = reason

        self._set_status(f"Scored {len(judged)} sentences for {user}")

