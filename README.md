# 🚀 Python Mutation Testing Benchmark

Questo progetto è un framework di benchmarking automatizzato progettato per confrontare l'efficacia delle diverse strategie di generazione di test e delle librerie di **Mutation Testing** in ambiente Python.

Il sistema utilizza **Pynguin** per generare suite di test automatiche e confronta le performance di **Mutmut** e **Cosmic Ray** su una funzione di riferimento (classificazione dei triangoli).

---

## 🛠️ Requisiti e Preparazione dell'Ambiente

### ⚠️ Nota Importante: WSL (Windows Subsystem for Linux)
Per gli utenti Windows, è **fondamentale** utilizzare **WSL** (consigliata Ubuntu 20.04+) per eseguire questo progetto. La libreria `mutmut` presenta limitazioni critiche e instabilità se eseguita direttamente su Windows nativo (problemi di fork e gestione dei file).

### 1. Clonazione e Setup
```bash
# Crea l'ambiente virtuale
python3 -m venv .venv

# Attiva l'ambiente
source .venv/bin/activate

# Installa le dipendenze
pip install -r requirements.txt
```

---

## 🔄 Flusso di Lavoro del Progetto

Il progetto segue una pipeline rigorosa per garantire risultati confrontabili e ripetibili:

1.  **Funzione Target**: Il punto di partenza è `benchmark/triangle.py`, una funzione classica che presenta diverse ramificazioni logiche ideali per il testing.
2.  **Generazione Test (Pynguin)**: Vengono utilizzati diversi algoritmi (come `DYNAMOSA` e `MIO`) per generare suite di test che massimizzino la copertura e la capacità di trovare bug.
3.  **Analisi delle Mutazioni**: Le suite generate vengono sottoposte a stress-test utilizzando due librerie leader:
    *   **Mutmut**: Veloce, basato su modifiche all'AST.
    *   **Cosmic Ray**: Estremamente rigoroso, basato su processi isolati.
4.  **Confronto e Report**: I dati raccolti (Mutation Score, tempo di esecuzione, utilizzo risorse) vengono aggregati in una dashboard interattiva.

---

## 🏃‍♂️ Il Benchmark Runner (`benchmark_runner.py`)

Il cuore dell'automazione è lo script `benchmark_runner.py`. Ecco come è strutturato e cosa esegue passo dopo passo:

### 1. Inizializzazione e Backup
Lo script inizia creando un backup della cartella `benchmark/`. Questo è fondamentale perché le librerie di mutation testing modificano temporaneamente il codice sorgente; il runner garantisce che il codice originale venga sempre ripristinato alla fine o in caso di errore.

### 2. Pulizia della Cache (`clean_run_cache`)
Prima di ogni singola esecuzione (run), il runner pulisce:
*   Database di sessione (`session.sqlite`, `.mutmut-cache`).
*   File di coverage e cache di pytest.
*   La cartella `tests/`, per assicurarsi che i test di un algoritmo non influenzino quelli del successivo.

### 3. Generazione Test con Pynguin
Lancia il comando:
```bash
pynguin --project-path ./benchmark --module-name triangle --output-path ./tests --assertion-generation MUTATION_ANALYSIS --algorithm <ALGORITMO>
```
Questo genera file di test validi all'interno della cartella `tests/`.

### 4. Esecuzione Mutation Testing
Il runner esegue parallelamente (ma in sequenza logica) i due tool:

*   **Mutmut**:
    ```bash
    mutmut run
    mutmut html
    ```
    Monitora anche il consumo di CPU e RAM durante l'esecuzione tramite `psutil`.
*   **Cosmic Ray**:
    ```bash
    cosmic-ray init cosmic-ray.toml session.sqlite
    cosmic-ray exec cosmic-ray.toml session.sqlite
    cr-html session.sqlite > report.html
    ```

### 5. Monitoraggio Risorse
Durante l'esecuzione di ogni tool, un thread separato campiona l'utilizzo di CPU (%) e RAM (MB) del processo padre e di tutti i suoi figli (worker), calcolando medie precise.

---

## 📊 Dashboard dei Risultati

Al termine dell'esecuzione, viene generato un file `results/summary_dashboard.html`. Questa dashboard offre:
*   **Mutation Score Comparison**: Grafico a barre che confronta la capacità di "uccidere" mutanti di ogni suite.
*   **Performance Metrics**: Analisi dei tempi di esecuzione.
*   **Resource Usage**: Grafici sull'impatto computazionale di Mutmut vs Cosmic Ray.
*   **Report Dettagliati**: Link diretti ai report HTML generati da ogni singolo run per ispezionare i mutanti sopravvissuti.

---

## 🚀 Come avviare il Benchmark

Per lanciare l'intera suite di benchmark automatizzata:

```bash
python3 benchmark_runner.py
```

I risultati saranno disponibili in:
*   `results/benchmark_data.json` (dati grezzi)
*   `results/summary_dashboard.html` (visualizzazione grafica)
*   `results/mutmut/` e `results/cosmic_ray/` (report specifici)

---

## 📁 Struttura della Repository

*   `benchmark/`: Contiene il codice sorgente da testare (`triangle.py`).
*   `tests/`: Cartella di destinazione per i test generati da Pynguin.
*   `results/`: Tutti i report e la dashboard finale.
*   `benchmark_runner.py`: Script principale di automazione.
*   `cosmic-ray.toml`: Configurazione specifica per Cosmic Ray.
