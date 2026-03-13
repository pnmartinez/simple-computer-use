#!/usr/bin/env python3
"""
Compare voice-command performance across three periods, split by the two
main code-change dates:

  ANTES        : up to 2026-02-15  (before OCR improvements)
  POST-OCR     : 2026-02-17 – 2026-02-26  (after spatial-overlap + thresholds)
  POST-ROBUSTEZ: 2026-02-28 – today       (after P1-P5 click robustness)

Usage:
    python analyze_performance_comparison.py                        # default structured_logs/
    python analyze_performance_comparison.py --logs-dir other_dir/
    python analyze_performance_comparison.py --report comparison.md
"""

import json
import os
import glob
import argparse
import statistics
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, List, Any, Optional

PERIOD_BOUNDARIES = [
    ("ANTES",         None,             date(2026, 2, 15)),
    ("POST-OCR",      date(2026, 2, 17), date(2026, 2, 26)),
    ("POST-ROBUSTEZ", date(2026, 2, 28), None),
]


def _period_for_date(d: date) -> Optional[str]:
    for name, start, end in PERIOD_BOUNDARIES:
        after_start = (start is None) or (d >= start)
        before_end = (end is None) or (d <= end)
        if after_start and before_end:
            return name
    return None


def _parse_event_payload(entry: dict) -> Optional[dict]:
    data = entry.get("data")
    if data and isinstance(data, dict) and "event" in data:
        return data
    msg = entry.get("message", "")
    if isinstance(msg, str) and msg.startswith("{") and msg.endswith("}"):
        try:
            parsed = json.loads(msg)
            if isinstance(parsed, dict) and "event" in parsed:
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def load_logs(logs_dir: str):
    """Yield (period_name, event_payload) for every structured event."""
    files = sorted(glob.glob(os.path.join(logs_dir, "structured_events_*.jsonl")))
    print(f"Found {len(files)} log files in {logs_dir}/")
    for fpath in files:
        basename = os.path.basename(fpath)
        date_str = basename.replace("structured_events_", "").replace(".jsonl", "")
        try:
            file_date = datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            continue
        period = _period_for_date(file_date)
        if period is None:
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                payload = _parse_event_payload(entry)
                if payload:
                    yield period, payload, entry.get("timestamp", "")


def _safe_median(values):
    return statistics.median(values) if values else 0.0


def _safe_mean(values):
    return statistics.mean(values) if values else 0.0


def _pct(num, den):
    return (num / den * 100) if den else 0.0


def analyze(logs_dir: str) -> Dict[str, Any]:
    periods: Dict[str, dict] = {}
    for name, _, _ in PERIOD_BOUNDARIES:
        periods[name] = {
            "voice_cmds": [],
            "transcription_times": [],
            "execution_times": [],
            "total_times": [],
            "voice_success": 0,
            "voice_fail": 0,
            "search_success": 0,
            "search_fail": 0,
            "search_scores": [],
            "failure_reasons": defaultdict(int),
            "step_success": 0,
            "step_fail": 0,
            "days": set(),
        }

    for period, payload, ts in load_logs(logs_dir):
        p = periods[period]
        evt = payload.get("event", "")

        if ts:
            try:
                p["days"].add(ts[:10])
            except Exception:
                pass

        if evt == "voice_command.complete":
            p["voice_cmds"].append(payload)
            if payload.get("transcription_time"):
                p["transcription_times"].append(payload["transcription_time"])
            if payload.get("execution_time"):
                p["execution_times"].append(payload["execution_time"])
            if payload.get("total_time"):
                p["total_times"].append(payload["total_time"])
            if payload.get("execution_success"):
                p["voice_success"] += 1
            else:
                p["voice_fail"] += 1

        elif evt == "ui_element_search_success":
            p["search_success"] += 1
            match = payload.get("selected_match", {})
            if match.get("score"):
                p["search_scores"].append(match["score"])

        elif evt in ("ui_element_search_no_match", "ui_element_search_no_matches"):
            p["search_fail"] += 1
            reason = payload.get("failure_reason", "unknown")
            p["failure_reasons"][reason] += 1
            top_score = payload.get("top_match_score")
            if top_score and top_score > 0:
                p["search_scores"].append(top_score)

        elif evt == "command.step.result":
            if payload.get("success"):
                p["step_success"] += 1
            else:
                p["step_fail"] += 1

    return periods


