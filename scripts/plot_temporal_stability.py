"""Draw the monthly repeat-purchase result as an SVG, using only the standard library.

Reads artifacts/temporal-stability/results.json and writes docs/figures/temporal-stability.svg.
Three lines per cutoff: model PR-AUC, the prevalence a no-skill model would score, and the
outcome-permutation control (prevalence + permuted gain).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "artifacts" / "temporal-stability" / "results.json"
OUT = ROOT / "docs" / "figures" / "temporal-stability.svg"

W, H = 760, 380
LEFT, RIGHT, TOP, BOTTOM = 56, 36, 40, 64
Y_MAX = 0.7


def _x(i: int, n: int) -> float:
    return LEFT + i * (W - LEFT - RIGHT) / (n - 1)


def _y(v: float) -> float:
    return TOP + (1 - v / Y_MAX) * (H - TOP - BOTTOM)


def _line(values: list[float], color: str, dash: str = "") -> str:
    pts = " ".join(f"{_x(i, len(values)):.1f},{_y(v):.1f}" for i, v in enumerate(values))
    style = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{style}/>'


def main() -> None:
    monthly = json.loads(SRC.read_text())["monthly"]
    cutoffs = [m["cutoff"][:7] for m in monthly]
    pr_auc = [m["pr_auc"] for m in monthly]
    prevalence = [m["pr_auc"] - m["pr_auc_gain"] for m in monthly]
    permuted = [p + m["permutation_pr_auc_gain"] for p, m in zip(prevalence, monthly)]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'font-family="Helvetica, Arial, sans-serif" font-size="12">',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        f'<text x="{LEFT}" y="22" font-size="14" font-weight="bold">Repeat purchase next month, '
        'Online Retail II (exploratory)</text>',
    ]
    for v in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        y = _y(v)
        parts.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{W - RIGHT}" y2="{y:.1f}" stroke="#e5e5e5"/>')
        parts.append(f'<text x="{LEFT - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#666">{v:.1f}</text>')
    for i, c in enumerate(cutoffs):
        if i % 2 == 0:
            parts.append(f'<text x="{_x(i, len(cutoffs)):.1f}" y="{H - BOTTOM + 18}" '
                         f'text-anchor="middle" fill="#666">{c}</text>')
    parts += [
        _line(pr_auc, "#1f5fa8"),
        _line(prevalence, "#888888", "5 4"),
        _line(permuted, "#c0392b", "2 3"),
    ]
    legend = [("#1f5fa8", "", "model PR-AUC"), ("#888888", "5 4", "prevalence (no skill)"),
              ("#c0392b", "2 3", "labels shuffled (control)")]
    for k, (color, dash, label) in enumerate(legend):
        x = LEFT + k * 220
        y = H - 18
        style = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{x}" y1="{y - 4}" x2="{x + 28}" y2="{y - 4}" stroke="{color}" '
                     f'stroke-width="2"{style}/>')
        parts.append(f'<text x="{x + 34}" y="{y}">{label}</text>')
    parts.append("</svg>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(cutoffs)} cutoffs)")


if __name__ == "__main__":
    main()
