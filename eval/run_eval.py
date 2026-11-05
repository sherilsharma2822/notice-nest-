"""Measure how accurate the extraction is on a hand-labelled "answer key".

    python -m eval.run_eval              # basic regex mode (works offline)
    python -m eval.run_eval --llm        # also test the AI (needs a key in .env)

Setups compared:
  regex            - patterns only (the baseline)
  llm_raw          - what the AI said, before checking
  llm_validated    - the AI's answer after validator.py checked every date and fee
Results are saved to eval/results/latest.json and shown on the /metrics page.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.config import Config
from app.services import ai_extractor, regex_extractor, validator
from app.services.fetcher import parse_notice_file
from app.services.llm_client import llm_enabled
from app.services.matcher import normalize_course

GOLD_DIR = Path(__file__).resolve().parent / "gold"


def load_gold() -> list[dict]:
    items = json.loads((GOLD_DIR / "labels.json").read_text(encoding="utf-8"))
    for item in items:
        raw = (GOLD_DIR / "notices" / item["file"]).read_text(encoding="utf-8")
        _, item["text"] = parse_notice_file(raw)
    return items


def _predicted_dates(data: dict) -> set[str]:
    return {str(d.get("date")) for d in data.get("deadlines", []) if d.get("date")}


def _predicted_fees(data: dict) -> set[float]:
    out = set()
    for f in data.get("fees", []):
        try:
            out.add(float(f.get("amount")))
        except (TypeError, ValueError):
            pass
    return out


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def score(predictions: list[dict], gold: list[dict]) -> dict:
    type_ok = who_ok = 0
    d_tp = d_fp = d_fn = f_tp = f_fp = f_fn = 0
    for pred, item in zip(predictions, gold):
        exp = item["expected"]
        type_ok += pred.get("notice_type") == exp["notice_type"]

        applies = pred.get("applies_to", {})
        got = (bool(applies.get("all")),
               sorted({normalize_course(c) for c in applies.get("courses", [])}),
               sorted(int(s) for s in applies.get("semesters", [])))
        who_ok += got == (exp["all"], sorted(exp["courses"]), sorted(exp["semesters"]))

        pd, gd = _predicted_dates(pred), set(exp["deadlines"])
        d_tp += len(pd & gd); d_fp += len(pd - gd); d_fn += len(gd - pd)
        pf, gf = _predicted_fees(pred), {float(x) for x in exp["fees"]}
        f_tp += len(pf & gf); f_fp += len(pf - gf); f_fn += len(gf - pf)
    n = len(gold)
    return {
        "notices": n,
        "type_accuracy": round(type_ok / n, 3),
        "who_it_applies_to_accuracy": round(who_ok / n, 3),
        "deadlines": _prf(d_tp, d_fp, d_fn),
        "fees": _prf(f_tp, f_fp, f_fn),
    }


def invented_dates(predictions: list[dict], gold: list[dict]) -> int:
    """How many predicted dates are NOT written anywhere in the notice (possible hallucinations)."""
    count = 0
    for pred, item in zip(predictions, gold):
        written = {h.value.isoformat() for h in regex_extractor.find_dates(item["text"])}
        count += len(_predicted_dates(pred) - written)
    return count


def run(use_llm: bool) -> dict:
    gold = load_gold()
    results: dict = {}

    regex_raw = [regex_extractor.extract_all(g["title"], g["text"]) for g in gold]
    regex_checked = [validator.validate(p, g["text"], g["published"]).data for p, g in zip(regex_raw, gold)]
    results["regex"] = {**score(regex_checked, gold), "invented_dates": invented_dates(regex_checked, gold)}

    if use_llm:
        if not llm_enabled():
            print("AI is not set up (check LLM_PROVIDER and the API key in .env). Skipping the AI setups.")
        else:
            raw = []
            for g in gold:
                out = ai_extractor.extract_with_llm(g["title"], g["text"], g["published"])
                raw.append(out or {"notice_type": "other", "applies_to": {}, "deadlines": [], "fees": []})
            checked = [validator.validate(p, g["text"], g["published"]).data for p, g in zip(raw, gold)]
            results["llm_raw"] = {**score(raw, gold), "invented_dates": invented_dates(raw, gold)}
            results["llm_validated"] = {**score(checked, gold), "invented_dates": invented_dates(checked, gold)}

    return {"generated_at": datetime.now().replace(microsecond=0).isoformat(sep=" "),
            "provider": Config.LLM_PROVIDER if use_llm else "none", "setups": results}


def print_table(report: dict) -> None:
    print(f"\nEvaluation on {next(iter(report['setups'].values()))['notices']} hand-labelled notices\n")
    header = f"{'setup':<15}{'type acc':>9}{'who acc':>9}{'date P':>8}{'date R':>8}{'date F1':>9}{'fee R':>7}{'invented':>10}"
    print(header)
    print("-" * len(header))
    for name, r in report["setups"].items():
        print(f"{name:<15}{r['type_accuracy']:>9.2f}{r['who_it_applies_to_accuracy']:>9.2f}"
              f"{r['deadlines']['precision']:>8.2f}{r['deadlines']['recall']:>8.2f}{r['deadlines']['f1']:>9.2f}"
              f"{r['fees']['recall']:>7.2f}{r['invented_dates']:>10d}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="also evaluate the AI extractor")
    args = parser.parse_args()
    report = run(args.llm)
    Config.EVAL_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    Config.EVAL_RESULTS_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_table(report)
    print(f"\nSaved to {Config.EVAL_RESULTS_FILE}")


if __name__ == "__main__":
    main()
