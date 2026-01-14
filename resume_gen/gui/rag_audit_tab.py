"""RAG Embedding Audit Tab

Scores how well sentences are categorized/tagged (not job relevance) and allows
deleting or changing categories for cleanup before re-indexing.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
import json

from core.llm_client import LocalLLM


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


class RAGAuditTab:
    """Audit existing RAG embeddings for tagging/category accuracy."""

    def __init__(self, parent, user_manager, status_callback=None):
        self.parent = parent
        self.user_manager = user_manager
        self.status_callback = status_callback or (lambda msg: None)
        self.indexes_dir = Path(__file__).parent.parent / 'indexes'
        self.item_data = {}

        self.frame = ttk.Frame(parent, padding="15")
        self.tooltip = _Tooltip(self.frame)
        self.reason_by_item = {}

        self._build_ui()
        self._load_users()

    def _build_ui(self):
        header = ttk.Label(self.frame, text="RAG Embedding Audit", font=('Arial', 12, 'bold'))
        header.pack(anchor='w', pady=(0, 10))

        form = ttk.Frame(self.frame)
        form.pack(fill='x', pady=(0, 10))

        ttk.Label(form, text="User:", width=10).grid(row=0, column=0, sticky='w', pady=4)
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(form, textvariable=self.user_var, state='readonly', width=30)
        self.user_combo.grid(row=0, column=1, sticky='w', pady=4, padx=(5, 0))
        ttk.Button(form, text="Load", command=self.load_sentences).grid(row=0, column=2, padx=(10, 0))

        ttk.Label(form, text="Audit sample (N):", width=14).grid(row=1, column=0, sticky='w', pady=4)
        self.sample_var = tk.IntVar(value=20)
        ttk.Entry(form, textvariable=self.sample_var, width=6).grid(row=1, column=1, sticky='w', pady=4)

        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(btn_frame, text="Run LLM Audit on selection", command=self.run_audit_selection).pack(side='left')
        ttk.Button(btn_frame, text="Run LLM Audit on top N", command=self.run_audit_sample).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Change Category", command=self.change_category).pack(side='right', padx=(5, 0))
        ttk.Button(btn_frame, text="Delete", command=self.delete_selected).pack(side='right')

        # Results table
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill='both', expand=True)

        cols = ('type', 'category', 'tags', 'audit_score', 'suggested', 'sentence')
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings', selectmode='extended')
        self.tree.heading('type', text='Type')
        self.tree.heading('category', text='Category')
        self.tree.heading('tags', text='Tags')
        self.tree.heading('audit_score', text='Audit Score')
        self.tree.heading('suggested', text='Suggested Type')
        self.tree.heading('sentence', text='Sentence')

        self.tree.column('type', width=90, anchor='w')
        self.tree.column('category', width=120, anchor='w')
        self.tree.column('tags', width=140, anchor='w')
        self.tree.column('audit_score', width=90, anchor='center')
        self.tree.column('suggested', width=140, anchor='w')
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

    def _load_users(self):
        users = self.user_manager.list_users()
        self.user_combo['values'] = users
        if users:
            self.user_combo.current(0)

    def set_status(self, msg):
        self.status_label.config(text=msg)
        self.status_callback(msg)

    def load_sentences(self):
        self.reason_by_item.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_data.clear()

        user = self.user_var.get().strip()
        if not user:
            messagebox.showwarning("Select user", "Choose a user first.")
            return

        flat = self.user_manager.get_sentences_flat(user)
        for entry in flat:
            category = entry.get("tags", [None])[0] if entry.get("type") in ("skill", "experience") else ""
            tags = entry.get("tags", [])
            row_id = self.tree.insert(
                '', 'end',
                values=(entry.get("type", ""), category or "", ", ".join(tags), "", "", entry.get("text", ""))
            )
            self.item_data[row_id] = {
                "type": entry.get("type", ""),
                "category": category,
                "tags": tags,
                "text": entry.get("text", "")
            }
        self.set_status(f"Loaded {len(flat)} sentences for {user}")

    def _audit_prompt(self, text, current_type, category, tags):
        tags_str = ", ".join(tags) if tags else "none"
        return f"""
