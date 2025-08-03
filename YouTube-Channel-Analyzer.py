import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import logging
import pickle
from datetime import datetime
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
import time
import webbrowser
from collections import defaultdict
from functools import lru_cache

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_analyzer.log'),
        logging.StreamHandler()
    ]
)

class YouTubeAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Channel Analyzer - Versione Ottimizzata")
        self.root.geometry("900x750")
        
        # Variabili
        self.api_key = tk.StringVar()
        self.channel_url = tk.StringVar()
        self.channel_data = None
        self.videos = []
        self.filtered_videos = []
        self.api_calls_count = 0
        self.youtube = None  # Cache dell'istanza YouTube API
        
        # Cache per ottimizzazione
        self._video_cache = {}
        self._search_cache = defaultdict(set)
        
        # Rate limiting
        self.last_api_call = 0
        self.api_call_delay = 0.1  # 100ms tra le chiamate (default)
        self.aggressive_mode = False  # Per strategia Complete
        
        # Inizializza variabili mancanti
        self.api_keys = []
        self.current_api_key_index = 0
        self.session_state = None
        self.session_file = None
        self.debug_info = {
            'playlist_pages': 0,
            'search_pages': 0,
            'quota_errors': 0,
            'other_errors': 0,
            'last_error': '',
            'strategies_used': []
        }
        
        # Carica configurazione se esiste
        self.load_config()
        
        # Assicura che api_keys sia sempre una lista
        if not hasattr(self, 'api_keys') or not self.api_keys:
            self.api_keys = []
            # Se c'è una key nell'entry, aggiungila alla lista
            if self.api_key.get():
                self.api_keys = [self.api_key.get()]
        
        # Crea interfaccia
        self.create_widgets()
        
        # Stile
        self.setup_style()
        
    def setup_style(self):
        """Configura lo stile dell'interfaccia"""
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Info.TLabel', font=('Arial', 10))
        
    def create_widgets(self):
        """Crea tutti i widget dell'interfaccia"""
        # Frame principale
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurazione griglia
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # --- Sezione API Key --- 
        ttk.Label(main_frame, text="YouTube API Key:", style='Title.TLabel').grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        api_frame = ttk.Frame(main_frame)
        api_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.api_entry = ttk.Entry(api_frame, textvariable=self.api_key, show="*", width=50)
        self.api_entry.grid(row=0, column=0, padx=(0, 5))
        
        ttk.Button(api_frame, text="Mostra/Nascondi", 
                  command=self.toggle_api_visibility).grid(row=0, column=1, padx=5)
        
        ttk.Button(api_frame, text="Salva API Key", 
                  command=self.save_config).grid(row=0, column=2, padx=5)
        
        ttk.Button(api_frame, text="Gestisci Keys", 
                  command=self.manage_api_keys).grid(row=0, column=3, padx=5)
        
        # Label per mostrare quale API key è in uso
        self.api_status_label = ttk.Label(api_frame, text="", font=('Arial', 9))
        self.api_status_label.grid(row=1, column=0, columnspan=4, pady=(5, 0))
        
        # Aggiorna status iniziale
        self.update_api_status()
        
        # --- Sezione URL Canale --- 
        ttk.Label(main_frame, text="URL Canale YouTube:", style='Title.TLabel').grid(
            row=2, column=0, sticky=tk.W, pady=(10, 5))
        
        url_frame = ttk.Frame(main_frame)
        url_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.url_entry = ttk.Entry(url_frame, textvariable=self.channel_url, width=50)
        self.url_entry.grid(row=0, column=0, padx=(0, 5))
        
        self.analyze_btn = ttk.Button(url_frame, text="Analizza Canale", 
                                     command=self.analyze_channel)
        self.analyze_btn.grid(row=0, column=1, padx=5)
        
        # --- Sezione Informazioni Canale --- 
        info_frame = ttk.LabelFrame(main_frame, text="Informazioni Canale", padding="10")
        info_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.info_text = tk.Text(info_frame, height=6, width=70, wrap=tk.WORD)
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.info_text.config(state=tk.DISABLED)
        
        # --- Sezione Filtri --- 
        filter_frame = ttk.LabelFrame(main_frame, text="Filtri Video", padding="10")
        filter_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Filtro keyword
        ttk.Label(filter_frame, text="Cerca nel titolo:").grid(row=0, column=0, sticky=tk.W)
        self.keyword_var = tk.StringVar()
        self.keyword_entry = ttk.Entry(filter_frame, textvariable=self.keyword_var, width=30)
        self.keyword_entry.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        # Modalità di ricerca
        self.search_mode = tk.StringVar(value="AND")
        mode_frame = ttk.Frame(filter_frame)
        mode_frame.grid(row=0, column=2, padx=(10, 5))
        
        ttk.Radiobutton(mode_frame, text="Tutte", variable=self.search_mode, 
                       value="AND").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="Almeno una", variable=self.search_mode, 
                       value="OR").pack(side=tk.LEFT)
        
        # Filtro views
        ttk.Label(filter_frame, text="Views minime:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.min_views_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.min_views_var, width=15).grid(
            row=1, column=1, padx=5, sticky=tk.W, pady=(5, 0))
        
        # Filtri durata
        duration_frame = ttk.Frame(filter_frame)
        duration_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(duration_frame, text="Durata:").pack(side=tk.LEFT)
        
        ttk.Label(duration_frame, text="da").pack(side=tk.LEFT, padx=(10, 5))
        self.min_duration_var = tk.StringVar()
        min_dur_entry = ttk.Entry(duration_frame, textvariable=self.min_duration_var, width=8)
        min_dur_entry.pack(side=tk.LEFT)
        
        ttk.Label(duration_frame, text="a").pack(side=tk.LEFT, padx=5)
        self.max_duration_var = tk.StringVar()
        max_dur_entry = ttk.Entry(duration_frame, textvariable=self.max_duration_var, width=8)
        max_dur_entry.pack(side=tk.LEFT)
        
        ttk.Label(duration_frame, text="(minuti o mm:ss)").pack(side=tk.LEFT, padx=(5, 0))
        
        # Preset durata
        preset_frame = ttk.Frame(filter_frame)
        preset_frame.grid(row=2, column=2, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        ttk.Button(preset_frame, text="Shorts", width=8,
                  command=lambda: self.set_duration_preset(0, 1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Brevi", width=8,
                  command=lambda: self.set_duration_preset(1, 10)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Medi", width=8,
                  command=lambda: self.set_duration_preset(10, 30)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Lunghi", width=8,
                  command=lambda: self.set_duration_preset(30, None)).pack(side=tk.LEFT, padx=2)
        
        # Filtri data pubblicazione
        date_range_frame = ttk.Frame(filter_frame)
        date_range_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(date_range_frame, text="Data pubblicazione:").pack(side=tk.LEFT)
        
        ttk.Label(date_range_frame, text="da").pack(side=tk.LEFT, padx=(10, 5))
        self.start_date_var = tk.StringVar()
        start_date_entry = ttk.Entry(date_range_frame, textvariable=self.start_date_var, width=10)
        start_date_entry.pack(side=tk.LEFT)
        
        ttk.Label(date_range_frame, text="a").pack(side=tk.LEFT, padx=5)
        self.end_date_var = tk.StringVar()
        end_date_entry = ttk.Entry(date_range_frame, textvariable=self.end_date_var, width=10)
        end_date_entry.pack(side=tk.LEFT)
        
        ttk.Label(date_range_frame, text="(AAAA-MM-GG)").pack(side=tk.LEFT, padx=(5, 0))
        
        # Case sensitive e parola completa
        options_frame = ttk.Frame(filter_frame)
        options_frame.grid(row=1, column=2, columnspan=2, pady=(5, 0))
        
        self.case_sensitive = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Maiuscole/minuscole", 
                       variable=self.case_sensitive).pack(side=tk.LEFT, padx=(0, 10))
        
        self.whole_word = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Parola completa", 
                       variable=self.whole_word).pack(side=tk.LEFT)
        
        # Help text
        help_text = "Suggerimenti: virgola per separare | -parola per escludere | \"frase esatta\" | Durata: 5 o 5:30"
        ttk.Label(filter_frame, text=help_text, font=('Arial', 8, 'italic')).grid(
            row=4, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))
        
        # Pulsanti filtro
        button_frame = ttk.Frame(filter_frame)
        button_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        ttk.Button(button_frame, text="Applica Filtri", 
                  command=self.apply_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset Filtri", 
                  command=self.reset_filters).pack(side=tk.LEFT, padx=5)
        
        # --- Sezione Lista Video --- 
        video_frame = ttk.LabelFrame(main_frame, text="Lista Video", padding="10")
        video_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        main_frame.rowconfigure(6, weight=1)
        
        # Treeview per i video
        columns = ('Titolo', 'Views', 'Like', 'Data', 'Durata')
        self.video_tree = ttk.Treeview(video_frame, columns=columns, show='tree headings', height=12)
        
        # Configura colonne
        self.video_tree.column('#0', width=50)
        self.video_tree.column('Titolo', width=400)
        self.video_tree.column('Views', width=100)
        self.video_tree.column('Like', width=80)
        self.video_tree.column('Data', width=100)
        self.video_tree.column('Durata', width=80)
        
        # Intestazioni
        self.video_tree.heading('#0', text='#')
        self.video_tree.heading('Titolo', text='Titolo')
        self.video_tree.heading('Views', text='Views')
        self.video_tree.heading('Like', text='Like')
        self.video_tree.heading('Data', text='Data')
        self.video_tree.heading('Durata', text='Durata')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(video_frame, orient=tk.VERTICAL, command=self.video_tree.yview)
        self.video_tree.configure(yscrollcommand=scrollbar.set)
        
        self.video_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)
        
        # Doppio click per aprire video
        self.video_tree.bind('<Double-Button-1>', self.open_video)
        
        # --- Sezione Controlli --- 
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=7, column=0, columnspan=3, pady=10)
        
        self.load_strategy = tk.StringVar(value="smart")
        strategy_frame = ttk.LabelFrame(control_frame, text="Strategia di caricamento", padding="5")
        strategy_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Radiobutton(strategy_frame, text="Smart", variable=self.load_strategy, 
                       value="smart", command=self.update_strategy_info).pack(side=tk.LEFT)
        ttk.Radiobutton(strategy_frame, text="Veloce", variable=self.load_strategy, 
                       value="fast", command=self.update_strategy_info).pack(side=tk.LEFT)
        ttk.Radiobutton(strategy_frame, text="Completo", variable=self.load_strategy, 
                       value="complete", command=self.update_strategy_info).pack(side=tk.LEFT)
        
        self.get_videos_btn = ttk.Button(control_frame, text="Carica Video", 
                                        command=self.load_all_videos, state=tk.DISABLED)
        self.get_videos_btn.pack(side=tk.LEFT, padx=5)
        
        self.export_btn = ttk.Button(control_frame, text="Esporta CSV", 
                                    command=self.export_csv, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        self.export_filtered_btn = ttk.Button(control_frame, text="Esporta Filtrati", 
                                             command=self.export_filtered_csv, state=tk.DISABLED)
        self.export_filtered_btn.pack(side=tk.LEFT, padx=5)
        
        # Pulsanti per sessione
        session_frame = ttk.Frame(control_frame)
        session_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        ttk.Button(session_frame, text="💾 Salva Sessione", 
                  command=self.save_session).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(session_frame, text="📂 Carica Sessione", 
                  command=self.load_session).pack(side=tk.LEFT, padx=2)
        
        # Pulsante debug
        ttk.Button(control_frame, text="🐛 Debug Info", 
                  command=self.show_debug_info).pack(side=tk.LEFT, padx=(10, 0))
        
        # --- Status Bar --- 
        self.status_var = tk.StringVar()
        self.status_var.set("Pronto")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        self.progress.grid_remove()
        
        # Log iniziale
        logging.info(f"YouTube Analyzer avviato - {datetime.now()}")
        logging.info(f"Versione: Ottimizzata con multi-API support")
    
    def update_strategy_info(self):
        """Aggiorna le informazioni sulla strategia selezionata"""
        strategy = self.load_strategy.get()
        info = {
            "smart": "Ottimizzata: ~80% video, ~200 API calls per 20k+ video",
            "fast": "Veloce: max 3000 video recenti, ~60 API calls",
            "complete": "⚠️ Completa: TUTTI i video, 500+ API calls per 20k+ video"
        }
        self.update_status(f"Strategia: {info.get(strategy, '')}")
    
    def toggle_api_visibility(self):
        """Mostra/nascondi l'API key"""
        if self.api_entry['show'] == '*':
            self.api_entry.config(show='')
        else:
            self.api_entry.config(show='*')
    
    def save_config(self):
        """Salva la configurazione"""
        config = {
            'api_keys': self.api_keys if self.api_keys else [self.api_key.get()],
            'current_key': self.api_key.get()
        }
        try:
            with open('youtube_analyzer_config.json', 'w') as f:
                json.dump(config, f)
            messagebox.showinfo("Successo", "Configurazione salvata!")
            self.update_api_status()
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel salvataggio: {str(e)}")
    
    def load_config(self):
        """Carica la configurazione se esiste"""
        try:
            if os.path.exists('youtube_analyzer_config.json'):
                with open('youtube_analyzer_config.json', 'r') as f:
                    config = json.load(f)
                    
                    # Gestisci vecchio formato (singola key)
                    if 'api_key' in config:
                        self.api_keys = [config['api_key']]
                        self.api_key.set(config['api_key'])
                    else:
                        self.api_keys = config.get('api_keys', [])
                        if self.api_keys:
                            self.api_key.set(config.get('current_key', self.api_keys[0]))
        except Exception as e:
            logging.error(f"Errore caricamento config: {e}")
            self.api_keys = []
    
    def manage_api_keys(self):
        """Gestisci multiple API keys"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Gestione API Keys")
        dialog.geometry("600x400")
        
        # Frame principale
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Lista keys
        ttk.Label(main_frame, text="API Keys disponibili:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        # Listbox con scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.keys_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=10)
        self.keys_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.keys_listbox.yview)
        
        # Popola lista
        for i, key in enumerate(self.api_keys):
            display_key = f"Key {i+1}: {key[:10]}...{key[-10:]}" if len(key) > 20 else f"Key {i+1}: {key}"
            self.keys_listbox.insert(tk.END, display_key)
        
        # Frame per aggiungere key
        add_frame = ttk.Frame(main_frame)
        add_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(add_frame, text="Nuova API Key:").pack(side=tk.LEFT)
        new_key_var = tk.StringVar()
        new_key_entry = ttk.Entry(add_frame, textvariable=new_key_var, width=40)
        new_key_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        def add_key():
            key = new_key_var.get().strip()
            if key and key not in self.api_keys:
                self.api_keys.append(key)
                display_key = f"Key {len(self.api_keys)}: {key[:10]}...{key[-10:]}" if len(key) > 20 else f"Key {len(self.api_keys)}: {key}"
                self.keys_listbox.insert(tk.END, display_key)
                new_key_var.set("")
                if len(self.api_keys) == 1:
                    self.api_key.set(key)
                self.save_config()
        
        ttk.Button(add_frame, text="Aggiungi", command=add_key).pack(side=tk.LEFT)
        
        # Pulsanti azioni
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def remove_selected():
            selection = self.keys_listbox.curselection()
            if selection:
                index = selection[0]
                self.keys_listbox.delete(index)
                del self.api_keys[index]
                self.save_config()
        
        def set_primary():
            selection = self.keys_listbox.curselection()
            if selection:
                index = selection[0]
                self.api_key.set(self.api_keys[index])
                self.current_api_key_index = index
                self.update_api_status()
                messagebox.showinfo("Successo", f"API Key {index+1} impostata come primaria")
        
        ttk.Button(button_frame, text="Rimuovi Selezionata", command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Imposta come Primaria", command=set_primary).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Chiudi", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def update_api_status(self):
        """Aggiorna status delle API keys"""
        if hasattr(self, 'api_status_label'):
            if self.api_keys:
                status = f"API Keys: {len(self.api_keys)} disponibili | Attiva: Key {self.current_api_key_index + 1}"
            else:
                status = "Nessuna API Key configurata"
            self.api_status_label.config(text=status)
    
    def rotate_api_key(self):
        """Ruota alla prossima API key disponibile"""
        if len(self.api_keys) <= 1:
            return False
        
        self.current_api_key_index = (self.current_api_key_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_api_key_index]
        self.api_key.set(new_key)
        self.youtube = None  # Reset servizio per usare nuova key
        
        logging.info(f"Rotazione API Key: passato a Key {self.current_api_key_index + 1}")
        self.update_api_status()
        self.update_status(f"Cambiata API Key: usando Key {self.current_api_key_index + 1}")
        
        return True
    
    def save_session(self):
        """Salva lo stato corrente della sessione"""
        if not self.channel_data:
            messagebox.showwarning("Attenzione", "Nessun canale analizzato da salvare")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".session",
            filetypes=[("Session files", "*.session"), ("All files", "*.*")],
            initialfile=f"youtube_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.session"
        )
        
        if filename:
            try:
                session_data = {
                    'channel_url': self.channel_url.get(),
                    'channel_data': self.channel_data,
                    'videos': self.videos,
                    'video_cache': self._video_cache,
                    'search_cache': dict(self._search_cache),
                    'api_calls_count': self.api_calls_count,
                    'debug_info': self.debug_info,
                    'timestamp': datetime.now().isoformat()
                }
                
                with open(filename, 'wb') as f:
                    pickle.dump(session_data, f)
                
                self.session_file = filename
                messagebox.showinfo("Successo", f"Sessione salvata!\n{len(self.videos)} video salvati")
                logging.info(f"Sessione salvata: {filename}")
                
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nel salvataggio: {str(e)}")
                logging.error(f"Errore salvataggio sessione: {e}")
    
    def load_session(self):
        """Carica una sessione salvata"""
        filename = filedialog.askopenfilename(
            filetypes=[("Session files", "*.session"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'rb') as f:
                    session_data = pickle.load(f)
                
                # Ripristina stato
                self.channel_url.set(session_data['channel_url'])
                self.channel_data = session_data['channel_data']
                self.videos = session_data['videos']
                self._video_cache = session_data['video_cache']
                self._search_cache = defaultdict(set, session_data['search_cache'])
                self.api_calls_count = session_data.get('api_calls_count', 0)
                self.debug_info = session_data.get('debug_info', self.debug_info)
                
                self.session_file = filename
                
                # Aggiorna UI
                self.display_channel_info()
                self.display_videos(self.videos)
                self.filtered_videos = self.videos.copy()
                
                # Abilita pulsanti
                self.get_videos_btn.config(state=tk.NORMAL)
                self.export_btn.config(state=tk.NORMAL)
                
                saved_date = session_data.get('timestamp', 'N/A')
                total_videos = int(self.channel_data['statistics'].get('videoCount', 0))
                completeness = (len(self.videos) / total_videos * 100) if total_videos > 0 else 0
                
                messagebox.showinfo("Successo", 
                    f"Sessione caricata!\n"
                    f"Video: {len(self.videos):,} ({completeness:.1f}%)\n"
                    f"Salvata il: {saved_date[:19]}")
                
                self.update_status(f"Sessione caricata: {len(self.videos):,} video")
                logging.info(f"Sessione caricata: {filename}")
                
                # Chiedi se continuare caricamento
                if completeness < 95:
                    if messagebox.askyesno("Continua Caricamento?", 
                        f"La sessione contiene solo il {completeness:.1f}% dei video.\n"
                        f"Vuoi continuare il caricamento da dove era stato interrotto?"):
                        self.load_all_videos()
                
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nel caricamento: {str(e)}")
                logging.error(f"Errore caricamento sessione: {e}")
    
    def show_debug_info(self):
        """Mostra informazioni di debug"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Debug Information")
        dialog.geometry("800x600")
        
        # Text widget con scrollbar
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text = tk.Text(frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)
        
        # Prepara debug info
        total_videos = int(self.channel_data['statistics'].get('videoCount', 0)) if self.channel_data else 'N/A'
        total_videos_str = f"{total_videos:,}" if isinstance(total_videos, int) else total_videos
        
        info = f"""=== DEBUG INFORMATION ===
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CHANNEL INFO:
- URL: {self.channel_url.get()}
- Video totali dichiarati: {total_videos_str}
- Video caricati: {len(self.videos):,}
- Video in cache: {len(self._video_cache):,}

API CALLS:
- Totale chiamate API: {self.api_calls_count}
- API Keys disponibili: {len(self.api_keys)}
- Key attuale: {self.current_api_key_index + 1} di {len(self.api_keys)}

CARICAMENTO DETTAGLI:
- Pagine playlist caricate: {self.debug_info['playlist_pages']}
- Pagine search caricate: {self.debug_info['search_pages']}
- Errori quota: {self.debug_info['quota_errors']}
- Altri errori: {self.debug_info['other_errors']}
- Ultimo errore: {self.debug_info['last_error']}

STRATEGIE USATE:
{chr(10).join(f"- {s}" for s in self.debug_info['strategies_used'])}

VIDEO IDs UNICI TROVATI:
- Totale: {len(set(v['video_id'] for v in self.videos))}
- Duplicati rimossi: {len(self.videos) - len(set(v['video_id'] for v in self.videos))}

ANALISI TEMPORALE:
"""
        
        if self.videos:
            # Analisi per anno
            year_counts = defaultdict(int)
            for video in self.videos:
                year = video['data_pubblicazione'][:4]
                year_counts[year] += 1
            
            info += "\nVideo per anno:\n"
            for year in sorted(year_counts.keys(), reverse=True):
                info += f"  {year}: {year_counts[year]:,} video\n"
        
        # Log degli ultimi errori
        info += "\n=== ULTIMI LOG ERRORI ===\n"
        try:
            with open('youtube_analyzer.log', 'r') as f:
                lines = f.readlines()
                error_lines = [l for l in lines[-100:] if 'ERROR' in l or 'quota' in l.lower()]
                info += ''.join(error_lines[-20:])  # Ultimi 20 errori
        except:
            info += "Impossibile leggere il file di log\n"
        
        text.insert(1.0, info)
        text.config(state=tk.DISABLED)
        
        # Pulsanti
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def save_debug():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"debug_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text.get(1.0, tk.END))
                messagebox.showinfo("Salvato", "Debug info salvato!")
        
        ttk.Button(button_frame, text="Salva Debug Info", command=save_debug).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Chiudi", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def get_youtube_service(self):
        """Ottiene o crea l'istanza del servizio YouTube con caching"""
        if not self.youtube:
            current_key = self.api_key.get()
            if not current_key and self.api_keys:
                current_key = self.api_keys[self.current_api_key_index]
                self.api_key.set(current_key)
            
            self.youtube = build('youtube', 'v3', developerKey=current_key)
            logging.info(f"YouTube service creato con Key {self.current_api_key_index + 1}")
        return self.youtube
    
    def rate_limit(self):
        """Implementa rate limiting per le API calls"""
        # Modalità aggressiva per strategia Complete
        delay = 0.05 if self.aggressive_mode else self.api_call_delay
        
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        if time_since_last_call < delay:
            time.sleep(delay - time_since_last_call)
        self.last_api_call = time.time()
    
    def analyze_channel(self):
        """Analizza il canale in un thread separato"""
        if not self.api_key.get():
            messagebox.showerror("Errore", "Inserisci l'API Key!")
            return
        
        if not self.channel_url.get():
            messagebox.showerror("Errore", "Inserisci l'URL del canale!")
            return
        
        # Reset cache quando si analizza un nuovo canale
        self._video_cache.clear()
        self._search_cache.clear()
        
        # Avvia analisi in thread
        thread = threading.Thread(target=self._analyze_channel_thread)
        thread.daemon = True
        thread.start()
    
    def _analyze_channel_thread(self):
        """Thread per l'analisi del canale"""
        self.update_status("Analisi del canale in corso...")
        self.show_progress(True)
        self.api_calls_count = 0
        
        try:
            youtube = self.get_youtube_service()
            
            # Estrai channel ID
            channel_id = self.extract_channel_id(youtube, self.channel_url.get())
            if not channel_id:
                self.update_status("Errore: Canale non trovato")
                self.show_progress(False)
                return
            
            # Ottieni info canale
            self.rate_limit()
            response = youtube.channels().list(
                part='snippet,statistics,contentDetails',
                id=channel_id
            ).execute()
            self.api_calls_count += 1
            
            if response['items']:
                self.channel_data = response['items'][0]
                self.display_channel_info()
                self.update_status(f"Analisi completata! (API calls: {self.api_calls_count})")
                
                # Abilita pulsanti
                self.root.after(0, lambda: self.get_videos_btn.config(state=tk.NORMAL))
            else:
                self.update_status("Canale non trovato")
                
        except Exception as e:
            self.update_status(f"Errore: {str(e)}")
            messagebox.showerror("Errore", str(e))
        finally:
            self.show_progress(False)
    
    def extract_channel_id(self, youtube, channel_url):
        """Estrae l'ID del canale dall'URL in modo efficiente"""
        # Patterns per diversi tipi di URL YouTube
        patterns = [
            (r'youtube\.com/channel/([a-zA-Z0-9_-]+)', 'direct'),
            (r'youtube\.com/c/([a-zA-Z0-9_-]+)', 'custom'),
            (r'youtube\.com/@([a-zA-Z0-9_.-]+)', 'handle'),
            (r'youtube\.com/user/([a-zA-Z0-9_-]+)', 'user'),
            (r'youtube\.com/([a-zA-Z0-9_-]+)$', 'simple')
        ]
        
        for pattern, type_match in patterns:
            match = re.search(pattern, channel_url)
            if match:
                identifier = match.group(1)
                
                if type_match == 'direct':
                    return identifier
                
                # Per handle, prova prima il metodo più efficiente
                if type_match == 'handle':
                    try:
                        self.rate_limit()
                        response = youtube.channels().list(
                            part='id',
                            forHandle=identifier,
                            maxResults=1
                        ).execute()
                        self.api_calls_count += 1
                        
                        if response['items']:
                            return response['items'][0]['id']
                    except Exception as e:
                        logging.error(f"Errore nella ricerca handle: {e}")
                        pass
                
                # Usa search come fallback
                try:
                    self.rate_limit()
                    response = youtube.search().list(
                        part='snippet',
                        q=identifier,
                        type='channel',
                        maxResults=1
                    ).execute()
                    self.api_calls_count += 1
                    
                    if response['items']:
                        return response['items'][0]['snippet']['channelId']
                        
                except Exception as e:
                    logging.error(f"Errore nella ricerca del canale: {e}")
                    continue
        
        return None
    
    def display_channel_info(self):
        """Mostra le informazioni del canale"""
        if not self.channel_data:
            return
        
        stats = self.channel_data['statistics']
        snippet = self.channel_data['snippet']
        
        # Gestisce il caso in cui subscriberCount possa essere nascosto
        subscriber_count = stats.get('subscriberCount', 'N/A')
        if subscriber_count != 'N/A' and subscriber_count.isdigit():
            subscriber_count = f"{int(subscriber_count):,}"
        
        info = f"""Nome: {snippet['title']}
Iscritti: {subscriber_count}
Video totali: {int(stats.get('videoCount', 0)):,}
Visualizzazioni totali: {int(stats.get('viewCount', 0)):,}
Data creazione: {snippet['publishedAt'][:10]}
"""
        
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info)
        self.info_text.config(state=tk.DISABLED)
    
    def load_all_videos(self):
        """Carica i video del canale"""
        if not self.channel_data:
            return
        
        thread = threading.Thread(target=self._load_videos_thread)
        thread.daemon = True
        thread.start()
    
    def _load_videos_thread(self):
        """Thread ottimizzato per caricare i video"""
        self.update_status("Caricamento video in corso...")
        self.show_progress(True)
        self.videos = []
        start_api_calls = self.api_calls_count
        
        try:
            youtube = self.get_youtube_service()
            strategy = self.load_strategy.get()
            total_video_count = int(self.channel_data['statistics'].get('videoCount', 0))
            
            # Avviso per canali molto grandi
            if total_video_count > 10000:
                self.update_status(f"⚠️ Canale con {total_video_count:,} video rilevato...")
                if strategy == "complete":
                    self.update_status("🚨 Strategia Complete per canale grande: potrebbe richiedere 30+ minuti!")
                    
                # Avviso speciale per canali enormi
                if total_video_count > 100000:
                    response = messagebox.askyesno("Canale Molto Grande", 
                        f"Questo canale ha {total_video_count:,} video!\n\n"
                        f"⚠️ LIMITAZIONI YOUTUBE API:\n"
                        f"• La Playlist API può recuperare max ~20,000 video\n"
                        f"• La Search API ha limiti non documentati (~500 pagine)\n"
                        f"• Alcuni video potrebbero essere privati/non listati\n\n"
                        f"Per canali TV/broadcast come questo:\n"
                        f"• Aspettati di recuperare 10-30% dei video totali\n"
                        f"• Molti video potrebbero essere clip brevi o non indicizzate\n"
                        f"• Considera di filtrare per periodo specifico\n\n"
                        f"Continuo comunque?")
                    
                    if not response:
                        self.update_status("Caricamento annullato dall'utente")
                        self.show_progress(False)
                        return
            
            if strategy == "fast":
                self._load_videos_fast(youtube)
            elif strategy == "complete":
                self._load_videos_complete(youtube, total_video_count)
            else:  # smart
                self._load_videos_smart(youtube, total_video_count)
            
            # Ordina i video per data (più recenti prima)
            self.videos.sort(key=lambda x: x['data_pubblicazione'], reverse=True)
            
            # Mostra video
            self.display_videos(self.videos)
            self.filtered_videos = self.videos.copy()
            
            # Analizza video mancanti
            missing_analysis = self._analyze_missing_videos()
            
            api_used = self.api_calls_count - start_api_calls
            completeness = (len(self.videos) / total_video_count * 100) if total_video_count > 0 else 100
            status_msg = f"Caricati {len(self.videos):,} video ({completeness:.1f}% del totale) - API calls: {api_used}"
            
            # Aggiungi info sulla strategia usata e video mancanti
            if strategy == "complete" and completeness < 95:
                status_msg += f" | ⚠️ {total_video_count - len(self.videos):,} video non trovati"
                
                # Se ci sono molti video mancanti, mostra analisi dettagliata
                if missing_analysis and missing_analysis['percentage'] > 10:
                    causes_str = "\n• ".join(missing_analysis['causes'])
                    messagebox.showwarning("Video Mancanti", 
                        f"Non è stato possibile trovare tutti i video:\n\n"
                        f"Video dichiarati: {total_video_count:,}\n"
                        f"Video trovati: {len(self.videos):,}\n"
                        f"Video mancanti: {missing_analysis['missing']:,} ({missing_analysis['percentage']:.1f}%)\n\n"
                        f"Possibili cause:\n• {causes_str}\n\n"
                        f"Suggerimenti:\n"
                        f"• Aggiungi più API keys per continuare\n"
                        f"• Salva la sessione e riprendi più tardi\n"
                        f"• Verifica il log per dettagli sugli errori")
                        
            elif strategy == "smart" and completeness < 80:
                status_msg += " | 💡 Usa strategia 'Complete' per più video"
                
            self.update_status(status_msg)
            
            # Abilita pulsanti
            self.root.after(0, lambda: self.export_btn.config(state=tk.NORMAL))
            
        except Exception as e:
            self.update_status(f"Errore: {str(e)}")
            messagebox.showerror("Errore", str(e))
        finally:
            self.show_progress(False)
    
    def _analyze_missing_videos(self):
        """Analizza perché alcuni video non vengono trovati"""
        if not self.channel_data:
            return None
            
        total_declared = int(self.channel_data['statistics'].get('videoCount', 0))
        total_found = len(self.videos)
        missing = total_declared - total_found
        
        if missing > 0:
            logging.warning(f"Video mancanti: {missing:,} ({missing/total_declared*100:.1f}%)")
            
            # Analizza distribuzione temporale
            if self.videos:
                oldest_date = min(v['data_pubblicazione'] for v in self.videos)
                newest_date = max(v['data_pubblicazione'] for v in self.videos)
                
                # Conta video per anno
                year_counts = defaultdict(int)
                for v in self.videos:
                    year = int(v['data_pubblicazione'][:4])
                    year_counts[year] += 1
                
                # Trova anni con pochi video (possibili gap)
                avg_per_year = total_found / len(year_counts) if year_counts else 0
                gaps = []
                for year in range(min(year_counts.keys()), max(year_counts.keys()) + 1):
                    if year_counts[year] < avg_per_year * 0.5:
                        gaps.append((year, year_counts[year]))
                
                logging.info(f"Range video trovati: {oldest_date[:10]} - {newest_date[:10]}")
                logging.info(f"Anni con pochi video (possibili gap): {gaps}")
                
                # Possibili cause
                causes = []
                if int(oldest_date[:4]) > 2010:
                    causes.append("Video più vecchi del 2010 potrebbero non essere indicizzati")
                if missing > total_found * 0.5:
                    causes.append("Possibili video privati/eliminati/non listati")
                if self.debug_info['quota_errors'] > 0:
                    causes.append(f"Quota API esaurita {self.debug_info['quota_errors']} volte")
                if total_declared > 50000:
                    causes.append("YouTube API limita i risultati per canali molto grandi")
                if 'La7' in self.channel_data['snippet']['title'] or total_declared > 100000:
                    causes.append("Canali broadcast TV hanno spesso metadati non standard")
                    
                # Controlla se ci sono limiti API specifici
                if len(self.videos) > 0:
                    # YouTube Search API ha un limite non documentato di ~500-1000 pagine
                    if self.debug_info['search_pages'] > 400:
                        causes.append("Raggiunto limite pagine Search API (~500 pagine)")
                    if self.debug_info['playlist_pages'] > 400:
                        causes.append("Raggiunto limite pagine Playlist API")
                    
                logging.info(f"Possibili cause video mancanti: {', '.join(causes)}")
                
                return {
                    'missing': missing,
                    'percentage': missing/total_declared*100,
                    'date_range': (oldest_date[:10], newest_date[:10]),
                    'gaps': gaps,
                    'causes': causes
                }
        return None
    
    def _load_videos_smart(self, youtube, total_count):
        """Strategia smart: bilancia completezza e efficienza"""
        if total_count <= 500:
            # Per canali piccoli usa playlist API
            self._load_from_playlist(youtube, max_pages=20)
        elif total_count <= 3000:
            # Per canali medi usa combinazione
            self._load_from_playlist(youtube, max_pages=60)
            if len(self.videos) < total_count * 0.8:
                self._load_from_search(youtube, max_results=1000)
        else:
            # Per canali grandi usa strategia mista ottimizzata
            self.update_status(f"📊 Canale grande ({total_count:,} video). Caricamento ottimizzato...")
            
            # Fase 1: Playlist per video recenti
            self._load_from_playlist(youtube, max_pages=200)  # Aumentato da 100
            
            # Fase 2: Search ottimizzata
            if len(self.videos) < total_count * 0.7:
                self._load_from_search_optimized(youtube, total_count)
    
    def _load_videos_fast(self, youtube):
        """Strategia veloce: carica solo i video più recenti"""
        self._load_from_playlist(youtube, max_pages=60)
    
    def _load_videos_complete(self, youtube, total_count):
        """Strategia completa: prova a caricare tutti i video"""
        # Attiva modalità aggressiva per velocizzare
        self.aggressive_mode = True
        
        try:
            # Prima usa playlist API al massimo
            self.update_status("📥 Fase 1: Caricamento via Playlist API...")
            self._load_from_playlist(youtube, max_pages=500)  # Nessun limite pratico
            
            # Poi usa search comprehensiva
            if len(self.videos) < total_count * 0.95:
                self.update_status(f"🔍 Fase 2: Ricerca completa ({len(self.videos):,}/{total_count:,} video)...")
                self._load_from_search_comprehensive(youtube, total_count)
        finally:
            # Disattiva modalità aggressiva
            self.aggressive_mode = False
    
    def _load_from_playlist(self, youtube, max_pages=None):
        """Carica video dalla playlist uploads con gestione quota"""
        playlist_id = self.channel_data['contentDetails']['relatedPlaylists']['uploads']
        
        # Se abbiamo già una sessione, riprendi da dove eravamo
        if self.session_state and isinstance(self.session_state, dict) and 'playlist_token' in self.session_state:
            next_page_token = self.session_state['playlist_token']
            page_count = self.session_state.get('playlist_pages', 0)
            logging.info(f"Ripresa playlist da pagina {page_count} con token: {next_page_token[:20] if next_page_token else 'None'}...")
        else:
            next_page_token = None
            page_count = 0
        
        while True:
            if max_pages and page_count >= max_pages:
                break
                
            try:
                self.rate_limit()
                response = youtube.playlistItems().list(
                    part='contentDetails',
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()
                self.api_calls_count += 1
                page_count += 1
                self.debug_info['playlist_pages'] += 1
                
                video_ids = [item['contentDetails']['videoId'] for item in response['items']]
                
                if video_ids:
                    self._load_video_details_batch(youtube, video_ids)
                
                self.update_status(f"Playlist: {len(self.videos)} video caricati (pagina {page_count})...")
                
                # Salva stato per ripresa
                self.session_state = {
                    'playlist_token': response.get('nextPageToken'),
                    'playlist_pages': page_count
                }
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    logging.info(f"Playlist completata dopo {page_count} pagine")
                    break
                    
                # Rate limiting adattivo
                if page_count % 10 == 0:
                    time.sleep(0.5)
                    
            except HttpError as e:
                self.debug_info['last_error'] = str(e)
                if e.resp.status == 403:
                    self.debug_info['quota_errors'] += 1
                    logging.error(f"Quota esaurita su playlist (pagina {page_count})")
                    
                    # Prova a ruotare API key
                    if self.rotate_api_key():
                        youtube = self.get_youtube_service()
                        self.update_status("Quota esaurita, cambio API key...")
                        time.sleep(2)  # Pausa prima di riprovare
                        continue
                    else:
                        self.update_status("⚠️ Quota API esaurita su tutte le keys!")
                        break
                else:
                    self.debug_info['other_errors'] += 1
                    logging.error(f"Errore playlist: {e}")
                    raise e
    
    def _load_from_search(self, youtube, max_results=2000):
        """Carica video usando search API standard"""
        channel_id = self._get_channel_id()
        if not channel_id:
            return
            
        next_page_token = None
        results_count = 0
        existing_ids = {v['video_id'] for v in self.videos}
        
        while results_count < max_results:
            try:
                self.rate_limit()
                response = youtube.search().list(
                    part='id',
                    channelId=channel_id,
                    type='video',
                    maxResults=50,
                    pageToken=next_page_token,
                    order='date'
                ).execute()
                self.api_calls_count += 1
                
                new_video_ids = []
                for item in response['items']:
                    video_id = item['id']['videoId']
                    if video_id not in existing_ids:
                        new_video_ids.append(video_id)
                        existing_ids.add(video_id)
                
                if new_video_ids:
                    self._load_video_details_batch(youtube, new_video_ids)
                    results_count += len(new_video_ids)
                
                self.update_status(f"Search: {len(self.videos)} video totali...")
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(new_video_ids) == 0:
                    break
                    
            except HttpError as e:
                if e.resp.status == 403:
                    break
                else:
                    print(f"Errore search: {e}")
                    break
    
    def _load_from_search_optimized(self, youtube, total_count):
        """Strategia di ricerca ottimizzata per canali grandi"""
        channel_id = self._get_channel_id()
        if not channel_id:
            return
            
        existing_ids = {v['video_id'] for v in self.videos}
        
        # Strategia 1: Ricerca per periodi recenti (ultimi 10 anni)
        current_year = datetime.now().year
        for year in range(current_year, max(2010, current_year - 10), -1):
            if len(self.videos) > min(total_count * 0.9, 50000):  # Aumentato limite
                break
                
            self._search_by_year(youtube, channel_id, year, existing_ids, max_pages=30)
        
        # Strategia 2: Diversi ordinamenti per trovare video mancanti
        for order in ['viewCount', 'relevance', 'rating']:
            if len(self.videos) > min(total_count * 0.95, 60000):  # Aumentato limite
                break
                
            self._search_by_order(youtube, channel_id, order, existing_ids, max_pages=20)
    
    def _load_from_search_comprehensive(self, youtube, total_count):
        """Ricerca completa per canali che vogliono tutti i video"""
        channel_id = self._get_channel_id()
        if not channel_id:
            logging.error("Channel ID non trovato per ricerca comprehensiva")
            return
            
        existing_ids = {v['video_id'] for v in self.videos}
        initial_count = len(self.videos)
        
        # NESSUN LIMITE - Continua fino a trovare tutti i video
        self.update_status("⚠️ Modalità Complete: potrebbe richiedere molto tempo e molte API calls...")
        logging.info(f"Inizio ricerca comprehensiva. Video esistenti: {initial_count}")
        
        # Cerca per tutti gli anni
        current_year = datetime.now().year
        for year in range(2005, current_year + 1):
            if self.debug_info['quota_errors'] > 5:
                logging.warning("Troppe quote errors, interrompo ricerca")
                break
                
            videos_before = len(self.videos)
            self._search_by_year(youtube, channel_id, year, existing_ids, max_pages=100)
            videos_after = len(self.videos)
            
            if videos_after - videos_before > 0:
                logging.info(f"Anno {year}: trovati {videos_after - videos_before} nuovi video")
        
        # Cerca con tutti gli ordinamenti per trovare video mancanti
        orders = ['date', 'viewCount', 'relevance', 'rating', 'title']
        for order in orders:
            if self.debug_info['quota_errors'] > 10:
                break
                
            old_count = len(self.videos)
            self._search_by_order(youtube, channel_id, order, existing_ids, max_pages=100)
            new_count = len(self.videos)
            
            if new_count - old_count > 0:
                logging.info(f"Ordinamento {order}: trovati {new_count - old_count} nuovi video")
            
            # Se questo ordinamento ha trovato molti nuovi video, riprova
            if new_count - old_count > 100:
                self._search_by_order(youtube, channel_id, order, existing_ids, max_pages=100)
        
        # Ricerca aggiuntiva per mesi se mancano ancora video
        current_ratio = len(self.videos) / total_count if total_count > 0 else 1
        if current_ratio < 0.95:
            self.update_status(f"🔍 Ricerca dettagliata per mesi ({len(self.videos):,}/{total_count:,} = {current_ratio*100:.1f}%)...")
            
            # Focus sugli ultimi 10 anni dove ci sono probabilmente più video
            for year in range(max(2010, current_year - 15), current_year + 1):
                if self.debug_info['quota_errors'] > 20:
                    break
                    
                for month in range(1, 13):
                    videos_before = len(self.videos)
                    self._search_by_month(youtube, channel_id, year, month, existing_ids, max_pages=20)
                    videos_after = len(self.videos)
                    
                    if videos_after - videos_before > 0:
                        logging.info(f"Mese {year}-{month:02d}: trovati {videos_after - videos_before} nuovi video")
        
        final_count = len(self.videos)
        logging.info(f"Ricerca comprehensiva completata. Video trovati: {final_count - initial_count} nuovi, totale: {final_count}")
    
    def _search_by_year(self, youtube, channel_id, year, existing_ids, max_pages=20):
        """Cerca video di un anno specifico con gestione quota"""
        next_page_token = None
        page_count = 0
        
        published_after = f"{year}-01-01T00:00:00Z"
        published_before = f"{year + 1}-01-01T00:00:00Z"
        
        self.debug_info['strategies_used'].append(f"Search per anno {year}")
        
        while page_count < max_pages:
            try:
                self.rate_limit()
                response = youtube.search().list(
                    part='id',
                    channelId=channel_id,
                    type='video',
                    maxResults=50,
                    pageToken=next_page_token,
                    publishedAfter=published_after,
                    publishedBefore=published_before,
                    order='date'
                ).execute()
                self.api_calls_count += 1
                page_count += 1
                self.debug_info['search_pages'] += 1
                
                new_video_ids = []
                for item in response['items']:
                    video_id = item['id']['videoId']
                    if video_id not in existing_ids:
                        new_video_ids.append(video_id)
                        existing_ids.add(video_id)
                
                if new_video_ids:
                    self._load_video_details_batch(youtube, new_video_ids)
                
                if len(new_video_ids) > 0:
                    self.update_status(f"Anno {year}: {len(self.videos)} video totali...")
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(new_video_ids) < 10:
                    break
                    
            except HttpError as e:
                self.debug_info['last_error'] = str(e)
                if e.resp.status == 403:
                    self.debug_info['quota_errors'] += 1
                    logging.error(f"Quota esaurita su search anno {year}")
                    
                    # Prova a ruotare API key
                    if self.rotate_api_key():
                        youtube = self.get_youtube_service()
                        self.update_status(f"Quota esaurita per anno {year}, cambio API key...")
                        time.sleep(2)
                        continue
                    else:
                        logging.warning(f"Impossibile completare ricerca anno {year}")
                        break
                else:
                    self.debug_info['other_errors'] += 1
                    logging.error(f"Errore search anno {year}: {e}")
                    break
    
    def _search_by_order(self, youtube, channel_id, order, existing_ids, max_pages=20):
        """Cerca video con un ordinamento specifico"""
        next_page_token = None
        page_count = 0
        consecutive_empty = 0
        
        while page_count < max_pages:
            try:
                self.rate_limit()
                response = youtube.search().list(
                    part='id',
                    channelId=channel_id,
                    type='video',
                    maxResults=50,
                    pageToken=next_page_token,
                    order=order
                ).execute()
                self.api_calls_count += 1
                page_count += 1
                
                new_video_ids = []
                for item in response['items']:
                    video_id = item['id']['videoId']
                    if video_id not in existing_ids:
                        new_video_ids.append(video_id)
                        existing_ids.add(video_id)
                
                if new_video_ids:
                    self._load_video_details_batch(youtube, new_video_ids)
                    consecutive_empty = 0
                else:
                    consecutive_empty += 1
                
                if consecutive_empty > 3:  # Stop se non trova nuovi video
                    break
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                    
            except HttpError:
                break
    
    def _search_by_month(self, youtube, channel_id, year, month, existing_ids, max_pages=10):
        """Cerca video di un mese specifico"""
        next_page_token = None
        page_count = 0
        
        # Calcola date range per il mese
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year
            
        published_after = f"{year}-{month:02d}-01T00:00:00Z"
        published_before = f"{next_year}-{next_month:02d}-01T00:00:00Z"
        
        while page_count < max_pages:
            try:
                self.rate_limit()
                response = youtube.search().list(
                    part='id',
                    channelId=channel_id,
                    type='video',
                    maxResults=50,
                    pageToken=next_page_token,
                    publishedAfter=published_after,
                    publishedBefore=published_before,
                    order='date'
                ).execute()
                self.api_calls_count += 1
                page_count += 1
                
                new_video_ids = []
                for item in response['items']:
                    video_id = item['id']['videoId']
                    if video_id not in existing_ids:
                        new_video_ids.append(video_id)
                        existing_ids.add(video_id)
                
                if new_video_ids:
                    self._load_video_details_batch(youtube, new_video_ids)
                    
                self.update_status(f"Mese {year}-{month:02d}: {len(self.videos)} video totali...")
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(new_video_ids) < 5:
                    break
                    
            except HttpError:
                break
    
    def _get_channel_id(self):
        """Ottiene l'ID del canale dal channel data"""
        # Prova prima dal channel data stesso
        if 'id' in self.channel_data:
            return self.channel_data['id']
            
        # Altrimenti estrai dalla playlist uploads
        playlist_id = self.channel_data['contentDetails']['relatedPlaylists']['uploads']
        if playlist_id.startswith('UU'):
            return 'UC' + playlist_id[2:]
            
        return None
    
    def _load_video_details_batch(self, youtube, video_ids):
        """Carica dettagli video in batch con caching e gestione quota"""
        new_video_ids = [vid for vid in video_ids if vid not in self._video_cache]
        
        if not new_video_ids:
            # Tutti i video sono già in cache
            for vid in video_ids:
                if vid in self._video_cache:
                    self.videos.append(self._video_cache[vid])
            return
        
        # Carica solo i nuovi video
        for i in range(0, len(new_video_ids), 50):
            batch_ids = new_video_ids[i:i+50]
            
            retry_count = 0
            while retry_count < 3:  # Max 3 tentativi
                try:
                    self.rate_limit()
                    response = youtube.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(batch_ids)
                    ).execute()
                    self.api_calls_count += 1
                    
                    for video in response['items']:
                        processed = self._process_video_data(video)
                        if processed:
                            self._video_cache[processed['video_id']] = processed
                            self.videos.append(processed)
                    
                    break  # Successo, esci dal loop retry
                    
                except HttpError as e:
                    self.debug_info['last_error'] = str(e)
                    if e.resp.status == 403:
                        self.debug_info['quota_errors'] += 1
                        logging.error(f"Quota esaurita su video details batch")
                        
                        # Prova a ruotare API key
                        if self.rotate_api_key():
                            youtube = self.get_youtube_service()
                            retry_count += 1
                            time.sleep(2)
                            continue
                        else:
                            logging.error("Impossibile caricare dettagli video - quota esaurita")
                            return
                    else:
                        self.debug_info['other_errors'] += 1
                        logging.error(f"Errore batch details: {e}")
                        break
                except Exception as e:
                    logging.error(f"Errore inaspettato batch details: {e}")
                    break
    
    def _process_video_data(self, video):
        """Processa i dati di un video con gestione errori migliorata"""
        try:
            video_id = video['id']
            snippet = video['snippet']
            stats = video['statistics']
            content = video['contentDetails']
            
            published_at = snippet['publishedAt']
            duration_seconds = self.parse_duration_to_seconds(content['duration'])
            
            return {
                'titolo': snippet['title'],
                'video_id': video_id,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'data_pubblicazione': published_at,
                'date': datetime.fromisoformat(published_at.replace('Z', '+00:00')).date(),
                'durata': self.format_duration(duration_seconds),
                'durata_secondi': duration_seconds,
                'visualizzazioni': int(stats.get('viewCount', 0)),
                'like': int(stats.get('likeCount', 0)),
                'commenti': int(stats.get('commentCount', 0))
            }
        except Exception as e:
            print(f"Errore processamento video: {e}")
            return None
    
    @lru_cache(maxsize=1000)
    def parse_duration_to_seconds(self, duration):
        """Converte durata ISO 8601 in secondi con caching"""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if match:
            hours, minutes, seconds = match.groups()
            hours = int(hours or 0)
            minutes = int(minutes or 0)
            seconds = int(seconds or 0)
            return hours * 3600 + minutes * 60 + seconds
        return 0
    
    def format_duration(self, seconds):
        """Formatta durata da secondi a stringa"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def parse_duration_input(self, duration_str):
        """Converte input durata utente in secondi"""
        duration_str = duration_str.strip()
        if not duration_str:
            return None
            
        try:
            if ':' in duration_str:
                parts = duration_str.split(':')
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return int(float(duration_str)) * 60
        except ValueError:
            return None
    
    def display_videos(self, videos):
        """Mostra i video nella treeview in modo efficiente"""
        # Pulisci treeview
        self.video_tree.delete(*self.video_tree.get_children())
        
        # Limita visualizzazione per performance
        display_limit = 2000
        display_videos = videos[:display_limit]
        
        # Inserisci in batch per migliori performance
        for i, video in enumerate(display_videos, 1):
            self.video_tree.insert('', 'end', values=(
                video['titolo'],
                f"{video['visualizzazioni']:,}",
                f"{video['like']:,}",
                video['data_pubblicazione'][:10],
                video['durata']
            ), text=str(i))
        
        if len(videos) > display_limit:
            self.update_status(f"Mostrando primi {display_limit:,} di {len(videos):,} video. Usa filtri per raffinare.")
    
    def set_duration_preset(self, min_minutes, max_minutes):
        """Imposta preset di durata"""
        self.min_duration_var.set(str(min_minutes) if min_minutes is not None else "")
        self.max_duration_var.set(str(max_minutes) if max_minutes is not None else "")
    
    def apply_filters(self):
        """Applica filtri in modo ottimizzato"""
        if not self.videos:
            messagebox.showinfo("Info", "Carica prima i video del canale!")
            return
        
        # Parti da tutti i video
        self.filtered_videos = self.videos.copy()
        filters_applied = []
        
        # Filtro keyword ottimizzato
        keyword = self.keyword_var.get().strip()
        if keyword:
            self.filtered_videos = self._filter_by_keyword(keyword)
            filters_applied.append(f"Keyword: {keyword}")
        
        # Filtro views
        min_views_str = self.min_views_var.get().strip()
        if min_views_str:
            try:
                min_views = int(min_views_str.replace(',', '').replace('.', ''))
                self.filtered_videos = [v for v in self.filtered_videos 
                                      if v['visualizzazioni'] >= min_views]
                filters_applied.append(f"Views ≥ {min_views:,}")
            except ValueError:
                pass
        
        # Filtro durata
        min_dur = self.parse_duration_input(self.min_duration_var.get())
        max_dur = self.parse_duration_input(self.max_duration_var.get())
        
        if min_dur is not None or max_dur is not None:
            self.filtered_videos = self._filter_by_duration(min_dur, max_dur)
            dur_info = self._format_duration_filter(min_dur, max_dur)
            filters_applied.append(dur_info)
        
        # Filtro data
        start_date = self._parse_date(self.start_date_var.get())
        end_date = self._parse_date(self.end_date_var.get())
        
        if start_date or end_date:
            self.filtered_videos = self._filter_by_date(start_date, end_date)
            date_info = self._format_date_filter(start_date, end_date)
            filters_applied.append(date_info)
        
        # Mostra risultati
        self.display_videos(self.filtered_videos)
        
        # Status
        status = f"Filtrati: {len(self.filtered_videos):,} di {len(self.videos):,} video"
        if filters_applied:
            status += f" | {' | '.join(filters_applied)}"
        self.update_status(status)
        
        # Abilita export se ci sono risultati
        self.export_filtered_btn.config(
            state=tk.NORMAL if self.filtered_videos else tk.DISABLED
        )
    
    def _filter_by_keyword(self, keyword):
        """Filtro keyword ottimizzato"""
        # Parse keyword
        keywords, exclude_keywords = self._parse_keywords(keyword)
        
        if not keywords and not exclude_keywords:
            return self.filtered_videos
        
        case_sensitive = self.case_sensitive.get()
        whole_word = self.whole_word.get()
        mode = self.search_mode.get()
        
        filtered = []
        for video in self.filtered_videos:
            title = video['titolo']
            
            # Check esclusioni
            if any(self._match_keyword(ex_k, title, case_sensitive, whole_word) 
                   for ex_k in exclude_keywords):
                continue
            
            # Check inclusioni
            if keywords:
                if mode == "AND":
                    if all(self._match_keyword(k, title, case_sensitive, whole_word) 
                           for k in keywords):
                        filtered.append(video)
                else:  # OR
                    if any(self._match_keyword(k, title, case_sensitive, whole_word) 
                           for k in keywords):
                        filtered.append(video)
            else:
                filtered.append(video)
        
        return filtered
    
    def _parse_keywords(self, keyword_str):
        """Parse keywords separando inclusioni ed esclusioni"""
        keywords = []
        exclude_keywords = []
        
        # Estrai frasi tra virgolette
        phrases = re.findall(r'"([^"]+)"', keyword_str)
        remaining = keyword_str
        for phrase in phrases:
            remaining = remaining.replace(f'"{phrase}"', '', 1)
        
        # Split rimanenti
        if ',' in remaining:
            parts = [p.strip() for p in remaining.split(',') if p.strip()]
        else:
            parts = [p.strip() for p in remaining.split() if p.strip()]
        
        all_terms = phrases + parts
        
        # Separa inclusioni/esclusioni
        for term in all_terms:
            if term.startswith('-') and len(term) > 1:
                exclude_keywords.append(term[1:])
            elif term:
                keywords.append(term)
        
        return keywords, exclude_keywords
    
    @lru_cache(maxsize=10000)
    def _match_keyword(self, keyword, title, case_sensitive, whole_word):
        """Match keyword con caching"""
        if not case_sensitive:
            keyword = keyword.lower()
            title = title.lower()
        
        if whole_word:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            return bool(re.search(pattern, title, 0 if case_sensitive else re.IGNORECASE))
        else:
            return keyword in title
    
    def _filter_by_duration(self, min_dur, max_dur):
        """Filtra per durata"""
        filtered = []
        for video in self.filtered_videos:
            dur = video['durata_secondi']
            if min_dur is not None and dur < min_dur:
                continue
            if max_dur is not None and dur > max_dur:
                continue
            filtered.append(video)
        return filtered
    
    def _filter_by_date(self, start_date, end_date):
        """Filtra per data"""
        filtered = []
        for video in self.filtered_videos:
            video_date = video['date']
            if start_date and video_date < start_date:
                continue
            if end_date and video_date > end_date:
                continue
            filtered.append(video)
        return filtered
    
    def _parse_date(self, date_str):
        """Parse data con gestione errori"""
        date_str = date_str.strip()
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
    
    def _format_duration_filter(self, min_dur, max_dur):
        """Formatta info filtro durata"""
        if min_dur is not None and max_dur is not None:
            return f"Durata: {self.format_duration(min_dur)} - {self.format_duration(max_dur)}"
        elif min_dur is not None:
            return f"Durata ≥ {self.format_duration(min_dur)}"
        else:
            return f"Durata ≤ {self.format_duration(max_dur)}"
    
    def _format_date_filter(self, start_date, end_date):
        """Formatta info filtro data"""
        if start_date and end_date:
            return f"Data: {start_date} → {end_date}"
        elif start_date:
            return f"Data ≥ {start_date}"
        else:
            return f"Data ≤ {end_date}"
    
    def reset_filters(self):
        """Reset tutti i filtri"""
        self.keyword_var.set("")
        self.min_views_var.set("")
        self.min_duration_var.set("")
        self.max_duration_var.set("")
        self.start_date_var.set("")
        self.end_date_var.set("")
        self.search_mode.set("AND")
        self.case_sensitive.set(False)
        self.whole_word.set(False)
        
        if self.videos:
            self.filtered_videos = self.videos.copy()
            self.display_videos(self.videos)
            self.update_status(f"Totale: {len(self.videos):,} video")
            self.export_filtered_btn.config(state=tk.DISABLED)
    
    def open_video(self, event):
        """Apre il video selezionato"""
        selection = self.video_tree.selection()
        if selection:
            item = self.video_tree.item(selection[0])
            try:
                index = int(item['text']) - 1
                video_list = self.filtered_videos if self.filtered_videos else self.videos
                
                if 0 <= index < len(video_list):
                    webbrowser.open(video_list[index]['url'])
            except:
                pass
    
    def export_csv(self):
        """Esporta tutti i video"""
        self._export_to_csv(self.videos, "tutti_video")
    
    def export_filtered_csv(self):
        """Esporta video filtrati"""
        self._export_to_csv(self.filtered_videos, "video_filtrati")
    
    def _export_to_csv(self, videos, default_name):
        """Export ottimizzato in CSV"""
        if not videos:
            messagebox.showwarning("Attenzione", "Nessun video da esportare")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{default_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            try:
                # Prepara dati per DataFrame
                data = [{
                    'Titolo': v['titolo'],
                    'URL': v['url'],
                    'Data': v['data_pubblicazione'][:10],
                    'Durata': v['durata'],
                    'Views': v['visualizzazioni'],
                    'Like': v['like'],
                    'Commenti': v['commenti']
                } for v in videos]
                
                df = pd.DataFrame(data)
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                
                messagebox.showinfo("Successo", 
                    f"Esportati {len(videos):,} video in:\n{os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore esportazione: {str(e)}")
    
    def update_status(self, message):
        """Aggiorna status bar"""
        self.root.after(0, lambda: self.status_var.set(message))
    
    def show_progress(self, show):
        """Mostra/nasconde progress bar"""
        if show:
            self.root.after(0, self.progress.grid)
            self.root.after(0, self.progress.start)
        else:
            self.root.after(0, self.progress.stop)
            self.root.after(0, self.progress.grid_remove)

def main():
    # Crea directory per log se non esiste
    log_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(log_dir, exist_ok=True)
    
    root = tk.Tk()
    app = YouTubeAnalyzerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()