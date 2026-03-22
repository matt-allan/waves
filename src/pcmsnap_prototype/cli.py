#!/usr/bin/env python3
"""Command-line interface for synth_snapshot.

Usage:
    # Generate JSON snapshot from WAV (auto-detect channel type)
    python -m synth_snapshot snap output.wav -o test.snap.json

    # Specify GB channel type
    python -m synth_snapshot snap pu1_output.wav --channel PU1 -o test.snap.json

    # Generate from raw 16-bit stereo
    python -m synth_snapshot snap output.raw -f raw -r 44100 -o test.snap.json

    # Render SVG from existing snapshot
    python -m synth_snapshot render test.snap.json -o test.svg

    # Do both in one step
    python -m synth_snapshot snap output.wav -o test.snap.json --svg test.svg

    # Compare two snapshots
    python -m synth_snapshot diff old.snap.json new.snap.json
"""

import argparse
import sys
import json

from .formats import load_audio
from .analyze import analyze, snapshot_to_json, snapshot_from_json, GBSnapshotConfig
from .render import render_svg


def cmd_snap(args):
    left, right, sr = load_audio(
        args.input,
        format=args.format,
        sample_rate=args.sample_rate,
        channels=args.channels,
        bit_depth=args.bit_depth,
        byte_order=args.byte_order,
    )

    config = GBSnapshotConfig(channel=args.channel)
    if args.window_ms:
        config.envelope_window_ms = args.window_ms

    snapshot = analyze(left, right, sr, config)

    out = args.output or args.input.rsplit(".", 1)[0] + ".snap.json"
    with open(out, "w") as f:
        f.write(snapshot_to_json(snapshot))
    print(f"Snapshot: {out}")

    if args.svg:
        with open(args.svg, "w") as f:
            f.write(render_svg(snapshot))
        print(f"SVG:      {args.svg}")


def cmd_render(args):
    with open(args.input) as f:
        snapshot = snapshot_from_json(f.read())
    out = args.output or args.input.rsplit(".", 1)[0] + ".svg"
    with open(out, "w") as f:
        f.write(render_svg(snapshot))
    print(f"SVG: {out}")


def cmd_diff(args):
    with open(args.old) as f:
        old = snapshot_from_json(f.read())
    with open(args.new) as f:
        new = snapshot_from_json(f.read())
    _diff_snapshots(old, new)


def _diff_snapshots(old, new, prefix=""):
    changes = 0
    for key in sorted(set(list(old.keys()) + list(new.keys()))):
        path = f"{prefix}.{key}" if prefix else key
        if key not in old:
            print(f"  + {path}: {_summarize(new[key])}")
            changes += 1
        elif key not in new:
            print(f"  - {path}: {_summarize(old[key])}")
            changes += 1
        elif isinstance(old[key], dict) and isinstance(new[key], dict):
            changes += _diff_snapshots(old[key], new[key], path)
        elif isinstance(old[key], list) and isinstance(new[key], list):
            if old[key] != new[key]:
                if (all(isinstance(x, (int, float)) for x in old[key]) and
                        all(isinstance(x, (int, float)) for x in new[key])):
                    if len(old[key]) == len(new[key]):
                        diffs = [abs(a - b) for a, b in zip(old[key], new[key])]
                        changed = sum(1 for d in diffs if d > 0)
                        print(f"  ~ {path}: {changed}/{len(old[key])} values changed, "
                              f"max Δ={max(diffs):.4f}, avg Δ={sum(diffs)/len(diffs):.4f}")
                    else:
                        print(f"  ~ {path}: length {len(old[key])} -> {len(new[key])}")
                else:
                    print(f"  ~ {path}: changed")
                changes += 1
        elif old[key] != new[key]:
            print(f"  ~ {path}: {old[key]} -> {new[key]}")
            changes += 1
    if not prefix:
        print(f"\n{changes} difference(s)." if changes else "No differences.")
    return changes


def _summarize(val):
    if isinstance(val, list):
        return f"[{len(val)} items]"
    if isinstance(val, dict):
        return f"{{{len(val)} keys}}"
    return str(val)


def main():
    parser = argparse.ArgumentParser(prog="synth_snapshot",
                                     description="GB synth snapshot testing")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("snap", help="Generate snapshot from audio")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("-f", "--format", default="auto",
                   choices=["auto", "raw", "wav", "aiff"])
    p.add_argument("-r", "--sample-rate", type=int, default=44100)
    p.add_argument("-c", "--channels", type=int, default=2)
    p.add_argument("-b", "--bit-depth", type=int, default=16)
    p.add_argument("--byte-order", default="little", choices=["little", "big"])
    p.add_argument("--channel", default="auto",
                   choices=["auto", "PU1", "PU2", "WAV", "NOI"])
    p.add_argument("--svg")
    p.add_argument("--window-ms", type=float)

    p = sub.add_parser("render", help="Render SVG from snapshot")
    p.add_argument("input")
    p.add_argument("-o", "--output")

    p = sub.add_parser("diff", help="Compare two snapshots")
    p.add_argument("old")
    p.add_argument("new")

    args = parser.parse_args()
    {"snap": cmd_snap, "render": cmd_render, "diff": cmd_diff}.get(
        args.command, lambda _: parser.print_help())(args)


if __name__ == "__main__":
    main()