You audit resume sentences for correct categorization. Categories: skill, experience, achievement, education, certifications, projects.

Sentence: "{text}"
Current category: {current_type}
Current subcategory: {category or 'none'}
Current tags: {tags_str}

Tasks:
1) Decide if the current category is correct. Score 0-100 (0 = wrong, 100 = perfect).
2) Suggest the best category from the allowed list.
3) Include a short reason.

Return JSON only:
{{"score": 0-100, "suggested": "skill|experience|achievement|education|certifications|projects", "reason": "why"}}"""

    def _run_llm_audit(self, items):
        llm = LocalLLM()
        for row_id in items:
            data = self.item_data[row_id]
            prompt = self._audit_prompt(
                data.get("text", ""),
                data.get("type", ""),
                data.get("category", ""),
                data.get("tags", [])
            )
            try:
                raw = llm.generate(prompt, stream=False, temperature=0.0, timeout=60)
                start = raw.find('{')
                end = raw.rfind('}') + 1
                payload = raw[start:end] if start != -1 and end > start else raw
                result = json.loads(payload)
                score = int(result.get("score", 0))
                suggested = result.get("suggested", "")
                reason = result.get("reason", "")
            except Exception as e:
                score = 0
                suggested = ""
                reason = f"Error: {e}"

            self.tree.set(row_id, 'audit_score', f"{score}/100")
            self.tree.set(row_id, 'suggested', suggested)
            self.reason_by_item[row_id] = reason
        self.set_status(f"Audited {len(items)} sentence(s)")

    def run_audit_selection(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select rows", "Select one or more rows to audit.")
            return
        self._run_llm_audit(selected)

    def run_audit_sample(self):
        n = max(1, int(self.sample_var.get() or 1))
        items = self.tree.get_children()[:n]
        if not items:
            messagebox.showinfo("No rows", "Load sentences first.")
            return
        self._run_llm_audit(items)

    def delete_selected(self):
        user = self.user_var.get().strip()
        if not user:
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select rows", "Select rows to delete.")
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(selected)} sentence(s)?"):
            return

        for row_id in selected:
            data = self.item_data.get(row_id, {})
            stype = data.get("type")
            text = data.get("text", "")
            category = data.get("category")
            if stype in ("skill", "experience"):
                self.user_manager.remove_sentence(user, stype + "s", text, category=category)
            else:
                self.user_manager.remove_sentence(user, stype + "s", text)
        # Rebuild index to stay in sync
        self.user_manager.rebuild_rag_index(user)
        self.load_sentences()
        self.set_status("Deleted and rebuilt index")

    def change_category(self):
        user = self.user_var.get().strip()
        if not user:
            return
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showinfo("Select one", "Select a single row to change category.")
            return
        row_id = selected[0]
        data = self.item_data.get(row_id, {})
        text = data.get("text", "")
        old_type = data.get("type", "")
        old_category = data.get("category", "")

        new_type = simpledialog.askstring("New Type", "Enter new type (skill, experience, achievement, education, certifications, projects):", initialvalue=old_type)
        if not new_type:
            return
        new_type = new_type.lower()
        if new_type not in ["skill", "experience", "achievement", "education", "certifications", "projects"]:
            messagebox.showerror("Invalid", "Unsupported type.")
            return
        new_category = None
        if new_type in ("skill", "experience"):
            new_category = simpledialog.askstring("New Category", "Enter category (e.g., python, leadership):", initialvalue=old_category or "")

        # Remove old
        if old_type in ("skill", "experience"):
            self.user_manager.remove_sentence(user, old_type + "s", text, category=old_category)
        else:
            self.user_manager.remove_sentence(user, old_type + "s", text)
        # Add new
        self.user_manager.add_sentence(user, new_type + "s", text, category=new_category, tags=data.get("tags", []))
        self.user_manager.rebuild_rag_index(user)
        self.load_sentences()
        self.set_status(f"Updated type to {new_type}")

