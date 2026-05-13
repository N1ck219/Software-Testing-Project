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

def monitor_resources(pid, interval=0.5):
    """Monitora CPU (%) e RAM (MB) di un processo e dei suoi figli in background."""
    cpu_samples = []
    ram_samples = []
    stop_event = threading.Event()
    
    def target():
        try:
            parent = psutil.Process(pid)
            # Warmup
            parent.cpu_percent(interval=None)
        except psutil.NoSuchProcess:
            return

        while not stop_event.is_set():
            try:
                if not parent.is_running():
                    break
                
                procs = [parent] + parent.children(recursive=True)
                total_cpu = 0
                total_ram = 0
                
                for p in procs:
                    try:
                        total_cpu += p.cpu_percent(interval=None)
                        total_ram += p.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                if total_cpu > 0: # Salta i campioni a zero (iniziali)
                    cpu_samples.append(total_cpu)
                ram_samples.append(total_ram / (1024 * 1024))
                
                time.sleep(interval)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

    thread = threading.Thread(target=target)
    thread.start()
    return stop_event, thread, cpu_samples, ram_samples

def get_averages(cpu_samples, ram_samples):
    """Calcola le medie dai campioni raccolti."""
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    avg_ram = sum(ram_samples) / len(ram_samples) if ram_samples else 0.0
    return round(avg_cpu, 2), round(avg_ram, 2)

