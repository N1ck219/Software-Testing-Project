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

# Configurazione Globali
NUM_RUNS = 2 if os.environ.get("CI") else 1

# ALGORITHMS = ["DYNAMOSA", "WHOLE_SUITE", "MIO"]
# ALGORITHMS = ["DYNAMOSA", "MIO", "GEMINI"]
# ALGORITHMS = ["DYNAMOSA", "MIO"]
# ALGORITHMS = ["DYNAMOSA", "GEMINI"]
ALGORITHMS = ["DYNAMOSA"]
# ALGORITHMS = ["GEMINI"]
# Configurazione Target (il modulo in benchmark/ da testare)
# TARGET_MODULE = "timer"
# TARGET_MODULE = "triangle"
TARGET_MODULE = "validation"

PYNGUIN_SEARCH_BUDGET = 60 # Budget in secondi per la ricerca dei test
RANDOM_SEED = 42 # Seed per la riproducibilità

RESULTS_FILE = "results/benchmark_data.json"