"""Compare separate chaining and linear probing search costs."""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path

from src.hash_table import HashTable, LinearProbingHashTable

BUCKET_COUNT = 10_000
RANDOM_SEED = 20261120
RESULTS_PATH = Path(__file__).resolve().with_name("results.csv")
SVG_PATH = Path(__file__).resolve().with_name("probe_experiment.svg")


@dataclass(frozen=True)
class Result:
    alpha: float
    item_count: int
    chaining_success: float
    chaining_success_theory: float
    chaining_failure: float
    chaining_failure_theory: float
    linear_success: float
    linear_success_theory: float
    linear_failure: float
    linear_failure_theory: float


def _random_url(rng: random.Random, host: str, index: int) -> str:
    token = rng.getrandbits(64)
    return f"https://{host}/{index}-{token:016x}"


def measure(seed: int = RANDOM_SEED) -> list[Result]:
    rng = random.Random(seed)
    maximum_count = BUCKET_COUNT * 9 // 10
    inserted_keys = [
        _random_url(rng, "example.com", index) for index in range(maximum_count)
    ]
    missing_keys = [
        _random_url(rng, "missing.example", index) for index in range(maximum_count)
    ]
    results: list[Result] = []

    for step in range(1, 10):
        item_count = BUCKET_COUNT * step // 10
        alpha = item_count / BUCKET_COUNT
        keys = inserted_keys[:item_count]
        misses = missing_keys[:item_count]

        chaining = HashTable(capacity=BUCKET_COUNT, max_load=None)
        linear = LinearProbingHashTable(capacity=BUCKET_COUNT, max_load=None)
        for key in keys:
            chaining.put(key, key)
            linear.put(key, key)

        chaining_success = _average_probes(chaining, keys, expected=keys)
        chaining_failure = _average_probes(chaining, misses, expected=None)
        linear_success = _average_probes(linear, keys, expected=keys)
        linear_failure = _average_probes(linear, misses, expected=None)
        results.append(
            Result(
                alpha=alpha,
                item_count=item_count,
                chaining_success=chaining_success,
                chaining_success_theory=1 + alpha / 2,
                chaining_failure=chaining_failure,
                chaining_failure_theory=alpha,
                linear_success=linear_success,
                linear_success_theory=(1 + 1 / (1 - alpha)) / 2,
                linear_failure=linear_failure,
                linear_failure_theory=(1 + 1 / (1 - alpha) ** 2) / 2,
            )
        )
    return results


def _average_probes(
    table: HashTable | LinearProbingHashTable,
    keys: list[str],
    expected: list[str] | None,
) -> float:
    total = 0
    for index, key in enumerate(keys):
        value, probes = table.get_with_probes(key)
        expected_value = None if expected is None else expected[index]
        if value != expected_value:
            raise RuntimeError(f"unexpected lookup result for {key!r}: {value!r}")
        total += probes
    return total / len(keys)


def write_csv(results: list[Result], path: Path = RESULTS_PATH) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            (
                "alpha",
                "item_count",
                "chaining_success_measured",
                "chaining_success_theory",
                "chaining_failure_measured",
                "chaining_failure_theory",
                "linear_probing_success_measured",
                "linear_probing_success_theory",
                "linear_probing_failure_measured",
                "linear_probing_failure_theory",
            )
        )
        for result in results:
            writer.writerow(
                (
                    f"{result.alpha:.2f}",
                    result.item_count,
                    f"{result.chaining_success:.6f}",
                    f"{result.chaining_success_theory:.6f}",
                    f"{result.chaining_failure:.6f}",
                    f"{result.chaining_failure_theory:.6f}",
                    f"{result.linear_success:.6f}",
                    f"{result.linear_success_theory:.6f}",
                    f"{result.linear_failure:.6f}",
                    f"{result.linear_failure_theory:.6f}",
                )
            )


