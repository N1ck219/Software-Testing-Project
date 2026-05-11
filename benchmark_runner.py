import subprocess
import time
import json
import os
import shutil
import re
from pathlib import Path
import psutil
import threading

# Configurazione Globali
NUM_RUNS = 2 if os.environ.get("CI") else 2
# ALGORITHMS = ["DYNAMOSA", "WHOLE_SUITE", "MIO"]
ALGORITHMS = ["DYNAMOSA", "MIO"]
PYNGUIN_SEARCH_BUDGET = 60 # Budget in secondi per la ricerca dei test
RESULTS_FILE = "results/benchmark_data.json"

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

    # Svuota la cartella tests per far rigenerare tutto a Pynguin (mantiene .gitkeep)
    tests_path = Path("tests")
    if tests_path.exists() and tests_path.is_dir():
        for item in tests_path.iterdir():
            if item.is_dir(): shutil.rmtree(item)
            elif item.name != ".gitkeep": item.unlink()
    elif not tests_path.exists():
        tests_path.mkdir(exist_ok=True)
        (tests_path / ".gitkeep").touch()

def run_pynguin(algorithm):
    """Esegue Pynguin per generare una nuova suite di test con l'algoritmo specificato."""
    print(f"   🤖 Generazione test con Pynguin ({algorithm})...")
    env = os.environ.copy()
    env["PYNGUIN_DANGER_AWARE"] = "true"
    
    cmd = [
        get_bin_path("pynguin"),
        "--project-path", "./benchmark",
        "--module-name", "triangle",
        "--output-path", "./tests",
        "--assertion-generation", "MUTATION_ANALYSIS",
        "--algorithm", algorithm,
        "--maximum-search-time", str(PYNGUIN_SEARCH_BUDGET)
    ]
    
    start_time = time.time()
    subprocess.run(cmd, env=env, capture_output=True, text=True)
    return time.time() - start_time

