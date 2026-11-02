"""Summarize actual Locust CSV only; no fallback or synthetic values."""

import csv
import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def rows(path):
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main():
    folder = Path(sys.argv[1])
    stats = rows(folder / "load_stats.csv")
    aggregate = next(row for row in stats if row["Name"] == "Aggregated")
    count = int(aggregate["Request Count"])
    failures = int(aggregate["Failure Count"])
    report = {
        "requests": count,
        "failures": failures,
        "error_rate_percent": 100 * failures / count if count else None,
        "rps": float(aggregate["Requests/s"]),
        "mean_ms": float(aggregate["Average Response Time"]),
        "min_ms": float(aggregate["Min Response Time"]),
        "max_ms": float(aggregate["Max Response Time"]),
        "p95_ms": float(aggregate["95%"]) if count else None,
    }
    resources = rows(folder / "resources.csv")
    report["resources"] = {}
    for service in sorted({row["service"] for row in resources}):
        samples = [r for r in resources if r["service"] == service]
        cpu = [float(r["cpu_percent"]) for r in samples]
        ram = [float(r["ram_bytes"]) / 1024**2 for r in samples]
        report["resources"][service] = {
            "samples": len(samples),
            "cpu_mean_percent": statistics.mean(cpu),
            "cpu_max_percent": max(cpu),
            "ram_mean_mib": statistics.mean(ram),
            "ram_max_mib": max(ram),
        }
    history = [
        row for row in rows(folder / "load_stats_history.csv") if row["Name"] == "Aggregated"
    ]
    history = [
        row
        for row in history
        if row.get("Total Request Count") and int(row["Total Request Count"]) > 0
    ]
    if history:
        times = [float(r["Timestamp"]) - float(history[0]["Timestamp"]) for r in history]
        fig, axes = plt.subplots(2, 1, figsize=(9, 6), layout="constrained")
        axes[0].plot(
            times, [float(r["95%"].replace("N/A", "nan")) for r in history], label="Rolling p95"
        )
        axes[0].set_ylabel("Response time (ms)")
        axes[0].legend()
        axes[1].plot(times, [float(r["Requests/s"]) for r in history], color="#187a69")
        axes[1].set_ylabel("Requests per second")
        axes[1].set_xlabel("Seconds since first non-empty sample")
        for axis in axes:
            axis.grid(alpha=0.25)
        fig.savefig(folder / "latency_rps.png", dpi=180)
        plt.close(fig)
    (folder / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Actual Locust results", "", "| Metric | Value |", "|---|---|"]
    lines.extend(f"| {key} | {value} |" for key, value in report.items() if key != "resources")
    lines += [
        "",
        "Expected enrollment HTTP 409 responses are separate in outcomes.json.",
        "Error Rate counts unexpected failures; p95 is Locust's histogram approximation.",
        "CPU 100% means one logical core. RSS sums can count shared pages more than once.",
        "Missing resource samples mean NOT MEASURED, never zero.",
        "",
        "Resource samples: " + json.dumps(report["resources"], ensure_ascii=False),
    ]
    (folder / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
