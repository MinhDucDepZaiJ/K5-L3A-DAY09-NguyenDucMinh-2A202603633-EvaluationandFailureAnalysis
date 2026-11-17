"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations
import math
import argparse
import json
from pathlib import Path
from collections import Counter
from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:

    problems = []

    for label, report in (("PR", pr), ("baseline", base)):
        manifest = report.get("manifest", {})
        rows = report.get("rows", [])
        metrics = report.get("metrics", {})
        seeds = manifest.get("seeds", [])
        items = manifest.get("items", 0)

        if not isinstance(rows, list) or not isinstance(metrics, dict):
            problems.append(f"{label}: invalid report structure")
            continue

        if not isinstance(items, int) or items <= 0:
            problems.append(f"{label}: invalid item count")
            continue

        if not isinstance(seeds, list) or not seeds:
            problems.append(f"{label}: missing seeds")
            continue

        if len(set(seeds)) != len(seeds):
            problems.append(f"{label}: duplicate manifest seeds")

        if len(rows) != items * len(seeds):
            problems.append(f"{label}: incorrect row count")

        keys = [(r.get("item_id"), r.get("seed")) for r in rows]
        if len(keys) != len(set(keys)):
            problems.append(f"{label}: duplicate item/seed pairs")

        item_ids = {r.get("item_id") for r in rows}
        if None in item_ids or len(item_ids) != items:
            problems.append(f"{label}: item count mismatch")

        if any(r.get("seed") not in seeds for r in rows):
            problems.append(f"{label}: unexpected seed")

        expected = {(item, seed) for item in item_ids for seed in seeds}
        if set(keys) != expected:
            problems.append(f"{label}: incomplete item/seed matrix")

        if report.get("evaluator_failures"):
            problems.append(f"{label}: evaluator failures")

        for mid, value in metrics.items():
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problems.append(f"{label}: invalid metric {mid}")
            elif not math.isfinite(value):
                problems.append(f"{label}: non-finite metric {mid}")

        for m in spec.get("metrics", []):
            mid = m["id"]
            if mid not in metrics or metrics[mid] is None:
                problems.append(f"{label}: missing metric {mid}")

            # Derived and system metrics are not row-level graders.
            if mid.startswith(("pass_hat_", "pass_at_")):
                continue
            if mid in ("cost_per_success", "pass_5"):
                continue

            present = [mid in r for r in rows]

            if any(present):
                if not all(present):
                    problems.append(f"{label}: missing row metric {mid}")
                elif any(r[mid] is None for r in rows):
                    problems.append(f"{label}: null grader {mid}")
            elif mid != "reply_ledger_consistent":
                problems.append(f"{label}: absent row grader {mid}")

        for r in rows:
            if not isinstance(r.get("cost"), (int, float)):
                problems.append(f"{label}: invalid cost")
                break
            if not math.isfinite(r["cost"]) or r["cost"] < 0:
                problems.append(f"{label}: invalid cost")
                break

    pr_keys = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])}
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}

    if pr_keys != base_keys:
        problems.append("PR/baseline item-seed mismatch")

    def tags(report):
        result = {}
        for row in report.get("rows", []):
            key = (row.get("item_id"), row.get("seed"))
            result[key] = frozenset(row.get("slices") or [])
        return result

    if tags(pr) != tags(base):
        problems.append("PR/baseline slice tags mismatch")

    if base_spec is not None:
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            def compare_thresholds(new, old, identifier):
                new_th = new.get("threshold", {})
                old_th = old.get("threshold", {})

                for key in ("min", "max", "max_increase"):
                    if key not in old_th:
                        continue
                    if key not in new_th:
                        problems.append(f"{identifier}: removed {key}")
                    elif key == "min" and new_th[key] < old_th[key]:
                        problems.append(f"{identifier}: loosened min")
                    elif key != "min" and new_th[key] > old_th[key]:
                        problems.append(f"{identifier}: loosened {key}")

                if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
                    problems.append(f"{identifier}: removed significance check")

                if old.get("blocking") and not new.get("blocking"):
                    problems.append(f"{identifier}: removed blocking")

            old_metrics = {m["id"]: m for m in base_spec.get("metrics", [])}
            new_metrics = {m["id"]: m for m in spec.get("metrics", [])}

            for mid, old in old_metrics.items():
                if mid not in new_metrics:
                    problems.append(f"ratchet: removed metric {mid}")
                else:
                    compare_thresholds(new_metrics[mid], old, f"metric:{mid}")

            old_slices = {
                (s["name"], s["metric"]): s
                for s in base_spec.get("slices", [])
            }
            new_slices = {
                (s["name"], s["metric"]): s
                for s in spec.get("slices", [])
            }

            for key, old in old_slices.items():
                if key not in new_slices:
                    problems.append(f"ratchet: removed slice {key}")
                    continue

                new = new_slices[key]
                for field in ("min", "max"):
                    if field in old:
                        if field not in new:
                            problems.append(f"slice:{key}: removed {field}")
                        elif field == "min" and new[field] < old[field]:
                            problems.append(f"slice:{key}: loosened min")
                        elif field == "max" and new[field] > old[field]:
                            problems.append(f"slice:{key}: loosened max")

                if old.get("blocking") and not new.get("blocking"):
                    problems.append(f"slice:{key}: removed blocking")
                if old.get("no_significant_drop") and not new.get("no_significant_drop"):
                    problems.append(f"slice:{key}: removed significance check")

    return problems



def slice_check(
    pr: dict,
    base: dict,
    spec: dict,
) -> tuple[list[str], list[str]]:
    """Evaluate per-slice floors and paired regression confidence intervals."""
    blocked = []
    lines = []
    bs = spec.get("bootstrap", {})

    for cfg in spec.get("slices", []):
        name = cfg["name"]
        metric = cfg["metric"]
        identifier = f"slice:{name}/{metric}"

        pr_values = per_item(pr, metric, slice_name=name)
        base_values = per_item(base, metric, slice_name=name)

        if not pr_values:
            lines.append(f"  {identifier}: MISSING (empty slice)")
            if cfg.get("blocking", False):
                blocked.append(identifier)
            continue

        value = sum(pr_values.values()) / len(pr_values)
        failed = False
        notes = []

        if "min" in cfg and value < cfg["min"]:
            failed = True
            notes.append(f"below min {cfg['min']:.3f}")

        if cfg.get("no_significant_drop", False):
            if set(pr_values) != set(base_values):
                failed = True
                notes.append("item mismatch")
            else:
                keys = sorted(pr_values)

                delta, lo, hi = stats.paired_bootstrap(
                    [pr_values[k] for k in keys],
                    [base_values[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )

                notes.append(
                    f"delta {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                )

                if hi < 0:
                    failed = True

        if failed and cfg.get("blocking", False):
            blocked.append(identifier)

        verdict = (
            "BLOCK" if failed and cfg.get("blocking", False)
            else "warn" if failed
            else "ok"
        )

        lines.append(
            f"  {identifier:<35} "
            f"value={value:.4f} n={len(pr_values)} "
            f"{'; '.join(notes)} {verdict}"
        )

    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
