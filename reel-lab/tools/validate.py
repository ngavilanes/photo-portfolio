#!/usr/bin/env python3
"""
validate.py - score teardown.py's cuts against a hand-labelled ground truth.

    python tools/validate.py references/airports/analysis.json references/airports/ground_truth.json

ground_truth.json:
  {"tolerance_s": 0.1,
   "cuts": [{"time": 3.55, "kind": "hard cut", "note": "..."}],
   "ambiguous": [{"start": 10.2, "end": 11.15, "note": "..."}]}

A detection inside an "ambiguous" range counts neither for nor against.
Exit code 1 if recall is below --min-recall.
"""
import argparse
import json
import sys


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis")
    ap.add_argument("truth")
    ap.add_argument("--min-recall", type=float, default=0.9)
    a = ap.parse_args(argv)
    an = json.load(open(a.analysis))
    gt = json.load(open(a.truth))
    tol = gt.get("tolerance_s", 0.1)
    det = [c["time"] for c in an["cuts"]]
    amb = gt.get("ambiguous", [])
    in_amb = lambda t: any(r["start"] - tol <= t <= r["end"] + tol for r in amb)

    used, rows = set(), []
    for c in gt["cuts"]:
        best = None
        for i, t in enumerate(det):
            if i in used or abs(t - c["time"]) > tol:
                continue
            if best is None or abs(t - c["time"]) < abs(det[best] - c["time"]):
                best = i
        if best is not None:
            used.add(best)
        rows.append((c, None if best is None else det[best]))

    extra = [t for i, t in enumerate(det) if i not in used and not in_amb(t)]
    ignored = [t for i, t in enumerate(det) if i not in used and in_amb(t)]
    hit = sum(1 for _, d in rows if d is not None)
    recall = hit / len(rows) if rows else 1.0
    precision = hit / (hit + len(extra)) if hit + len(extra) else 1.0
    fps = an.get("analysis_fps", 30)

    print(f"ground truth: {len(rows)} cuts, tolerance ±{tol}s\n")
    print(f"{'truth':>7}  {'found':>7}  {'error':>9}  note")
    for c, d in rows:
        err = "MISSED" if d is None else f"{(d - c['time']) * 1000:+.0f}ms/{(d - c['time']) * fps:+.1f}f"
        print(f"{c['time']:7.2f}  {'-' if d is None else f'{d:7.2f}':>7}  {err:>9}  {c.get('kind', '')} {c.get('note', '')}")
    print(f"\nfalse positives: {', '.join(f'{t:.2f}' for t in extra) or 'none'}")
    if ignored:
        print(f"inside ambiguous ranges (not scored): {', '.join(f'{t:.2f}' for t in ignored)}")
    print(f"\nrecall {recall:.0%}  precision {precision:.0%}")
    return 0 if recall >= a.min_recall else 1


if __name__ == "__main__":
    sys.exit(main())
