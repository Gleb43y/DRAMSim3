
#!/usr/bin/env python3
"""Run the same DRAMSim3 trace on HBM2 and GDDR5X."""

import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "build" / "dramsim3main"
TRACE = ROOT / "tests" / "example.trace"
OUT = ROOT / "comparison_results"

CONFIGS = {
    "HBM2": ROOT / "configs" / "HBM2_8Gb_x128.ini",
    "GDDR5X": ROOT / "configs" / "GDDR5X_8Gb_x32.ini",
}
CYCLES = 1_000_000


def numeric_fields(obj, prefix=""):
    result = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = f"{prefix}.{key}" if prefix else key
            result.update(numeric_fields(value, name))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            result.update(numeric_fields(value, f"{prefix}[{i}]"))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        result[prefix] = obj
    return result


def run_model(name, config):
    if not config.is_file():
        print(f"[ERROR] Missing config: {config}")
        return None

    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(BINARY),
        str(config),
        "-c", str(CYCLES),
        "-t", str(TRACE),
        "-o", str(folder),
    ]

    print(f"Running {name}...")
    with (folder / "run.log").open("w") as log:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=3600,
            check=False,
        )

    if result.returncode != 0:
        print(f"[ERROR] {name} failed; inspect {folder / 'run.log'}")
        return None

    # Locate simulator statistics without assuming one fixed filename.
    candidates = list(folder.glob("*.json"))
    if not candidates:
        candidates = list(ROOT.glob("dramsim3.json"))

    stats_file = next(
        (p for p in candidates if "epoch" not in p.name.lower()),
        None,
    )
    if stats_file is None:
        print(f"[WARN] No JSON statistics found for {name}.")
        print(f"Inspect {folder / 'run.log'} and output settings.")
        return {
            "model": name,
            "status": "ran_no_json_found",
        }

    try:
        stats = json.loads(stats_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WARN] Cannot parse {stats_file}: {exc}")
        return None

    row = {"model": name, "status": "ok"}
    row.update(numeric_fields(stats))
    return row


def main():
    if not BINARY.is_file():
        raise SystemExit(
            "Build DRAMSim3 first: cmake -S . -B build && "
            "cmake --build build -j4"
        )
    if not TRACE.is_file():
        raise SystemExit(f"Trace not found: {TRACE}")

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []

    for name, config in CONFIGS.items():
        row = run_model(name, config)
        if row:
            rows.append(row)

    if not rows:
        raise SystemExit("No results produced.")

    columns = list(dict.fromkeys(
        key for row in rows for key in row
    ))
    with (OUT / "comparison.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    (OUT / "comparison.json").write_text(
        json.dumps(rows, indent=2),
        encoding="utf-8",
    )

    print(f"Results saved to: {OUT}")
    print("Review completion counters before comparing performance.")


if __name__ == "__main__":
    main()
