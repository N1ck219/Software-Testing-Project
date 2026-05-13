import subprocess
import time
import json
import os
import shutil
import re
from pathlib import Path
import psutil
import threading
from dotenv import load_dotenv
from google import genai

from scripts.config import RESULTS_FILE

def get_bin_path(name):
    """Restituisce il percorso del binario nella venv se esiste, altrimenti il nome."""
    venv_bin = Path(".venv/bin") / name
    if venv_bin.exists():
        return str(venv_bin)
    return name

def setup_directories():
    """Inizializza le cartelle e pulisce i vecchi dati globali una sola volta all'avvio."""
    print("📁 Inizializzazione cartelle e pulizia vecchi benchmark...")
    
    # 1. Rimuove i vecchi file JSON e HTML globali
    old_global_files = [RESULTS_FILE, "results/summary_dashboard.html"]
    for f in old_global_files:
        path = Path(f)
        if path.exists():
            path.unlink()
            
    # 2. Svuota le cartelle dei report specifici (mantenendo i .gitkeep)
    dirs_to_empty = ["results/cosmic_ray", "results/mutmut", "results/pynguin"]
    for d in dirs_to_empty:
        path = Path(d)
        if path.exists() and path.is_dir():
            for item in path.iterdir():
                if item.is_dir(): 
                    shutil.rmtree(item)
                elif item.name != ".gitkeep": 
                    item.unlink()       
        elif not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            (path / ".gitkeep").touch()

def clean_run_cache():
    """Pulisce la cache, i db e i vecchi test prima di OGNI run."""
    files_to_remove = ["session.sqlite", ".mutmut-cache", ".coverage"]
    dirs_to_remove = [".benchmarks", ".pytest_cache", "pynguin-report"]
    
    # Rimuove i file di sessione/cache
    for file in files_to_remove:
        path = Path(file)
        if path.exists(): path.unlink()

    # Rimuove le cartelle di cache
    for d in dirs_to_remove:
        path = Path(d)
        if path.exists() and path.is_dir(): shutil.rmtree(path)

    # Svuota la cartella tests per far rigenerare tutto a Pynguin (mantiene solo .gitkeep)
    tests_path = Path("tests")
    if tests_path.exists() and tests_path.is_dir():
        for item in tests_path.iterdir():
            if item.is_dir(): shutil.rmtree(item)
            elif item.name not in [".gitkeep"]: item.unlink()
    elif not tests_path.exists():
        tests_path.mkdir(exist_ok=True)
        (tests_path / ".gitkeep").touch()