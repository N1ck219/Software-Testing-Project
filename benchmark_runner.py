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

from scripts.config import ALGORITHMS, NUM_RUNS, RANDOM_SEED, RESULTS_FILE
from scripts.system_utils import setup_directories, clean_run_cache
from scripts.engine_runners import run_gemini, run_pynguin, run_mutmut, run_cosmic_ray
from scripts.reporting import generate_comparison_report

load_dotenv()

def main():
    # 1. Setup Iniziale
    Path("results").mkdir(exist_ok=True)
    setup_directories()
    
    # Crea un backup di sicurezza del codice originale
    if Path("benchmark_backup").exists():
        shutil.rmtree("benchmark_backup")
    shutil.copytree("benchmark", "benchmark_backup")
    
    all_results = []
    
    try:
        # 2. Esecuzione Benchmark per ogni Algoritmo
        for alg in ALGORITHMS:
            print(f"\n🚀 === Test Strategia: {alg} ===")
            
            for i in range(NUM_RUNS):
                run_id = i + 1
                print(f"\n--- 🔄 Esecuzione {alg} | Run {run_id}/{NUM_RUNS} ---")
                
                clean_run_cache()
                run_seed = RANDOM_SEED + (run_id*26)
                
                if alg == "GEMINI":
                    pynguin_time = run_gemini(run_seed)
                else:
                    pynguin_time = run_pynguin(alg, run_seed, run_id)
                
                mutmut_data = run_mutmut(run_id, alg)
                if mutmut_data["killed"] == 0 and mutmut_data["survived"] == 0:
                    print("   ⚠️ Mutmut ha fallito la baseline o non ha trovato mutanti. Salto Cosmic Ray per questa run.")
                    continue 
                    
                cr_data = run_cosmic_ray(run_id, alg)
                
                run_record = {
                    "algorithm": alg,
                    "run_id": run_id,
                    "seed": run_seed,
                    "pynguin_time_sec": round(pynguin_time, 2),
                    "mutmut": mutmut_data,
                    "cosmic_ray": cr_data
                }
                all_results.append(run_record)
                
                # Salvataggio incrementale JSON
                with open(RESULTS_FILE, "w") as f:
                    json.dump(all_results, f, indent=4)
                    
                print(f"   ✅ Run {run_id} ({alg}) completata.")
            
        # 3. Report Finale
        generate_comparison_report(all_results)
        print(f"\n🎉 Benchmark completato! Controlla la cartella 'results/' per i report.")
    finally:
        # Ripristina sempre il backup originale anche in caso di crash
        print("\n🔄 Ripristino del codice sorgente originale...")
        if Path("benchmark").exists():
            shutil.rmtree("benchmark")
        shutil.copytree("benchmark_backup", "benchmark")
        shutil.rmtree("benchmark_backup")
        print("✅ Codice ripristinato con successo.")

if __name__ == "__main__":
    main()
