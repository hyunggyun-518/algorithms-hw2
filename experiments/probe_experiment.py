"""Measure separate-chaining search probes and compare them with theory."""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path

from src.hash_table import HashTable

BUCKET_COUNT = 4093
RANDOM_SEED = 20261120
RESULTS_PATH = Path(__file__).resolve().with_name("results.csv")
SVG_PATH = Path(__file__).resolve().with_name("probe_experiment.svg")

Result = tuple[float, float, int, float, float, float, float]


def _random_url(rng: random.Random, host: str, index: int) -> str:
    token = rng.getrandbits(64)
    return f"https://{host}/{index}-{token:016x}"


def measure(seed: int = RANDOM_SEED) -> list[Result]:
    rng = random.Random(seed)
    results: list[Result] = []

    for quarter_steps in range(1, 17):
        target_alpha = quarter_steps / 4
        item_count = round(target_alpha * BUCKET_COUNT)
        table = HashTable(capacity=BUCKET_COUNT, max_load=None)
        urls: list[str] = []

        for index in range(item_count):
            url = _random_url(rng, "example.com", index)
            table.put(url, url)
            urls.append(url)

        successful_probes = 0
        for url in urls:
            value, comparisons = table.get_with_probes(url)
            if value != url:
                raise RuntimeError(f"inserted URL was not found: {url}")
            successful_probes += comparisons

        unsuccessful_probes = 0
        for index in range(item_count):
            url = _random_url(rng, "missing.example", index)
            value, comparisons = table.get_with_probes(url)
            if value is not None:
                raise RuntimeError(f"failure probe unexpectedly found a URL: {url}")
            unsuccessful_probes += comparisons

        alpha = len(table) / table.capacity
        average_success = successful_probes / item_count
        average_failure = unsuccessful_probes / item_count
        results.append(
            (
                target_alpha,
                alpha,
                item_count,
                average_success,
                1 + alpha / 2,
                average_failure,
                alpha,
            )
        )

    return results


def write_csv(results: list[Result], path: Path = RESULTS_PATH) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            (
                "target_alpha",
                "actual_alpha",
                "item_count",
                "successful_average_probes",
                "successful_theory",
                "unsuccessful_average_probes",
                "unsuccessful_theory",
            )
        )
        for result in results:
            writer.writerow(
                (
                    f"{result[0]:.2f}",
                    f"{result[1]:.6f}",
                    result[2],
                    f"{result[3]:.6f}",
                    f"{result[4]:.6f}",
                    f"{result[5]:.6f}",
                    f"{result[6]:.6f}",
                )
            )


def write_svg(results: list[Result], path: Path = SVG_PATH) -> None:
    width, height = 960, 560
    left, top, right, bottom = 78, 70, 260, 74
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_min, x_max = results[0][0], results[-1][0]
    largest_value = max(
        max(result[3], result[4], result[5], result[6]) for result in results
    )
    y_max = math.ceil(largest_value) + 0.5

    def x_position(alpha: float) -> float:
        return left + (alpha - x_min) / (x_max - x_min) * plot_width

    def y_position(value: float) -> float:
        return top + (y_max - value) / y_max * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,sans-serif;fill:#222}"
        ".grid{stroke:#ddd;stroke-width:1}.axis{stroke:#333;stroke-width:1.5}"
        ".measured{stroke-width:2.5;fill:none}.theory{stroke-width:2;fill:none;"
        "stroke-dasharray:7 5}</style>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="480" y="30" text-anchor="middle" font-size="20">'
        "Separate chaining: measured and theoretical node comparisons</text>",
    ]

    for tick in range(math.floor(y_max) + 1):
        y = y_position(float(tick))
        parts.append(
            f'<line class="grid" x1="{left}" y1="{y:.2f}" '
            f'x2="{left + plot_width}" y2="{y:.2f}"/>'
        )
        parts.append(
            f'<text x="{left - 12}" y="{y + 5:.2f}" text-anchor="end" '
            f'font-size="12">{tick}</text>'
        )

    x_ticks = (0.25, 1.0, 2.0, 3.0, 4.0)
    for tick in x_ticks:
        x = x_position(tick)
        parts.append(
            f'<line class="grid" x1="{x:.2f}" y1="{top}" '
            f'x2="{x:.2f}" y2="{top + plot_height}"/>'
        )
        parts.append(
            f'<text x="{x:.2f}" y="{top + plot_height + 22}" '
            f'text-anchor="middle" font-size="12">{tick:g}</text>'
        )

    parts.extend(
        (
            f'<line class="axis" x1="{left}" y1="{top + plot_height}" '
            f'x2="{left + plot_width}" y2="{top + plot_height}"/>',
            f'<line class="axis" x1="{left}" y1="{top}" '
            f'x2="{left}" y2="{top + plot_height}"/>',
            f'<text x="{left + plot_width / 2:.2f}" y="{height - 20}" '
            'text-anchor="middle" font-size="14">Load factor α</text>',
            f'<text x="20" y="{top + plot_height / 2:.2f}" '
            'text-anchor="middle" font-size="14" '
            f'transform="rotate(-90 20 {top + plot_height / 2:.2f})">'
            "Average nodes compared</text>",
        )
    )

    series = (
        ("Successful measured", 3, "#1769aa", "measured"),
        ("Successful theory: 1 + α/2", 4, "#1769aa", "theory"),
        ("Unsuccessful measured", 5, "#c62828", "measured"),
        ("Unsuccessful theory: α", 6, "#c62828", "theory"),
    )
    legend_x = left + plot_width + 28
    legend_y = top + 24
    for series_index, (label, result_index, color, line_style) in enumerate(series):
        points = " ".join(
            f"{x_position(result[0]):.2f},{y_position(result[result_index]):.2f}"
            for result in results
        )
        parts.append(
            f'<polyline class="{line_style}" stroke="{color}" points="{points}"/>'
        )
        if line_style == "measured":
            for result in results:
                parts.append(
                    f'<circle cx="{x_position(result[0]):.2f}" '
                    f'cy="{y_position(result[result_index]):.2f}" r="2.5" '
                    f'fill="{color}"/>'
                )
        y = legend_y + series_index * 26
        dash = ' stroke-dasharray="7 5"' if line_style == "theory" else ""
        parts.append(
            f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 28}" y2="{y}" '
            f'stroke="{color}" stroke-width="2.5"{dash}/>'
        )
        parts.append(
            f'<text x="{legend_x + 36}" y="{y + 5}" font-size="12">{label}</text>'
        )

    parts.append(
        f'<text x="{legend_x}" y="{legend_y + 4 * 26 + 12}" font-size="11">'
        f"Buckets: {BUCKET_COUNT}; seed: {RANDOM_SEED}</text>"
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def print_table(results: list[Result]) -> None:
    print(
        "target α | actual α | n | success avg | success theory "
        "| failure avg | failure theory"
    )
    print("-" * 91)
    for target, alpha, count, success, success_theory, failure, failure_theory in results:
        print(
            f"{target:8.2f} | {alpha:8.4f} | {count:5d} | "
            f"{success:11.4f} | {success_theory:15.4f} | "
            f"{failure:11.4f} | {failure_theory:14.4f}"
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
