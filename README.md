# Software Testing Project - Triangle Classification

Questo progetto utilizza **Pynguin** per la generazione automatica di test unitari e **Pytest** per la loro esecuzione e l'analisi della copertura del codice.

## 🛠️ Setup del Progetto

1. **Creazione dell'ambiente virtuale:**
   ```bash
   python3 -m venv .venv
   ```

2. **Attivazione dell'ambiente virtuale:**
   ```bash
   source .venv/bin/activate
   ```

3. **Installazione delle dipendenze:**
   ```bash
   pip install -r requirements.txt
   ```

## 🧪 Generazione dei Test con Pynguin

Per generare i test automaticamente, segui questi passaggi:

1. **Configura la variabile d'ambiente di sicurezza:**
   Pynguin richiede questa conferma poiché esegue il codice durante l'analisi.
   ```bash
   export PYNGUIN_DANGER_AWARE=true
   ```

2. **Esegui la generazione:**
   Il comando seguente analizza il modulo `triangle` e salva i test nella cartella `tests/`.
   ```bash
   pynguin --project-path ./benchmark --module-name triangle --output-path ./tests
   ```

## 🚀 Esecuzione dei Test e Coverage

Grazie alla configurazione presente in `pytest.ini` e `.coveragerc`, l'esecuzione dei test e la generazione del report di coverage sono completamente automatiche.

Per eseguire i test e generare i report:
```bash
pytest ./tests
```

### Output dei risultati
Dopo l'esecuzione, troverai tutti i risultati nella cartella `results/pynguin/`:
*   **Report HTML**: `results/pynguin/htmlcov/index.html` (apribile nel browser).
*   **Dati Coverage**: `results/pynguin/.coverage`.
