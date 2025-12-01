"""
Import Review Tab - Three sub-tabs for reviewing PDF resume imports
Categorization, Extraction Quality, and Impact Score views
With non-blocking async re-scoring on edits
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from typing import Callable, Optional
from pathlib import Path
import sys

# Add parent to path for package imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from resume_gen.pdf_parser import PDFParser, ParsedSentence, ReviewSession
from resume_gen.user_manager import UserManager


class LoadingSpinner(ttk.Frame):
    """Animated loading spinner widget"""
    
    SPINNER_CHARS = ['◐', '◓', '◑', '◒']  # Rotating moon phases
    
    def __init__(self, parent, text: str = "Loading...", **kwargs):
        super().__init__(parent, **kwargs)
        
        self.spinner_idx = 0
        self.is_spinning = False
        self.after_id = None
        
        # Spinner label
        self.spinner_label = ttk.Label(self, text=self.SPINNER_CHARS[0], font=('Arial', 14))
        self.spinner_label.pack(side='left', padx=(0, 5))
        
        # Text label
        self.text_var = tk.StringVar(value=text)
        self.text_label = ttk.Label(self, textvariable=self.text_var)
        self.text_label.pack(side='left')
        
        # Start hidden
        self.pack_forget()
    
    def start(self, text: str = None):
        """Start the spinning animation"""
        if text:
            self.text_var.set(text)
        self.is_spinning = True
        self.pack(pady=5)
        self._animate()
    
    def stop(self):
        """Stop the spinning animation"""
        self.is_spinning = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.pack_forget()
    
    def _animate(self):
        """Animate the spinner"""
        if not self.is_spinning:
            return
        
        self.spinner_idx = (self.spinner_idx + 1) % len(self.SPINNER_CHARS)
        self.spinner_label.config(text=self.SPINNER_CHARS[self.spinner_idx])
        self.after_id = self.after(100, self._animate)


class SentenceCard(ttk.Frame):
    """A card widget displaying a single sentence with scores and edit capability"""
    
    def __init__(self, parent, sentence: ParsedSentence, 
                 on_edit_callback: Callable[[ParsedSentence, str], None],
                 on_use_suggestion: Callable[[ParsedSentence], None],
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        self.sentence = sentence
        self.on_edit_callback = on_edit_callback
        self.on_use_suggestion = on_use_suggestion
        self.is_editing = False
        
        self.configure(relief='solid', borderwidth=1, padding=10)
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create card layout"""
        # Top row: Category badge and scores
        header_frame = ttk.Frame(self)
        header_frame.pack(fill='x', pady=(0, 5))
        
        # Category badge
        cat_color = self._get_category_color(self.sentence.category)
        self.category_label = ttk.Label(
            header_frame, 
            text=f"📁 {self.sentence.category.title()}",
            font=('Arial', 9, 'bold'),
            foreground=cat_color
        )
        self.category_label.pack(side='left')
        
        # Scores on the right
        scores_frame = ttk.Frame(header_frame)
        scores_frame.pack(side='right')
        
        self.conf_label = self._create_score_label(
            scores_frame, "Conf", self.sentence.categorization_confidence
        )
        self.qual_label = self._create_score_label(
            scores_frame, "Quality", self.sentence.extraction_quality
        )
        self.impact_label = self._create_score_label(
            scores_frame, "Impact", self.sentence.impact_score
        )
        
        # Main text area (display mode)
        self.display_frame = ttk.Frame(self)
        self.display_frame.pack(fill='x', pady=5)
        
        self.text_label = ttk.Label(
            self.display_frame, 
            text=self.sentence.get_display_text(),
            wraplength=600,
            font=('Arial', 10)
        )
        self.text_label.pack(side='left', fill='x', expand=True)
        
        # Edit button
        self.edit_btn = ttk.Button(
            self.display_frame, 
            text="✏️ Edit",
            width=8,
            command=self._start_edit
        )
        self.edit_btn.pack(side='right', padx=(10, 0))
        
        # Edit area (hidden initially)
        self.edit_frame = ttk.Frame(self)
        
        self.edit_text = tk.Text(self.edit_frame, height=3, font=('Arial', 10), wrap='word')
        self.edit_text.pack(fill='x', pady=5)
        
        edit_btns = ttk.Frame(self.edit_frame)
        edit_btns.pack(fill='x')
        
        ttk.Button(edit_btns, text="💾 Save & Re-score", command=self._save_edit).pack(side='left', padx=(0, 5))
        ttk.Button(edit_btns, text="❌ Cancel", command=self._cancel_edit).pack(side='left')
        
        # Loading spinner for re-scoring
        self.spinner = LoadingSpinner(self, text="Re-scoring...")
        
        # Suggestion area (if impact suggestion exists)
        if self.sentence.impact_suggestion and self.sentence.impact_suggestion != self.sentence.text:
            self._create_suggestion_area()
        
        # Issues area (if extraction issues exist)
        if self.sentence.extraction_issues:
            self._create_issues_area()
        
        # Tags
        if self.sentence.tags:
            tags_frame = ttk.Frame(self)
            tags_frame.pack(fill='x', pady=(5, 0))
            
            ttk.Label(tags_frame, text="Tags:", font=('Arial', 8)).pack(side='left')
            for tag in self.sentence.tags[:5]:  # Limit to 5 tags
                ttk.Label(
                    tags_frame, 
                    text=tag,
                    font=('Arial', 8),
                    foreground='#666',
                    background='#eee',
                    padding=(3, 1)
                ).pack(side='left', padx=2)
    
    def _create_score_label(self, parent, name: str, score: int) -> ttk.Label:
        """Create a score indicator label"""
        color = self._get_score_color(score)
        label = ttk.Label(
            parent,
            text=f"{name}: {score}",
            font=('Arial', 9),
            foreground=color
        )
        label.pack(side='left', padx=5)
        return label
    
    def _create_suggestion_area(self):
        """Create the suggestion panel"""
        sugg_frame = ttk.LabelFrame(self, text="💡 Impact Suggestion", padding=5)
        sugg_frame.pack(fill='x', pady=5)
        
        ttk.Label(
            sugg_frame,
            text=self.sentence.impact_suggestion,
            wraplength=550,
            font=('Arial', 10, 'italic'),
            foreground='#2d5aa0'
        ).pack(side='left', fill='x', expand=True)
        
        ttk.Button(
            sugg_frame,
            text="Use This",
            command=self._use_suggestion
        ).pack(side='right')
    
    def _create_issues_area(self):
        """Create the extraction issues panel"""
        issues_frame = ttk.LabelFrame(self, text="⚠️ Issues", padding=5)
        issues_frame.pack(fill='x', pady=5)
        
        for issue in self.sentence.extraction_issues:
            ttk.Label(
                issues_frame,
                text=f"• {issue}",
                font=('Arial', 9),
                foreground='#c44'
            ).pack(anchor='w')
    
    def _get_category_color(self, category: str) -> str:
        """Get color for category badge"""
        colors = {
            'skills': '#2e7d32',
            'experience': '#1565c0',
            'achievements': '#f57c00',
            'projects': '#7b1fa2',
            'education': '#00838f',
            'certifications': '#558b2f',
            'summary': '#5d4037'
        }
        return colors.get(category, '#666')
    
    def _get_score_color(self, score: int) -> str:
        """Get color based on score value"""
        if score >= 80:
            return '#2e7d32'  # Green
        elif score >= 60:
            return '#f57c00'  # Orange
        else:
            return '#c62828'  # Red
    
    def _start_edit(self):
        """Switch to edit mode"""
        self.is_editing = True
        self.display_frame.pack_forget()
        self.edit_frame.pack(fill='x', pady=5, before=self.spinner)
        
        self.edit_text.delete('1.0', 'end')
        self.edit_text.insert('1.0', self.sentence.get_display_text())
        self.edit_text.focus_set()
    
    def _cancel_edit(self):
        """Cancel editing and return to display mode"""
        self.is_editing = False
        self.edit_frame.pack_forget()
        self.display_frame.pack(fill='x', pady=5, before=self.spinner)
    
    def _save_edit(self):
        """Save edit and trigger re-scoring"""
        new_text = self.edit_text.get('1.0', 'end-1c').strip()
        
        if not new_text:
            messagebox.showwarning("Empty Text", "Please enter some text")
            return
        
        # If text unchanged, just cancel
        if new_text == self.sentence.get_display_text():
            self._cancel_edit()
            return
        
        # Switch to display mode with loading
        self.edit_frame.pack_forget()
        self.text_label.config(text=new_text)
        self.display_frame.pack(fill='x', pady=5)
        
        # Show spinner and trigger callback
        self.spinner.start("Re-scoring with LLM...")
        self.edit_btn.config(state='disabled')
        
        # Call the edit callback (parent handles async)
        self.on_edit_callback(self.sentence, new_text)
    
    def _use_suggestion(self):
        """Use the impact suggestion"""
        self.on_use_suggestion(self.sentence)
    
    def update_after_rescore(self):
        """Update display after re-scoring completes"""
        self.spinner.stop()
        self.edit_btn.config(state='normal')
        
        # Update text
        self.text_label.config(text=self.sentence.get_display_text())
        
        # Update scores
        self.conf_label.config(
            text=f"Conf: {self.sentence.categorization_confidence}",
            foreground=self._get_score_color(self.sentence.categorization_confidence)
        )
        self.qual_label.config(
            text=f"Quality: {self.sentence.extraction_quality}",
            foreground=self._get_score_color(self.sentence.extraction_quality)
        )
        self.impact_label.config(
            text=f"Impact: {self.sentence.impact_score}",
            foreground=self._get_score_color(self.sentence.impact_score)
        )
        
        # Update category
        self.category_label.config(
            text=f"📁 {self.sentence.category.title()}",
            foreground=self._get_category_color(self.sentence.category)
        )
        
        self.is_editing = False


