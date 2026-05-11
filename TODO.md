1) pynguin ci mette tempistiche diverse a run differenti. Come mai? (da 14s a 2s circa)
2) capire se è interessante capire perchè ad ogni run ci sono risultati diversi (mutants killed/survived) per quanto riguarda sia mutmut che cosmic ray
3) tracciare la coverage di pytest anche nella dashboard
4) Analizzate quali tipi di mutazioni Pynguin non riesce a "uccidere". Questo rivela i limiti dell'algoritmo di generazione automatica.
5) Pynguin permette diverse strategie di generazione (es. RANDOM, MOSA, MIO). Potreste modificare il benchmark_runner.py per testare queste diverse configurazioni e vedere quale produce la suite di test più "letale" per i mutanti.
6) <!-- Oltre al tempo, potreste monitorare:
    - Utilizzo della CPU/RAM: Cosmic Ray è più lento, ma consuma più risorse? -->
    - Parallelizzazione: Cosmic Ray supporta diversi "distributors". Potreste confrontare le performance del distributor local con l'esecuzione parallela per vedere quanto scala bene.