def run_mutmut(run_id, algorithm):
    """Esegue Mutmut, estrae il punteggio e genera il report HTML."""
    print("   👾 Esecuzione Mutmut...")

    is_ci = os.environ.get("CI")
    runner_cmd = "pytest" if is_ci else ".venv/bin/pytest"
    
    setup_cfg_content = f"""[mutmut]
    paths_to_mutate=benchmark/
    runner={runner_cmd}
    """
    with open("setup.cfg", "w") as f:
        f.write(setup_cfg_content)
    
    start_time = time.time()
    
    proc = subprocess.Popen([get_bin_path("mutmut"), "run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stop_event, monitor_thread, cpu_samples, ram_samples = monitor_resources(proc.pid)
    
    stdout, stderr = proc.communicate()
    stop_event.set()
    monitor_thread.join()
    
    execution_time = time.time() - start_time
    avg_cpu, avg_ram = get_averages(cpu_samples, ram_samples)
    
    killed, survived = 0, 0
    matches_k = re.findall(r"🎉\s*(\d+)", stdout)
    matches_s = re.findall(r"🙁\s*(\d+)", stdout)
    if matches_k: killed = int(matches_k[-1])
    if matches_s: survived = int(matches_s[-1])
    
    total = killed + survived
    score = (killed / total * 100) if total > 0 else 0.0

    mutmut_bin = get_bin_path("mutmut")
    report_dir = f"results/mutmut/{algorithm}_run_{run_id}_htmlcov"
    bash_cmd = f"{mutmut_bin} html && rm -rf {report_dir} && mv html {report_dir}"
    subprocess.run(bash_cmd, shell=True, executable="/bin/bash")
    
    print(f"   👾 Mutmut: Uccisi {killed} mutanti, Sopravvissuti {survived} mutanti, Tempo {execution_time:.2f}s")

    return {
        "tool": "mutmut",
        "time": round(execution_time, 2),
        "killed": killed,
        "survived": survived,
        "total": total,
        "mutation_score": round(score, 2),
        "cpu_avg": avg_cpu,
        "ram_avg": avg_ram
    }

def run_cosmic_ray(run_id, algorithm):
    """Esegue Cosmic Ray, estrae il punteggio e genera il report HTML."""
    print("   🚀 Esecuzione Cosmic Ray...")
    subprocess.run([get_bin_path("cosmic-ray"), "init", "cosmic-ray.toml", "session.sqlite"], capture_output=True)
    
    start_time = time.time()
    proc = subprocess.Popen([get_bin_path("cosmic-ray"), "exec", "cosmic-ray.toml", "session.sqlite"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stop_event, monitor_thread, cpu_samples, ram_samples = monitor_resources(proc.pid)
    
    proc.communicate()
    stop_event.set()
    monitor_thread.join()
    
    execution_time = time.time() - start_time
    avg_cpu, avg_ram = get_averages(cpu_samples, ram_samples)
    
    result = subprocess.run([get_bin_path("cr-report"), "session.sqlite"], capture_output=True, text=True)
    total_jobs, completed, survived, survival_rate = 0, 0, 0, 0.0
    
    match_t = re.search(r"total jobs:\s*(\d+)", result.stdout, re.IGNORECASE)
    match_c = re.search(r"complete:\s*(\d+)", result.stdout, re.IGNORECASE)
    match_s = re.search(r"surviving mutants:\s*(\d+)\s*\(([\d\.]+)%\)", result.stdout, re.IGNORECASE)
    
    if match_t: total_jobs = int(match_t.group(1))
    if match_c: completed = int(match_c.group(1))
    if match_s: 
        survived = int(match_s.group(1))
        survival_rate = float(match_s.group(2))
    
    killed = completed - survived
    score = 100.0 - survival_rate if completed > 0 else 0.0

    cr_html_bin = get_bin_path("cr-html")
    report_file = f"results/cosmic_ray/{algorithm}_run_{run_id}_report.html"
    bash_cmd = f"{cr_html_bin} session.sqlite > {report_file}"
    subprocess.run(bash_cmd, shell=True, executable="/bin/bash")
    
    print(f"   🚀 Cosmic Ray: Uccisi {killed} mutanti, Sopravvissuti {survived} mutanti, Tempo {execution_time:.2f}s")
    
    return {
        "tool": "cosmic_ray",
        "time": round(execution_time, 2),
        "total_jobs": total_jobs,
        "completed": completed,
        "survived": survived,
        "survival_rate": survival_rate,
        "mutation_score": round(score, 2),
        "cpu_avg": avg_cpu,
        "ram_avg": avg_ram
    }

def generate_comparison_report(data):
    """Genera la dashboard HTML con confronto tra algoritmi e strumenti."""
    print("\n   📊 Generazione Dashboard Finale...")
    
    # Raggruppamento per Algoritmo
    algs_found = sorted(list(set(r['algorithm'] for r in data)))
    
    # Calcolo Medie per ogni combinazione Algoritmo/Tool
    stats = {}
    for alg in algs_found:
        runs = [r for r in data if r['algorithm'] == alg]
        stats[alg] = {
            "mutmut": {
                "score": sum(r['mutmut']['mutation_score'] for r in runs) / len(runs),
                "time": sum(r['mutmut']['time'] for r in runs) / len(runs),
                "cpu": sum(r['mutmut']['cpu_avg'] for r in runs) / len(runs),
                "ram": sum(r['mutmut']['ram_avg'] for r in runs) / len(runs)
            },
            "cosmic_ray": {
                "score": sum(r['cosmic_ray']['mutation_score'] for r in runs) / len(runs),
                "time": sum(r['cosmic_ray']['time'] for r in runs) / len(runs),
                "cpu": sum(r['cosmic_ray']['cpu_avg'] for r in runs) / len(runs),
                "ram": sum(r['cosmic_ray']['ram_avg'] for r in runs) / len(runs)
            }
        }

    # Preparazione dati per i grafici a confronto (MOSA vs MIO)
    mut_scores = [stats[alg]['mutmut']['score'] for alg in algs_found]
    cr_scores = [stats[alg]['cosmic_ray']['score'] for alg in algs_found]
    
    mut_times = [stats[alg]['mutmut']['time'] for alg in algs_found]
    cr_times = [stats[alg]['cosmic_ray']['time'] for alg in algs_found]

    html_content = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <title>Benchmark Mutation Testing: Strategy Comparison</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; margin: 0; padding: 40px; color: #1c1e21; }}
            .container {{ max-width: 1200px; margin: auto; background: white; padding: 40px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); }}
            .header {{ text-align: center; margin-bottom: 50px; border-bottom: 2px solid #f0f2f5; padding-bottom: 20px; }}
            .chart-section {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 20px; }}
            .chart-container {{ width: calc(50% - 10px); box-sizing: border-box; margin-bottom: 40px; padding: 25px; background: #fff; border-radius: 12px; border: 1px solid #e0e0e0; }}
            h2 {{ color: #2c3e50; margin-bottom: 30px; text-align: center; font-size: 28px; }}
            h3 {{ color: #2c3e50; border-left: 5px solid #3498db; padding-left: 15px; margin-bottom: 25px; }}
            .report-btn {{ display: inline-block; padding: 4px 10px; margin: 2px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; font-size: 12px; transition: background 0.2s; }}
            .report-btn:hover {{ background: #2980b9; }}
            .cr-btn {{ background: #e74c3c; }}
            .cr-btn:hover {{ background: #c0392b; }}
            .summary-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            .summary-table th, .summary-table td {{ padding: 12px; border: 1px solid #eee; text-align: center; }}
            .summary-table th {{ background: #f8f9fa; color: #2c3e50; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Strategie Pynguin a Confronto: {', '.join(algs_found)}</h1>
                <p>Analisi delle performance basata su <strong>{NUM_RUNS} Run</strong> per ogni strategia</p>
            </div>

            <h2>Confronto Efficacia (Mutation Score)</h2>
            <div class="chart-section">
                <div class="chart-container" style="width: 100%;">
                    <canvas id="scoreComparisonChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <div class="chart-container" style="width: 100%;">
                    <h3>⏱️ Tempo di Esecuzione Medio (s)</h3>
                    <canvas id="timeChart"></canvas>
                </div>
            </div>

            <div class="chart-section">
                <div class="chart-container">
                    <h3>💻 Utilizzo CPU Medio (%)</h3>
                    <canvas id="cpuChart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>🧠 Utilizzo RAM Medio (MB)</h3>
                    <canvas id="ramChart"></canvas>
                </div>
            </div>

            <h2>Tabella Riassuntiva Medie</h2>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>Algoritmo</th>
                        <th>Tool</th>
                        <th>Score Medio (%)</th>
                        <th>Tempo Medio (s)</th>
                        <th>CPU (%)</th>
                        <th>RAM (MB)</th>
                        <th>Dettagli Mutanti (Sopravvissuti)</th>
                    </tr>
                </thead>
                <tbody>
                    { "".join([f'''
                    <tr>
                        <td rowspan="2"><strong>{alg}</strong></td>
                        <td>Mutmut</td>
                        <td>{stats[alg]['mutmut']['score']:.1f}%</td>
                        <td>{stats[alg]['mutmut']['time']:.2f}s</td>
                        <td>{stats[alg]['mutmut']['cpu']:.1f}%</td>
                        <td>{stats[alg]['mutmut']['ram']:.1f} MB</td>
                        <td>
                            {''.join([f'<a href="mutmut/{alg}_run_{r["run_id"]}_htmlcov/index.html" class="report-btn">Run {r["run_id"]}</a>' for r in [x for x in data if x['algorithm'] == alg]])}
                        </td>
                    </tr>
                    <tr>
                        <td>Cosmic Ray</td>
                        <td>{stats[alg]['cosmic_ray']['score']:.1f}%</td>
                        <td>{stats[alg]['cosmic_ray']['time']:.2f}s</td>
                        <td>{stats[alg]['cosmic_ray']['cpu']:.1f}%</td>
                        <td>{stats[alg]['cosmic_ray']['ram']:.1f} MB</td>
                        <td>
                            {''.join([f'<a href="cosmic_ray/{alg}_run_{r["run_id"]}_report.html" class="report-btn cr-btn">Run {r["run_id"]}</a>' for r in [x for x in data if x['algorithm'] == alg]])}
                        </td>
                    </tr>
                    ''' for alg in algs_found]) }
                </tbody>
            </table>
        </div>

        <script>
            const algLabels = {algs_found};
            
            const chartOptions = {{
                responsive: true,
                scales: {{
                    y: {{ beginAtZero: true, grid: {{ color: '#f0f2f5' }} }},
                    x: {{ grid: {{ display: false }} }}
                }},
                plugins: {{
                    legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 20 }} }}
                }}
            }};

            // Score Comparison
            new Chart(document.getElementById('scoreComparisonChart'), {{
                type: 'bar',
                data: {{
                    labels: algLabels,
                    datasets: [
                        {{
                            label: 'Mutmut Killed %',
                            data: {mut_scores},
                            backgroundColor: '#3498db',
                            borderRadius: 6
                        }},
                        {{
                            label: 'Cosmic Ray Killed %',
                            data: {cr_scores},
                            backgroundColor: '#e74c3c',
                            borderRadius: 6
                        }}
                    ]
                }},
                options: {{
                    ...chartOptions,
                    scales: {{ y: {{ max: 100, title: {{ display: true, text: 'Mutation Score (%)' }} }} }}
                }}
            }});

            // Execution Time
            new Chart(document.getElementById('timeChart'), {{
                type: 'bar',
                data: {{
                    labels: algLabels,
                    datasets: [
                        {{
                            label: 'Mutmut Time (s)',
                            data: {mut_times},
                            backgroundColor: '#3498db88',
                            borderColor: '#3498db',
                            borderWidth: 1
                        }},
                        {{
                            label: 'Cosmic Ray Time (s)',
                            data: {cr_times},
                            backgroundColor: '#e74c3c88',
                            borderColor: '#e74c3c',
                            borderWidth: 1
                        }}
                    ]
                }},
                options: chartOptions
            }});

            // CPU Chart
            new Chart(document.getElementById('cpuChart'), {{
                type: 'bar',
                data: {{
                    labels: algLabels,
                    datasets: [
                        {{
                            label: 'Mutmut CPU %',
                            data: {[stats[alg]['mutmut']['cpu'] for alg in algs_found]},
                            backgroundColor: '#3498db',
                            borderRadius: 6
                        }},
                        {{
                            label: 'Cosmic Ray CPU %',
                            data: {[stats[alg]['cosmic_ray']['cpu'] for alg in algs_found]},
                            backgroundColor: '#e74c3c',
                            borderRadius: 6
                        }}
                    ]
                }},
                options: chartOptions
            }});

            // RAM Chart
            new Chart(document.getElementById('ramChart'), {{
                type: 'bar',
                data: {{
                    labels: algLabels,
                    datasets: [
                        {{
                            label: 'Mutmut RAM (MB)',
                            data: {[stats[alg]['mutmut']['ram'] for alg in algs_found]},
                            backgroundColor: '#3498db',
                            borderRadius: 6
                        }},
                        {{
                            label: 'Cosmic Ray RAM (MB)',
                            data: {[stats[alg]['cosmic_ray']['ram'] for alg in algs_found]},
                            backgroundColor: '#e74c3c',
                            borderRadius: 6
                        }}
                    ]
                }},
                options: chartOptions
            }});
        </script>
    </body>
    </html>
    """
    with open("results/summary_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✨ Dashboard generata: results/summary_dashboard.html")

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
            print(f"\n🚀 === Test Strategia Pynguin: {alg} ===")
            
            for i in range(NUM_RUNS):
                run_id = i + 1
                print(f"\n--- 🔄 Esecuzione {alg} | Run {run_id}/{NUM_RUNS} ---")
                
                clean_run_cache()
                pynguin_time = run_pynguin(alg)
                
                mutmut_data = run_mutmut(run_id, alg)
                cr_data = run_cosmic_ray(run_id, alg)
                
                run_record = {
                    "algorithm": alg,
                    "run_id": run_id,
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
