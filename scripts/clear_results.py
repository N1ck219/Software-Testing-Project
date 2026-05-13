from benchmark_runner import setup_directories, clean_run_cache

def main():
    print("🧹 Inizio la pulizia dei risultati precedenti e della cache...")
    setup_directories()
    clean_run_cache()
    print("✅ Pulizia completata con successo.")

if __name__ == "__main__":
    main()