class ImportReviewTab(ttk.Frame):
    """Main import review tab with three sub-tabs"""
    
    def __init__(self, parent, user_manager: UserManager, status_callback: Callable[[str], None] = None):
        super().__init__(parent, padding="10")
        
        self.user_manager = user_manager
        self.status_callback = status_callback or (lambda x: None)
        self.pdf_parser = PDFParser()
        
        self.current_user: Optional[str] = None
        self.review_session: Optional[ReviewSession] = None
        self.sentence_cards: dict = {}  # Map sentence -> card widget
        
        self._create_widgets()
    
    def set_current_user(self, username: str):
        """Set the current user for import"""
        self.current_user = username
        self._update_status()
    
    def _create_widgets(self):
        """Create the main layout"""
        # Top: File selection and parse controls
        top_frame = ttk.LabelFrame(self, text="📄 Import PDF Resume", padding="10")
        top_frame.pack(fill='x', pady=(0, 10))
        
        # File path
        file_row = ttk.Frame(top_frame)
        file_row.pack(fill='x', pady=5)
        
        ttk.Label(file_row, text="PDF File:").pack(side='left')
        
        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_row, textvariable=self.file_path_var, width=60)
        self.file_entry.pack(side='left', padx=5, fill='x', expand=True)
        
        ttk.Button(file_row, text="📂 Browse", command=self._browse_file).pack(side='left', padx=5)
        
        # Parse button and progress
        action_row = ttk.Frame(top_frame)
        action_row.pack(fill='x', pady=5)
        
        self.parse_btn = ttk.Button(action_row, text="🔍 Parse & Analyze", command=self._parse_pdf)
        self.parse_btn.pack(side='left')
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(action_row, variable=self.progress_var, maximum=1.0, length=300)
        self.progress_bar.pack(side='left', padx=10)
        
        self.progress_label = ttk.Label(action_row, text="")
        self.progress_label.pack(side='left')
        
        # Loading spinner for initial parse
        self.main_spinner = LoadingSpinner(top_frame, text="Parsing PDF...")
        
        # Sub-tabs notebook
        self.sub_notebook = ttk.Notebook(self)
        self.sub_notebook.pack(fill='both', expand=True, pady=10)
        
        # Create three sub-tabs
        self.categorization_tab = self._create_sub_tab("📁 Categorization")
        self.quality_tab = self._create_sub_tab("✨ Extraction Quality")
        self.impact_tab = self._create_sub_tab("⚡ Impact Score")
        
        self.sub_notebook.add(self.categorization_tab['frame'], text="📁 Categorization")
        self.sub_notebook.add(self.quality_tab['frame'], text="✨ Extraction Quality")
        self.sub_notebook.add(self.impact_tab['frame'], text="⚡ Impact Score")
        
        # Bottom: Import button
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill='x', pady=(10, 0))
        
        self.import_btn = ttk.Button(
            bottom_frame, 
            text="✅ Import All to Library",
            command=self._import_to_library,
            state='disabled'
        )
        self.import_btn.pack(side='right')
        
        self.stats_label = ttk.Label(bottom_frame, text="No sentences loaded")
        self.stats_label.pack(side='left')
    
    def _create_sub_tab(self, title: str) -> dict:
        """Create a scrollable sub-tab"""
        frame = ttk.Frame(self.sub_notebook)
        
        # Canvas for scrolling
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Filter/sort options
        filter_frame = ttk.Frame(scrollable_frame)
        filter_frame.pack(fill='x', pady=5)
        
        ttk.Label(filter_frame, text="Filter:").pack(side='left')
        filter_var = tk.StringVar(value="all")
        
        ttk.Radiobutton(filter_frame, text="All", variable=filter_var, value="all").pack(side='left', padx=5)
        ttk.Radiobutton(filter_frame, text="Low Score (<70)", variable=filter_var, value="low").pack(side='left', padx=5)
        ttk.Radiobutton(filter_frame, text="Has Suggestions", variable=filter_var, value="suggestions").pack(side='left', padx=5)
        
        # Content frame for cards
        content_frame = ttk.Frame(scrollable_frame)
        content_frame.pack(fill='both', expand=True)
        
        return {
            'frame': frame,
            'canvas': canvas,
            'scrollable': scrollable_frame,
            'content': content_frame,
            'filter_var': filter_var
        }
    
    def _browse_file(self):
        """Open file dialog to select PDF"""
        filepath = filedialog.askopenfilename(
            title="Select Resume PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filepath:
            self.file_path_var.set(filepath)
    
    def _parse_pdf(self):
        """Parse the selected PDF file"""
        filepath = self.file_path_var.get().strip()
        
        if not filepath:
            messagebox.showwarning("No File", "Please select a PDF file first")
            return
        
        if not Path(filepath).exists():
            messagebox.showerror("File Not Found", f"File not found: {filepath}")
            return
        
        # Check PDF library availability
        if self.pdf_parser.pdf_library is None:
            messagebox.showerror(
                "Missing Dependency", 
                "No PDF library available.\nInstall with: pip install pdfplumber"
            )
            return
        
        # Disable parse button during parsing
        self.parse_btn.config(state='disabled')
        self.progress_var.set(0)
        
        # Parse in background thread
        def do_parse():
            def progress_callback(progress: float, message: str):
                self.after(0, lambda: self._update_progress(progress, message))
            
            session = self.pdf_parser.parse_pdf(filepath, progress_callback)
            self.after(0, lambda: self._on_parse_complete(session))
        
        thread = threading.Thread(target=do_parse, daemon=True)
        thread.start()
    
    def _update_progress(self, progress: float, message: str):
        """Update progress bar (called from main thread)"""
        self.progress_var.set(progress)
        self.progress_label.config(text=message)
    
    def _on_parse_complete(self, session: ReviewSession):
        """Handle parse completion"""
        self.parse_btn.config(state='normal')
        self.review_session = session
        
        # Show any errors
        if session.parse_errors:
            error_msg = "\n".join(session.parse_errors)
            if not session.sentences:
                messagebox.showerror("Parse Failed", f"Errors:\n{error_msg}")
                return
            else:
                messagebox.showwarning("Parse Warnings", f"Warnings:\n{error_msg}")
        
        if not session.sentences:
            messagebox.showwarning("No Content", "No sentences found in the PDF")
            return
        
        # Populate sub-tabs
        self._populate_tabs()
        
        # Update stats
        self._update_stats()
        
        # Enable import button
        self.import_btn.config(state='normal')
        
        self.status_callback(f"Parsed {len(session.sentences)} sentences from PDF")
    
    def _populate_tabs(self):
        """Populate all three sub-tabs with sentence cards"""
        if not self.review_session:
            return
        
        # Clear existing cards
        for tab_data in [self.categorization_tab, self.quality_tab, self.impact_tab]:
            for widget in tab_data['content'].winfo_children():
                widget.destroy()
        
        self.sentence_cards.clear()
        
        # Group by category for categorization tab
        by_category = {}
        for sentence in self.review_session.sentences:
            cat = sentence.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(sentence)
        
        # Categorization tab - grouped by category
        for category, sentences in sorted(by_category.items()):
            # Category header
            header = ttk.Label(
                self.categorization_tab['content'],
                text=f"━━━ {category.upper()} ({len(sentences)}) ━━━",
                font=('Arial', 11, 'bold')
            )
            header.pack(fill='x', pady=(10, 5))
            
            for sentence in sentences:
                card = SentenceCard(
                    self.categorization_tab['content'],
                    sentence,
                    on_edit_callback=self._on_sentence_edit,
                    on_use_suggestion=self._on_use_suggestion
                )
                card.pack(fill='x', pady=3, padx=5)
                self.sentence_cards[id(sentence)] = {'categorization': card}
        
        # Quality tab - sorted by extraction quality (low first)
        sorted_by_quality = sorted(self.review_session.sentences, key=lambda s: s.extraction_quality)
        
        ttk.Label(
            self.quality_tab['content'],
            text="Sentences sorted by extraction quality (lowest first)",
            font=('Arial', 10, 'italic'),
            foreground='gray'
        ).pack(pady=5)
        
        for sentence in sorted_by_quality:
            card = SentenceCard(
                self.quality_tab['content'],
                sentence,
                on_edit_callback=self._on_sentence_edit,
                on_use_suggestion=self._on_use_suggestion
            )
            card.pack(fill='x', pady=3, padx=5)
            
            if id(sentence) in self.sentence_cards:
                self.sentence_cards[id(sentence)]['quality'] = card
            else:
                self.sentence_cards[id(sentence)] = {'quality': card}
        
        # Impact tab - sorted by impact score (low first)
        sorted_by_impact = sorted(self.review_session.sentences, key=lambda s: s.impact_score)
        
        ttk.Label(
            self.impact_tab['content'],
            text="Sentences sorted by impact score (lowest first)",
            font=('Arial', 10, 'italic'),
            foreground='gray'
        ).pack(pady=5)
        
        for sentence in sorted_by_impact:
            card = SentenceCard(
                self.impact_tab['content'],
                sentence,
                on_edit_callback=self._on_sentence_edit,
                on_use_suggestion=self._on_use_suggestion
            )
            card.pack(fill='x', pady=3, padx=5)
            
            if id(sentence) in self.sentence_cards:
                self.sentence_cards[id(sentence)]['impact'] = card
            else:
                self.sentence_cards[id(sentence)] = {'impact': card}
    
    def _on_sentence_edit(self, sentence: ParsedSentence, new_text: str):
        """Handle sentence edit - trigger async re-scoring"""
        # Mark as rescoring
        sentence.is_rescoring = True
        
        def do_rescore():
            # This runs in background thread
            self.pdf_parser.rescore_sentence(sentence, new_text)
            sentence.is_rescoring = False
            
            # Update UI in main thread
            self.after(0, lambda: self._on_rescore_complete(sentence))
        
        thread = threading.Thread(target=do_rescore, daemon=True)
        thread.start()
    
    def _on_rescore_complete(self, sentence: ParsedSentence):
        """Handle re-score completion"""
        # Update all cards for this sentence
        cards = self.sentence_cards.get(id(sentence), {})
        for card in cards.values():
            card.update_after_rescore()
        
        self._update_stats()
        self.status_callback("Re-scoring complete")
    
    def _on_use_suggestion(self, sentence: ParsedSentence):
        """Use the impact suggestion for a sentence"""
        if sentence.impact_suggestion:
            self._on_sentence_edit(sentence, sentence.impact_suggestion)
    
    def _update_stats(self):
        """Update the stats label"""
        if not self.review_session:
            self.stats_label.config(text="No sentences loaded")
            return
        
        total = len(self.review_session.sentences)
        low_conf = len(self.review_session.get_low_confidence())
        low_quality = len(self.review_session.get_low_quality())
        low_impact = len(self.review_session.get_low_impact())
        
        self.stats_label.config(
            text=f"Total: {total} | Low Conf: {low_conf} | Low Quality: {low_quality} | Low Impact: {low_impact}"
        )
    
    def _update_status(self):
        """Update status based on current state"""
        if not self.current_user:
            self.import_btn.config(state='disabled')
            self.status_callback("Select a user before importing")
        elif self.review_session:
            self.import_btn.config(state='normal')
            self.status_callback(f"Ready to import to {self.current_user}")
        else:
            self.import_btn.config(state='disabled')
    
    def _import_to_library(self):
        """Import all reviewed sentences to user's library"""
        if not self.current_user:
            messagebox.showwarning("No User", "Please select a user first")
            return
        
        if not self.review_session or not self.review_session.sentences:
            messagebox.showwarning("No Sentences", "No sentences to import")
            return
        
        # Confirm import
        count = len(self.review_session.sentences)
        if not messagebox.askyesno(
            "Confirm Import",
            f"Import {count} sentences to {self.current_user}'s library?"
        ):
            return
        
        # Import each sentence
        imported = 0
        duplicates = 0
        
        # Get existing sentences for duplicate detection
        existing = self.user_manager.get_sentences_flat(self.current_user)
        existing_texts = {s['text'].lower().strip() for s in existing}
        
        for sentence in self.review_session.sentences:
            text = sentence.get_display_text()
            
            # Skip duplicates
            if text.lower().strip() in existing_texts:
                duplicates += 1
                continue
            
            # Determine category and tags
            category = sentence.user_category_override or sentence.category
            tags = sentence.tags if sentence.tags else None
            
            # Map category to sentence type
            sentence_type = category
            if sentence_type not in ['skills', 'experience', 'achievements', 'projects', 'education', 'certifications']:
                sentence_type = 'experience'  # Default
            
            # Use first tag as category for skills/experience
            sub_category = None
            if tags and sentence_type in ['skills', 'experience']:
                sub_category = tags[0]
                tags = tags[1:] if len(tags) > 1 else None
            
            # Add to library
            success = self.user_manager.add_sentence(
                self.current_user,
                sentence_type,
                text,
                sub_category,
                tags
            )
            
            if success:
                imported += 1
                existing_texts.add(text.lower().strip())
        
        # Report results
        msg = f"Imported {imported} sentences"
        if duplicates > 0:
            msg += f"\nSkipped {duplicates} duplicates"
        
        messagebox.showinfo("Import Complete", msg)
        self.status_callback(f"Imported {imported} sentences to {self.current_user}")
        
        # Clear the review session
        self.review_session = None
        self._clear_tabs()
        self.import_btn.config(state='disabled')
        self._update_stats()
    
    def _clear_tabs(self):
        """Clear all sentence cards from tabs"""
        for tab_data in [self.categorization_tab, self.quality_tab, self.impact_tab]:
            for widget in tab_data['content'].winfo_children():
                widget.destroy()
        self.sentence_cards.clear()


# Quick test
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Import Review Test")
    root.geometry("900x700")
    
    um = UserManager()
    
    tab = ImportReviewTab(root, um, lambda msg: print(f"Status: {msg}"))
    tab.pack(fill='both', expand=True)
    
    root.mainloop()
