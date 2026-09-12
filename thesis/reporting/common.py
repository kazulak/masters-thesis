"""Shared paths, appearance and figure saving. No evidence processing."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402 - select headless backend first


ROOT = Path(__file__).resolve().parents[2]
V4_RESULTS = ROOT / "thesis/implementation/thesis_results/unified_final_v4"
V4_READOUT = V4_RESULTS / "readout"
PATH_RESULTS = ROOT / "thesis/implementation/thesis_results/upmem_cost_guided_path_v1"
FIGURE_OUTPUT = Path(__file__).resolve().parent / "generated/figures"
TABLE_OUTPUT = Path(__file__).resolve().parent / "generated/tables"
PRIMARY_FAMILIES = ("bb84", "bv", "edc", "hs", "qrng", "xor")


def publication_style():
    matplotlib.rcdefaults()
    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "axes.edgecolor": "#777777",
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "svg.fonttype": "path",
        "svg.hashsalt": "thesis-reporting",
    })


def save_figure(fig, name):
    FIGURE_OUTPUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_OUTPUT / f"{name}.svg",
                metadata={"Date": None, "Creator": "thesis reporting"})
    fig.savefig(FIGURE_OUTPUT / f"{name}.png", dpi=300,
                metadata={"Software": "thesis reporting"})
    plt.close(fig)
