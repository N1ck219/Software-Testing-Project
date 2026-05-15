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
        print(f"   ✅ File {cache_file_path} già presente, riutilizzo quello salvato.")
        shutil.copy(cache_file_path, test_file_path)
        sanitize_gemini_tests(test_file_path)
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

REGOLE CRITICHE (UNIVERSALI):
1. **FEDELTÀ ASSOLUTA AL CODICE**: Non testare la "logica ideale" o come "dovrebbe essere" una funzione secondo la conoscenza comune. Analizza il codice fornito riga per riga: se il codice accetta un input tecnicamente errato senza lanciare eccezioni, il tuo test deve riflettere questo comportamento.
2. **STABILITÀ DEI TIPI**: Usa SOLO input del tipo previsto (es. stringhe per funzioni che manipolano stringhe). NON testare `None`, `True/False`, numeri o liste a meno che il codice non implementi esplicitamente controlli di tipo (`isinstance`). Crash non gestiti (es. AttributeError su None) fanno fallire il benchmark.
3. **GESTIONE ECCEZIONI**: Usa `pytest.raises` SOLO se vedi esplicitamente l'istruzione `raise` nel codice sorgente fornito. Non inventare validazioni che il codice non implementa.
4. **PUNTEGGIO vs STABILITÀ**: È meglio avere meno test che avere un solo test che fallisce sulla baseline. Se c'è la minima ambiguità sul risultato, NON includerlo.
5. **IMPORTAZIONE E FORMATO**: Usa `from {module_name} import *` e genera SOLO codice Python puro pronto per pytest. Niente markdown, niente spiegazioni.

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
    
    # Sanitizzazione automatica finale (sempre eseguita)
    sanitize_gemini_tests(test_file_path)
    return time.time() - start_time


def sanitize_gemini_tests(test_file_path):
    """Esegue pytest e commenta i test che falliscono per garantire una baseline 100% passante."""
    print(f"   🧹 Sanitizzazione test Gemini ({test_file_path})...")
    pwd = os.path.abspath(os.getcwd())
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{pwd}/libs:{pwd}/benchmark:{pwd}:{env.get('PYTHONPATH', '')}"

    max_iterations = 5 # Evitiamo loop infiniti
    for i in range(max_iterations):
        # Eseguiamo pytest e catturiamo i fallimenti
        result = subprocess.run(
            [".venv/bin/pytest", "--tb=short", str(test_file_path)],
            capture_output=True, text=True, env=env
        )
        
        if result.returncode == 0:
            print("   ✅ Tutti i test Gemini passano!")
            return True

        # Troviamo i nomi dei test falliti (supportando classi e parametrizzazione)
        failed_tests = re.findall(r"FAILED\s+tests/test_gemini\.py::(?:.*::)?(\w+)", result.stdout)
        
        if not failed_tests:
            print("   ⚠️ Impossibile identificare i test falliti singolarmente. Errore di collezione o sintassi.")
            print(f"DEBUG STDOUT:\n{result.stdout[-1000:]}")
            print(f"DEBUG STDERR:\n{result.stderr[-1000:]}")
            break

        print(f"   🚫 Rimozione di {len(set(failed_tests))} test falliti...")
        
        content = test_file_path.read_text()
        if "import pytest" not in content:
            content = "import pytest\n" + content
            
        for base_name in set(failed_tests):
            # Commentiamo la funzione del test mantenendo l'indentazione
            content = re.sub(rf"(\s+)(def\s+{base_name}\()", r"\1@pytest.mark.skip(reason='Auto-sanitized')\n\1\2", content)
        
        test_file_path.write_text(content)
    
    return False


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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
        pynguin_time = time.time() - start_time
        
        # Sanitizzazione dei test generati (correzione import re._parser per Python 3.10+)
        test_file = f"tests/test_{TARGET_MODULE}.py"
        if os.path.exists(test_file):
            subprocess.run(f"sed -i 's/import re._parser/import re/g' {test_file}", shell=True)
            subprocess.run(f"sed -i 's/re._parser/re/g' {test_file}", shell=True)
            
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Errore durante l'esecuzione di Pynguin (Exit Code: {e.returncode}):")
        print(f"--- STDOUT ---\n{e.stdout}\n--- STDERR ---\n{e.stderr}")
        return 0
    return pynguin_time

def run_mutmut(run_id, algorithm):
    """Esegue Mutmut, estrae il punteggio e genera il report HTML."""
    print("   👾 Esecuzione Mutmut...")

    is_ci = os.environ.get("CI")
    runner_cmd = "pytest" if is_ci else ".venv/bin/pytest"
    # Creiamo un file setup.cfg temporaneo per mutmut con percorsi ASSOLUTI
    pwd = os.path.abspath(os.getcwd())
    libs_path = os.path.join(pwd, "libs")
    benchmark_path = os.path.join(pwd, "benchmark")
    
    # Determiniamo il file di test corretto in base alla strategia
    if algorithm == "GEMINI":
        test_file = f"{pwd}/tests/test_gemini.py"
    else:
        test_file = f"{pwd}/tests/test_{TARGET_MODULE}.py"

    setup_cfg = f"""[mutmut]
paths_to_mutate=benchmark/{TARGET_MODULE}.py
backup=False
runner=sh -c "PYTHONPATH={libs_path}:{benchmark_path}:{pwd} .venv/bin/pytest {test_file}"
tests_dir=tests/
"""
    with open("setup.cfg", "w") as f:
        f.write(setup_cfg)
    
    # Pulizia forzata della cache di mutmut e python
    if os.path.exists(".mutmut-cache"):
        os.remove(".mutmut-cache")
    subprocess.run("find . -name '__pycache__' -type d -exec rm -rf {} +", shell=True)
    subprocess.run("find . -name '.pytest_cache' -type d -exec rm -rf {} +", shell=True)
    
    start_time = time.time()
    
    env = os.environ.copy()
    pwd = os.path.abspath(os.getcwd())
    env["PYTHONPATH"] = f"{pwd}/libs:{pwd}/benchmark:{pwd}:{env.get('PYTHONPATH', '')}"
    
    # Eseguiamo mutmut catturando solo lo stdout (per il riassunto)
    # e buttando via lo stderr (per nascondere barre di progresso e icone rotanti)
    proc = subprocess.Popen(
        [get_bin_path("mutmut"), "run"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.DEVNULL, 
        text=True,
        env=env
    )
    stop_event, monitor_thread, cpu_samples, ram_samples = monitor_resources(proc.pid)
    
    stdout, _ = proc.communicate()
    
    stop_event.set()
    monitor_thread.join()
    
    if proc.returncode != 0 and proc.returncode not in [1, 2]:
        print(f"   ❌ Errore durante l'esecuzione di Mutmut (Exit Code: {proc.returncode}):")
        if stdout:
            # Puliamo lo stdout dalle icone rotanti e messaggi di "running" ripetuti
            clean_stdout = "\n".join([line for line in stdout.splitlines() if "Running..." not in line])
            print(f"--- STDOUT ---\n{clean_stdout}")
    
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

    if killed + survived == 0:
        print("   ⚠️ Mutmut non ha trovato mutanti. Ecco l'output per il debug:")
        if stdout: print(f"--- STDOUT ---\n{stdout}")

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