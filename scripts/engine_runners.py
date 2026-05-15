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

from scripts.config import PYNGUIN_SEARCH_BUDGET, TARGET_MODULE
from scripts.system_utils import get_bin_path
from scripts.monitor import monitor_resources, get_averages

load_dotenv()

def run_gemini(seed):
    """Genera test tramite Gemini se non esistono già, altrimenti usa i test salvati."""
    print(f"   🤖 Generazione test con Gemini [Seed: {seed}]...")
    test_file_path = Path("tests/test_gemini.py")
    cache_file_path = Path(f"gemini_cache_{TARGET_MODULE}.py")
    if cache_file_path.exists():
        print("   ✅ File test_gemini_cache.py già presente, riutilizzo quello salvato.")
        shutil.copy(cache_file_path, test_file_path)
        return 0.0
    
    start_time = time.time()
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("   ❌ Errore: GEMINI_API_KEY non trovata. Impossibile generare i test.")
        return 0.0
    
    client = genai.Client(api_key=api_key)
    
    source_code_path = Path(f"benchmark/{TARGET_MODULE}.py")
    if not source_code_path.exists():
        print(f"   ❌ Errore: file sorgente {source_code_path} non trovato.")
        return 0.0
        
    source_code = source_code_path.read_text()
    
    module_name = source_code_path.stem
    
    prompt = f"""Sei un esperto QA engineer e specialista in Mutation Testing in Python.
Il tuo compito è analizzare il codice sorgente fornito e generare una test suite pytest estremamente rigorosa. L'obiettivo è massimizzare il Mutation Score (uccidere il maggior numero di mutanti), mantenendo rigorosamente il 100% di successo sul codice originale.

REGOLE CRITICHE (PENA IL FALLIMENTO DELL'INTERO BENCHMARK):
1. **BASELINE PASS RATE 100%**: È FONDAMENTALE che ogni test passi con successo sul codice originale. Se c'è la minima probabilità che un test fallisca per arrotondamenti o comportamenti ambigui, NON includerlo. Tutti gli `assert` devono riflettere la logica esatta del codice fornito, non la logica ideale.
2. **LIMITI SUI FLOAT**: Per evitare errori matematici di macchina (`float` in Python), NON usare numeri con più di 5 cifre decimali e NON usare numeri più grandi di 1e9. Evita somme che possono causare imprecisioni (es. `1e9 + 1`).
3. **BOUNDARY VALUE & EDGE CASES**: Concentrati sui limiti fisici e logici (es. se c'è `x > 0`, testa `-0.001`, `0`, `0.001`). Testa input estremi ma realistici entro i limiti definiti al punto 2.
4. **KILLER DI MUTANTI**: Scrivi asserzioni precise pensate per fallire se un operatore relazionale (`<`, `<=`, `==`) o logico (`and`, `or`) viene alterato. Sfrutta a pieno `@pytest.mark.parametrize` per inserire decine di casistiche.
5. **IMPORTAZIONE CORRETTA**: Il codice sorgente fornito corrisponde al modulo `{module_name}`. Analizza il codice per capire quali classi o funzioni testare e inserisci gli import adeguati all'inizio del file (es. `from {module_name} import ...`).
6. **FORMATO**: Genera SOLO ed ESCLUSIVAMENTE codice Python puro pronto per pytest. Niente markdown, niente spiegazioni, niente testo.

Codice Sorgente ({module_name}.py):
{source_code}
"""
    
    print("   ⏳ Chiamata all'API di Gemini in corso...")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        test_code = response.text
        
        # Pulizia base se Gemini include comunque i backtick
        if test_code.startswith("```python"):
            test_code = test_code[9:]
        if test_code.startswith("```"):
            test_code = test_code[3:]
        if test_code.endswith("```"):
            test_code = test_code[:-3]
            
        test_file_path.write_text(test_code.strip())
        cache_file_path.write_text(test_code.strip())
        print(f"   ✨ Test generati con successo in {test_file_path}")
    except Exception as e:
        print(f"   ❌ Errore durante la chiamata a Gemini: {e}")
        
    return time.time() - start_time