def write_svg(results: list[Result], path: Path = SVG_PATH) -> None:
    width, height = 1120, 620
    panel_width, panel_height = 450, 450
    top = 105
    panels = (
        (
            70,
            "Successful search",
            (
                ("Chaining measured", "chaining_success", "#1769aa", False),
                ("Chaining theory", "chaining_success_theory", "#1769aa", True),
                ("Linear probing measured", "linear_success", "#c62828", False),
                ("Linear probing theory", "linear_success_theory", "#c62828", True),
            ),
        ),
        (
            600,
            "Unsuccessful search",
            (
                ("Chaining measured", "chaining_failure", "#1769aa", False),
                ("Chaining theory", "chaining_failure_theory", "#1769aa", True),
                ("Linear probing measured", "linear_failure", "#c62828", False),
                ("Linear probing theory", "linear_failure_theory", "#c62828", True),
            ),
        ),
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,sans-serif;fill:#222}"
        ".grid{stroke:#ddd;stroke-width:1}.axis{stroke:#333;stroke-width:1.5}"
        ".line{stroke-width:2.5;fill:none}.theory{stroke-dasharray:7 5}</style>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="560" y="34" text-anchor="middle" font-size="21">'
        "Hash-table search cost: measured and theoretical</text>",
    ]

    for panel_x, title, series in panels:
        largest = max(getattr(result, field) for result in results for _, field, _, _ in series)
        tick_interval = 10 if largest > 10 else 1
        y_max = max(
            tick_interval,
            math.ceil(largest * 1.08 / tick_interval) * tick_interval,
        )
        plot_left = panel_x + 48
        plot_top = top
        plot_width = panel_width - 65
        plot_height = panel_height

        def x_position(alpha: float) -> float:
            return plot_left + (alpha - 0.1) / 0.8 * plot_width

        def y_position(value: float) -> float:
            return plot_top + (y_max - value) / y_max * plot_height

        parts.append(
            f'<text x="{panel_x + panel_width / 2}" y="77" text-anchor="middle" '
            f'font-size="17">{title}</text>'
        )
        for tick in range(0, y_max + 1, tick_interval):
            y = y_position(float(tick))
            parts.append(
                f'<line class="grid" x1="{plot_left}" y1="{y:.2f}" '
                f'x2="{plot_left + plot_width}" y2="{y:.2f}"/>'
            )
            parts.append(
                f'<text x="{plot_left - 9}" y="{y + 4:.2f}" text-anchor="end" '
                f'font-size="11">{tick}</text>'
            )
        for step in range(1, 10):
            alpha = step / 10
            x = x_position(alpha)
            parts.append(
                f'<line class="grid" x1="{x:.2f}" y1="{plot_top}" '
                f'x2="{x:.2f}" y2="{plot_top + plot_height}"/>'
            )
            parts.append(
                f'<text x="{x:.2f}" y="{plot_top + plot_height + 20}" '
                f'text-anchor="middle" font-size="10">{alpha:.1f}</text>'
            )
        parts.extend(
            (
                f'<line class="axis" x1="{plot_left}" y1="{plot_top + plot_height}" '
                f'x2="{plot_left + plot_width}" y2="{plot_top + plot_height}"/>',
                f'<line class="axis" x1="{plot_left}" y1="{plot_top}" '
                f'x2="{plot_left}" y2="{plot_top + plot_height}"/>',
                f'<text x="{panel_x + 12}" y="{plot_top + plot_height / 2:.2f}" '
                'text-anchor="middle" font-size="12" '
                f'transform="rotate(-90 {panel_x + 12} '
                f'{plot_top + plot_height / 2:.2f})">Average probes</text>',
                f'<text x="{plot_left + plot_width / 2}" '
                f'y="{plot_top + plot_height + 45}" text-anchor="middle" '
                'font-size="13">Load factor α</text>',
            )
        )

        legend_y = 100
        for index, (label, field, color, dashed) in enumerate(series):
            points = " ".join(
                f"{x_position(result.alpha):.2f},{y_position(getattr(result, field)):.2f}"
                for result in results
            )
            class_name = "line theory" if dashed else "line"
            parts.append(
                f'<polyline class="{class_name}" stroke="{color}" points="{points}"/>'
            )
            if not dashed:
                for result in results:
                    parts.append(
                        f'<circle cx="{x_position(result.alpha):.2f}" '
                        f'cy="{y_position(getattr(result, field)):.2f}" r="2.5" '
                        f'fill="{color}"/>'
                    )
            legend_x = panel_x + 12 + (index % 2) * 225
            row_y = legend_y + (index // 2) * 20
            dash = ' stroke-dasharray="7 5"' if dashed else ""
            parts.append(
                f'<line x1="{legend_x}" y1="{row_y}" x2="{legend_x + 24}" '
                f'y2="{row_y}" stroke="{color}" stroke-width="2.5"{dash}/>'
            )
            parts.append(
                f'<text x="{legend_x + 30}" y="{row_y + 4}" font-size="10">'
                f"{label}</text>"
            )

    parts.extend(
        (
            f'<text x="560" y="{height - 12}" text-anchor="middle" font-size="11">'
            f"Capacity: {BUCKET_COUNT}; inserted and queried keys/order shared; "
            f"seed: {RANDOM_SEED}</text>",
            "</svg>",
        )
    )
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def print_table(results: list[Result]) -> None:
    print(
        "α | n | chain success measured/theory | chain failure measured/theory "
        "| linear success measured/theory | linear failure measured/theory"
    )
    print("-" * 123)
    for result in results:
        print(
            f"{result.alpha:.1f} | {result.item_count:5d} | "
            f"{result.chaining_success:.4f}/{result.chaining_success_theory:.4f} | "
            f"{result.chaining_failure:.4f}/{result.chaining_failure_theory:.4f} | "
            f"{result.linear_success:.4f}/{result.linear_success_theory:.4f} | "
            f"{result.linear_failure:.4f}/{result.linear_failure_theory:.4f}"
        )


def main() -> None:
    results = measure()
    write_csv(results)
    write_svg(results)
    print_table(results)
    print(f"\nCSV: {RESULTS_PATH}")
    print(f"SVG: {SVG_PATH}")


if __name__ == "__main__":
    main()
