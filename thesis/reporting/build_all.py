"""Build the current reporting figures and tables, without running experiments."""
from pathlib import Path
import subprocess
import sys


def main():
    here = Path(__file__).resolve().parent
    scripts = ["figures/fig01_tasklets.py"]
    for script in scripts:
        subprocess.run([sys.executable, str(here / script)], check=True)


if __name__ == "__main__":
    main()
