"""Build the current reporting figures and tables, without running experiments."""
from pathlib import Path
import subprocess
import sys


def main():
    here = Path(__file__).resolve().parent
    scripts = [
        "figures/fig01_tasklets.py",
        "figures/fig02_dpus.py",
        "figures/fig03_ablation.py",
        "figures/fig04_quantization.py",
        "figures/fig05_final_cpu.py",
        "figures/app01_path_selection.py",
        "figures/app02_supplemental_resources.py",
        "figures/app03_supplemental_quantization.py",
        "tables/table01_workloads.py",
        "tables/table02_correctness.py",
        "tables/table03_resources.py",
        "tables/table04_path_selection.py",
        "tables/table05_cpu_comparison.py",
        "tables/app_table01_mechanisms.py",
        "tables/app_table02_cold_cost.py",
        "tables/app_table03_accounting.py",
        "tables/app_table04_frontiers.py",
        "tables/app_table05_validation.py",
        "tables/app_table06_ablation.py",
    ]
    for script in scripts:
        subprocess.run([sys.executable, str(here / script)], check=True)


if __name__ == "__main__":
    main()
