import os
import subprocess
import sys

def setup_environment():
    # Pynguin richiede questa variabile d'ambiente per funzionare
    # Assicurati di eseguire Pynguin solo su codice sicuro!
    os.environ["PYNGUIN_DANGER_AWARE"] = "1"

def run_pynguin():
    print("Iniziando la generazione dei test con Pynguin...")
    # Crea la cartella dei test se non esiste
    os.makedirs("tests", exist_ok=True)
    
    cmd = [
        sys.executable, "-m", "pynguin",
        "--project-path", ".",
        "--output-path", "./tests",
        "--module-name", "example_math"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("[OK] Pynguin ha generato i test con successo in ./tests")
    else:
        print("[ERR] Errore durante l'esecuzione di Pynguin:")
        print(result.stderr)

def setup_mutmut():
    print("\nConfigurando Mutmut...")
    config = """[mutmut]
paths_to_mutate=example_math.py
backup=False
runner=python -m pytest tests/
tests_dir=tests/
"""
    with open("setup.cfg", "w") as f:
        f.write(config)
    print("[OK] File setup.cfg creato per Mutmut.")

def setup_cosmic_ray():
    print("\nConfigurando Cosmic Ray...")
    config = """[cosmic-ray]
module-path = "example_math.py"
timeout = 10.0
excluded-modules = []
test-command = "python -m pytest tests/"

[cosmic-ray.execution-engine]
name = "local"
"""
    with open("cosmic-ray.conf", "w") as f:
        f.write(config)
    print("[OK] File cosmic-ray.conf creato per Cosmic Ray.")

if __name__ == "__main__":
    setup_environment()
    run_pynguin()
    setup_mutmut()
    setup_cosmic_ray()
    
    print("\n" + "="*50)
    print("Setup completato! Ecco come procedere:")
    print("1. Per eseguire Mutmut:    mutmut run")
    print("2. Per vedere i risultati: mutmut results")
    print("3. Per inizializzare Cosmic Ray: cosmic-ray init cosmic-ray.conf session.sqlite")
    print("4. Per eseguire Cosmic Ray:      cosmic-ray exec cosmic-ray.conf session.sqlite")
    print("5. Per vedere i risultati CR:    cr-report session.sqlite")
    print("="*50)
