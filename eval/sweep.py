"""Run every attack case against every model, several times, and record the results.

Writes one CSV row per model call, as it goes, so an interrupted run loses nothing.
Re-running skips rows already present in the results file.

    python sweep.py           # the full plan
    python sweep.py smoke     # one model, one run per case, to check the plumbing
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from runner import ATTACKS_PATH, attack_succeeded, build_prompt, load_attacks, student

MODELS = ["local-qwen-3b", "local-qwen-7b", "local-mistral-7b", "cloud-default"]
RUNS = 5
RESULTS_PATH = Path(__file__).parent / "results" / "sweep.csv"
COLUMNS = ["timestamp", "model", "case_id", "use_markers", "run", "verdict", "answer"]

if "smoke" in sys.argv:
    MODELS = MODELS[:1]
    RUNS = 1

attacks = load_attacks(ATTACKS_PATH)


def build_plan():
    """Every call we intend to make, decided before any of them runs."""
    plan = []

    # Every case, markers on.
    for model in MODELS:
        for case in attacks:
            for run in range(1, RUNS + 1):
                plan.append({"model": model, "case": case, "use_markers": True, "run": run})

    # Markers off only changes the prompt for cases that carry untrusted text.
    for model in MODELS:
        for case in attacks:
            if case.get("untrusted_text") is None:
                continue
            for run in range(1, RUNS + 1):
                plan.append({"model": model, "case": case, "use_markers": False, "run": run})

    return plan


def already_done(path):
    """Keys of rows the results file already holds, so a restart skips them."""
    if not path.exists():
        return set()
    with open(path, newline="") as stream:
        return {
            (row["model"], row["case_id"], row["use_markers"], row["run"])
            for row in csv.DictReader(stream)
        }


def key_of(entry):
    return (entry["model"], entry["case"]["id"], str(entry["use_markers"]), str(entry["run"]))


def main():
    plan = build_plan()
    done = already_done(RESULTS_PATH)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    is_new_file = not RESULTS_PATH.exists()
    with open(RESULTS_PATH, "a", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        if is_new_file:
            writer.writeheader()

        for position, entry in enumerate(plan, start=1):
            case = entry["case"]
            label = f"{position}/{len(plan)} {entry['model']} {case['id']} markers={entry['use_markers']} run={entry['run']}"

            if key_of(entry) in done:
                print(f"{label} -> skipped, already recorded")
                continue

            prompt = build_prompt(case, entry["use_markers"])
            try:
                answer = student(prompt, entry["model"])
                verdict = "FAIL" if attack_succeeded(answer, case["fails_if_contains"]) else "PASS"
            except Exception as exc:
                answer = f"{type(exc).__name__}: {exc}"
                verdict = "ERROR"

            writer.writerow({
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model": entry["model"],
                "case_id": case["id"],
                "use_markers": entry["use_markers"],
                "run": entry["run"],
                "verdict": verdict,
                "answer": answer,
            })
            stream.flush()

            print(f"{label} -> {verdict}")

    print(f"\nresults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
