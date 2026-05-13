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

from scripts.config import NUM_RUNS

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