def generate_report(periods: Dict[str, Any], output_file: str):
    lines = []
    lines.append("# Performance Comparison Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Periods")
    lines.append("")
    lines.append("| Period | Date range | Days with data |")
    lines.append("|--------|-----------|----------------|")
    for name, start, end in PERIOD_BOUNDARIES:
        s = str(start) if start else "earliest"
        e = str(end) if end else "today"
        n_days = len(periods[name]["days"])
        lines.append(f"| {name} | {s} .. {e} | {n_days} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 1. Voice Commands (end-to-end)")
    lines.append("")
    lines.append("| Metric | ANTES | POST-OCR | POST-ROBUSTEZ |")
    lines.append("|--------|-------|----------|---------------|")

    row = lambda label, fn: f"| {label} | " + " | ".join(fn(periods[n]) for n, _, _ in PERIOD_BOUNDARIES) + " |"

    lines.append(row("Total commands", lambda p: str(len(p["voice_cmds"]))))
    lines.append(row("Success", lambda p: str(p["voice_success"])))
    lines.append(row("Fail", lambda p: str(p["voice_fail"])))
    lines.append(row("Success rate",
                      lambda p: f"{_pct(p['voice_success'], p['voice_success'] + p['voice_fail']):.1f}%"))
    lines.append(row("Median transcription (s)",
                      lambda p: f"{_safe_median(p['transcription_times']):.2f}"))
    lines.append(row("Median execution (s)",
                      lambda p: f"{_safe_median(p['execution_times']):.2f}"))
    lines.append(row("Median total (s)",
                      lambda p: f"{_safe_median(p['total_times']):.2f}"))
    lines.append(row("Mean total (s)",
                      lambda p: f"{_safe_mean(p['total_times']):.2f}"))
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 2. UI Element Search (OCR + matching)")
    lines.append("")
    lines.append("| Metric | ANTES | POST-OCR | POST-ROBUSTEZ |")
    lines.append("|--------|-------|----------|---------------|")
    lines.append(row("Searches OK", lambda p: str(p["search_success"])))
    lines.append(row("Searches FAIL", lambda p: str(p["search_fail"])))
    total_search = lambda p: p["search_success"] + p["search_fail"]
    lines.append(row("Search success rate",
                      lambda p: f"{_pct(p['search_success'], total_search(p)):.1f}%"))
    lines.append(row("Median match score",
                      lambda p: f"{_safe_median(p['search_scores']):.1f}"))
    lines.append(row("Mean match score",
                      lambda p: f"{_safe_mean(p['search_scores']):.1f}"))
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 3. Step Execution")
    lines.append("")
    lines.append("| Metric | ANTES | POST-OCR | POST-ROBUSTEZ |")
    lines.append("|--------|-------|----------|---------------|")
    lines.append(row("Steps OK", lambda p: str(p["step_success"])))
    lines.append(row("Steps FAIL", lambda p: str(p["step_fail"])))
    total_steps = lambda p: p["step_success"] + p["step_fail"]
    lines.append(row("Step success rate",
                      lambda p: f"{_pct(p['step_success'], total_steps(p)):.1f}%"))
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. Failure Reasons (post-change only)")
    lines.append("")
    for name in ("POST-OCR", "POST-ROBUSTEZ"):
        reasons = periods[name]["failure_reasons"]
        if not reasons:
            continue
        lines.append(f"### {name}")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    antes_reasons = periods["ANTES"]["failure_reasons"]
    if antes_reasons:
        lines.append("### ANTES")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason, count in sorted(antes_reasons.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    lines.append("---")
    lines.append("*Report generated by analyze_performance_comparison.py*")

    report = "\n".join(lines)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to: {output_file}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Compare performance across code-change periods")
    parser.add_argument("--logs-dir", default="structured_logs",
                        help="Directory with structured_events_*.jsonl files")
    parser.add_argument("--report", default="performance_comparison_report.md",
                        help="Output report file")
    args = parser.parse_args()

    print("Loading and classifying events...")
    periods = analyze(args.logs_dir)

    for name, _, _ in PERIOD_BOUNDARIES:
        p = periods[name]
        print(f"  {name}: {len(p['voice_cmds'])} commands, "
              f"{p['search_success']}+{p['search_fail']} searches, "
              f"{len(p['days'])} days")

    print("\nGenerating report...")
    report = generate_report(periods, args.report)
    print("\n" + report)


if __name__ == "__main__":
    main()
