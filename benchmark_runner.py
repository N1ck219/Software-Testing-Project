import subprocess
import time
import json
import os
import shutil
import re
from pathlib import Path

NUM_RUNS = 2
RESULTS_FILE = "results/benchmark_data.json"

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

    # Svuota la cartella tests per far rigenerare tutto a Pynguin (mantiene .gitkeep)
    tests_path = Path("tests")
    if tests_path.exists() and tests_path.is_dir():
        for item in tests_path.iterdir():
            if item.is_dir(): shutil.rmtree(item)
            elif item.name != ".gitkeep": item.unlink()
    elif not tests_path.exists():
        tests_path.mkdir(exist_ok=True)
        (tests_path / ".gitkeep").touch()

def run_pynguin():
    """Esegue Pynguin per generare una nuova suite di test."""
    print("   🤖 Generazione test con Pynguin...")
    env = os.environ.copy()
    env["PYNGUIN_DANGER_AWARE"] = "true"
    
    cmd = [
        "pynguin",
        "--project-path", "./benchmark",
        "--module-name", "triangle",
        "--output-path", "./tests",
        "--assertion-generation", "MUTATION_ANALYSIS"
    ]
    
    start_time = time.time()
    subprocess.run(cmd, env=env, capture_output=True, text=True)
    return time.time() - start_time

def run_mutmut(run_id):
    """Esegue Mutmut, estrae il punteggio e genera il report HTML tramite bash."""
    print("   👾 Esecuzione Mutmut...")
    start_time = time.time()
    subprocess.run(["mutmut", "run"], capture_output=True, text=True)
    execution_time = time.time() - start_time
    
    # Estrae i risultati testuali
    result = subprocess.run(["mutmut", "results"], capture_output=True, text=True)
    killed, survived = 0, 0
    match_k = re.search(r"Killed:\s*(\d+)", result.stdout)
    match_s = re.search(r"Survived:\s*(\d+)", result.stdout)
    if match_k: killed = int(match_k.group(1))
    if match_s: survived = int(match_s.group(1))
    
    total = killed + survived
    score = (killed / total * 100) if total > 0 else 0.0

    # Genera report HTML usando il comando Bash richiesto
    bash_cmd = f"mutmut html && rm -rf results/mutmut/run_{run_id}_htmlcov && mv html results/mutmut/run_{run_id}_htmlcov"
    subprocess.run(bash_cmd, shell=True, executable="/bin/bash")
    
    return {
        "tool": "mutmut",
        "time": round(execution_time, 2),
        "killed": killed,
        "survived": survived,
        "total": total,
        "mutation_score": round(score, 2)
    }

def run_cosmic_ray(run_id):
    """Esegue Cosmic Ray, estrae il punteggio e genera il report HTML tramite bash."""
    print("   🚀 Esecuzione Cosmic Ray...")
    subprocess.run(["cosmic-ray", "init", "cosmic-ray.toml", "session.sqlite"], capture_output=True)
    
    start_time = time.time()
    subprocess.run(["cosmic-ray", "exec", "cosmic-ray.toml", "session.sqlite"], capture_output=True)
    execution_time = time.time() - start_time
    
    # Estrae risultati
    result = subprocess.run(["cr-report", "session.sqlite"], capture_output=True, text=True)
    total_jobs, survival_rate = 0, 0.0
    match_t = re.search(r"Total jobs:\s*(\d+)", result.stdout)
    match_sr = re.search(r"Survival rate:\s*([\d\.]+)%", result.stdout)
    if match_t: total_jobs = int(match_t.group(1))
    if match_sr: survival_rate = float(match_sr.group(1))
    
    score = 100.0 - survival_rate if total_jobs > 0 else 0.0

    # Genera report HTML usando il comando Bash richiesto
    bash_cmd = f"cr-html session.sqlite > results/cosmic_ray/run_{run_id}_report.html"
    subprocess.run(bash_cmd, shell=True, executable="/bin/bash")
    
    return {
        "tool": "cosmic_ray",
        "time": round(execution_time, 2),
        "total_jobs": total_jobs,
        "survival_rate": survival_rate,
        "mutation_score": round(score, 2)
    }

def generate_comparison_report(data):
    """Genera un file HTML per visualizzare i risultati del benchmark."""
    print("\n   📊 Generazione Dashboard Riassuntiva...")
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mutation Testing Benchmark Report</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ font-family: sans-serif; margin: 40px; background: #f4f4f9; }}
            .container {{ max-width: 1000px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; border: 1px solid #ddd; text-align: center; }}
            th {{ background-color: #eee; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Risultati Benchmark: Mutmut vs Cosmic Ray ({NUM_RUNS} Run)</h1>
            <canvas id="scoreChart"></canvas>
            <table>
                <tr>
                    <th>Tool</th>
                    <th>Media Mutation Score</th>
                    <th>Tempo Medio (sec)</th>
                </tr>
                <tr>
                    <td>Mutmut</td>
                    <td>{sum(r['mutmut']['mutation_score'] for r in data)/len(data):.2f}%</td>
                    <td>{sum(r['mutmut']['time'] for r in data)/len(data):.2f}s</td>
                </tr>
                <tr>
                    <td>Cosmic Ray</td>
                    <td>{sum(r['cosmic_ray']['mutation_score'] for r in data)/len(data):.2f}%</td>
                    <td>{sum(r['cosmic_ray']['time'] for r in data)/len(data):.2f}s</td>
                </tr>
            </table>
        </div>
        <script>
            const ctx = document.getElementById('scoreChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {[r['run_id'] for r in data]},
                    datasets: [
                        {{
                            label: 'Mutmut Score %',
                            data: {[r['mutmut']['mutation_score'] for r in data]},
                            borderColor: 'blue',
                            fill: false
                        }},
                        {{
                            label: 'Cosmic Ray Score %',
                            data: {[r['cosmic_ray']['mutation_score'] for r in data]},
                            borderColor: 'red',
                            fill: false
                        }}
                    ]
                }}
            }});
        </script>
    </body>
    </html>
    """
    with open("results/summary_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    # 1. Setup Iniziale
    Path("results").mkdir(exist_ok=True)
    setup_directories()
    
    all_results = []
    
    # 2. Esecuzione Benchmark
    for i in range(NUM_RUNS):
        run_id = i + 1
        print(f"\n--- 🔄 Esecuzione Run {run_id}/{NUM_RUNS} ---")
        
        clean_run_cache()
        pynguin_time = run_pynguin()
        
        mutmut_data = run_mutmut(run_id)
        cr_data = run_cosmic_ray(run_id)
        
        run_record = {
            "run_id": run_id,
            "pynguin_time_sec": round(pynguin_time, 2),
            "mutmut": mutmut_data,
            "cosmic_ray": cr_data
        }
        all_results.append(run_record)
        
        # Salvataggio incrementale JSON
        with open(RESULTS_FILE, "w") as f:
            json.dump(all_results, f, indent=4)
            
        print(f"   ✅ Run {run_id} completata.")
        
    # 3. Report Finale
    generate_comparison_report(all_results)
    print(f"\n🎉 Benchmark completato! Controlla la cartella 'results/' per i report.")

if __name__ == "__main__":
    main()