def run_pynguin(algorithm, seed, run_id):
    """Esegue Pynguin per generare una nuova suite di test con l'algoritmo specificato."""
    print(f"   🤖 Generazione test con Pynguin ({algorithm}) [Seed: {seed}]...")
    env = os.environ.copy()
    env["PYNGUIN_DANGER_AWARE"] = "true"
    env["PYTHONPATH"] = f"libs:benchmark:{env.get('PYTHONPATH', '')}"
    
    report_dir = f"results/pynguin/{algorithm}_run_{run_id}"
    
    cmd = [
        get_bin_path("pynguin"),
        "--project-path", "./benchmark",
        "--module-name", TARGET_MODULE,
        "--output-path", "./tests",
        "--assertion-generation", "MUTATION_ANALYSIS",
        "--algorithm", algorithm,
        "--maximum-search-time", str(PYNGUIN_SEARCH_BUDGET),
        "--seed", str(seed),
        "--statistics-backend", "CSV",
        "--report-dir", report_dir
    ]
    
    start_time = time.time()
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ❌ Errore durante l'esecuzione di Pynguin (Exit Code: {result.returncode}):")
        if result.stdout: print(f"--- STDOUT ---\n{result.stdout}")
        if result.stderr: print(f"--- STDERR ---\n{result.stderr}")
    return time.time() - start_time

def run_mutmut(run_id, algorithm):
    """Esegue Mutmut, estrae il punteggio e genera il report HTML."""
    print("   👾 Esecuzione Mutmut...")

    is_ci = os.environ.get("CI")
    runner_cmd = "pytest" if is_ci else ".venv/bin/pytest"
    
    setup_cfg_content = f"""[mutmut]
paths_to_mutate=benchmark/{TARGET_MODULE}.py
runner={runner_cmd}
"""
    with open("setup.cfg", "w") as f:
        f.write(setup_cfg_content)
    
    start_time = time.time()
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"libs:benchmark:{env.get('PYTHONPATH', '')}"
    
    proc = subprocess.Popen([get_bin_path("mutmut"), "run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    stop_event, monitor_thread, cpu_samples, ram_samples = monitor_resources(proc.pid)
    
    stdout, stderr = proc.communicate()
    stop_event.set()
    monitor_thread.join()
    
    if proc.returncode != 0:
        print(f"   ❌ Errore durante l'esecuzione di Mutmut (Exit Code: {proc.returncode}):")
        if stdout: print(f"--- STDOUT ---\n{stdout}")
        if stderr: print(f"--- STDERR ---\n{stderr}")
    
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
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"libs:benchmark:{env.get('PYTHONPATH', '')}"
    
    start_time = time.time()    # per il benchmark misuro anche la fase di init di Cosmic Ray, che è parte integrante del processo di mutazione

    # Crea dinamicamente cosmic-ray.toml per il modulo target
    toml_content = f"""[cosmic-ray]
# Subject Under Test
module-path = "benchmark/{TARGET_MODULE}.py"
test-command = "env PYTHONPATH=libs:benchmark pytest tests/"

# Timeout per evitare loop infiniti causati da mutanti "cattivi"
timeout = 10.0

# Aggiungi questa sezione per dire a Cosmic Ray di eseguire i test localmente
[cosmic-ray.distributor]
name = "local"
"""
    with open("cosmic-ray.toml", "w") as f:
        f.write(toml_content)

    subprocess.run(
        [get_bin_path("cosmic-ray"), "init", "cosmic-ray.toml", "session.sqlite"],
        capture_output=True,
        env=env,
    )

    proc_init = subprocess.Popen(
    [get_bin_path("cosmic-ray"), "init", "cosmic-ray.toml", "session.sqlite"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    proc_init.communicate()

    proc_exec = subprocess.Popen(
        [get_bin_path("cosmic-ray"), "exec", "cosmic-ray.toml", "session.sqlite"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
    )
    stop_event, monitor_thread, cpu_samples, ram_samples = monitor_resources(proc_exec.pid)

    proc_exec.communicate()
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