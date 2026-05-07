# Software Testing Project - Triangle Classification

Progetto per l'automazione del testing Python utilizzando **Pynguin** per la generazione dei test e **Mutmut** per la Mutation Analysis. 

---

## 🚀 Setup del Progetto

Segui questi passaggi per preparare l'ambiente di lavoro.

### 1. Creazione e Attivazione dell'Ambiente Virtuale
Crea l'ambiente virtuale per isolare le dipendenze del progetto:
```bash
python3 -m venv .venv
```

Attiva l'ambiente virtuale per isolare le dipendenze del progetto:
```bash
source .venv/bin/activate
```

### 2. Installazione delle Dipendenze
Installa tutti i pacchetti necessari (Pytest, Pynguin, Mutmut, ecc.):
```bash
pip install -r requirements.txt
```

---

## 🧪 Generazione dei Test (Pynguin)

Utilizziamo Pynguin per generare automaticamente una suite di test basata sull'analisi del codice.

### 3. Configurazione Variabile d'Ambiente
Permette a Pynguin di eseguire il codice per generare i test (necessario per motivi di sicurezza):
```bash
export PYNGUIN_DANGER_AWARE=true
```

### 4. Generazione della Suite di Test
Esegue Pynguin sul modulo `triangle` per creare i test nella cartella `tests/`:
```bash
pynguin --project-path ./benchmark --module-name triangle --output-path ./tests --assertion-generation MUTATION_ANALYSIS
```

---

## 📊 Esecuzione Test e Coverage (Pytest)

Una volta generati i test, verifichiamo quanto codice viene effettivamente coperto.

### 5. Esecuzione dei Test e Calcolo Coverage
Avvia la suite di test e genera automaticamente i report di copertura:
```bash
pytest
```
*I risultati (HTML e dati grezzi) verranno salvati nella cartella `results/pynguin/`.*

---

## 👾 Mutation Testing (Mutmut)

Verifichiamo la robustezza dei test introducendo piccoli "errori" (mutanti) nel codice originale.

### 6. Esecuzione della Mutation Analysis
Avvia Mutmut per generare e testare i mutanti:
```bash
mutmut run
```

### 7. Generazione del Report HTML
Converte i risultati della mutation analysis in un formato leggibile nel browser:
```bash
mutmut html && rm -rf results/mutmut/htmlcov && mv html results/mutmut/htmlcov
```

---

## 🔍 Visualizzazione dei Risultati

### 8. Sommario dei Risultati
Visualizza un riepilogo veloce dei mutanti (quanti uccisi, quanti sopravvissuti):
```bash
mutmut results
```

### 9. Analisi di un Singolo Mutante
Mostra esattamente quale modifica è stata apportata a un mutante specifico tramite il suo ID:
```bash
mutmut show <id>
```

---

## 📁 Struttura della Repository
Tutti i file generati durante l'esecuzione sono ignorati da Git per mantenere il progetto pulito:
- `tests/`: Suite di test generata.
- `results/`: Tutti i report (Coverage e Mutation).
- `.mutmut-cache`: Database interno di Mutmut.
- `.pytest_cache/`: Cache di Pytest.