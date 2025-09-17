from __future__ import annotations
from io import BytesIO
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")  # без GUI
import matplotlib.pyplot as plt


def bar_chart_png(
    title: str,
    x_labels: List[str],
    values: List[float],
    ylabel: str,
) -> BytesIO:
    """Строит простой столбчатый график и возвращает PNG в памяти."""
    fig, ax = plt.subplots(figsize=(7, 4))  # один график, без стилей
    ax.bar(x_labels, values)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5)
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=140)
    plt.close(fig)
    buf.seek(0)
    return buf
