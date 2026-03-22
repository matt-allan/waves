"""SVG renderer for GB synth snapshots.

Brutalist / lo-fi aesthetic: monochrome, blocky, no anti-aliasing,
step-interpolated waveforms, monospace everything.  Looks like it
came off a dot-matrix printer or a logic analyzer from 1989.

Two palettes:
  - "paper"  (default): black on off-white, like a printout
  - "dmg":   classic Game Boy dot-matrix green
"""

from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class RenderConfig:
    width: int = 960
    pad: int = 12
    header_h: int = 36
    waveform_h: int = 120
    envelope_h: int = 130
    timbre_h: int = 80
    panning_h: int = 36
    footer_h: int = 28
    palette: str = "paper"  # "paper" or "dmg"


# Palettes
_PALETTES = {
    "paper": {
        "bg": "#f4f1eb",
        "fg": "#1a1a1a",
        "mid": "#888880",
        "faint": "#ccc8be",
        "trace": "#1a1a1a",
        "trace2": "#666660",
        "accent": "#1a1a1a",
        "panel": "#eae7e0",
    },
    "dmg": {
        "bg": "#9bbc0f",
        "fg": "#0f380f",
        "mid": "#306230",
        "faint": "#8bac0f",
        "trace": "#0f380f",
        "trace2": "#306230",
        "accent": "#0f380f",
        "panel": "#8bac0f",
    },
}


def _pal(cfg):
    return _PALETTES.get(cfg.palette, _PALETTES["paper"])


def _svg_open(w, h, bg):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'shape-rendering="crispEdges">\n'
        f'<rect width="{w}" height="{h}" fill="{bg}"/>\n'
    )


def _txt(x, y, text, color, size=10, anchor="start", weight="400"):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" '
            f'font-family="\'Courier New\', Courier, monospace" '
            f'dominant-baseline="auto">{text}</text>\n')


def _hline(x, y, w, color, dashed=False):
    d = ' stroke-dasharray="2,4"' if dashed else ""
    return (f'<line x1="{x}" y1="{y}" x2="{x+w}" y2="{y}" '
            f'stroke="{color}" stroke-width="1"{d}/>\n')


def _vline(x, y, h, color):
    return (f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y+h}" '
            f'stroke="{color}" stroke-width="1"/>\n')


def _step_polyline(points, color, sw=1):
    """Step-interpolated polyline (no smooth lines — each sample holds
    its value until the next one, like a real DAC output)."""
    if len(points) < 2:
        return ""
    segs = []
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        segs.append(f"{x0:.0f},{y0:.0f}")
        segs.append(f"{x1:.0f},{y0:.0f}")  # hold value
    segs.append(f"{points[-1][0]:.0f},{points[-1][1]:.0f}")
    pts = " ".join(segs)
    return (f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}"/>\n')


def _block_bars(x, y, w, h, values, max_val, color, bar_gap=0):
    """Chunky block bars — no rounded corners, no anti-aliasing."""
    if not values or max_val <= 0:
        return ""
    n = len(values)
    bw = max(1, w / n - bar_gap)
    s = ""
    for i, v in enumerate(values):
        bh = (v / max_val) * h
        if bh < 0.5:
            continue
        bx = x + i * (w / n)
        by = y + h - bh
        s += (f'<rect x="{bx:.0f}" y="{by:.0f}" '
              f'width="{bw:.0f}" height="{bh:.0f}" fill="{color}"/>\n')
    return s


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _render_header(snap, cfg):
    p = _pal(cfg)
    m = snap["meta"]
    ch = snap.get("timbre", {}).get("channel", "??")

    s = ""
    # Top rule
    s += _hline(cfg.pad, 4, cfg.width - 2 * cfg.pad, p["fg"])

    title = f"[{ch}]  {m['sample_rate']}Hz  {m['duration_ms']:.0f}ms  {m['n_samples']}smp"
    s += _txt(cfg.pad, 24, title, p["fg"], size=12, weight="700")

    # Version tag
    s += _txt(cfg.width - cfg.pad, 24, f'v{m["version"]}', p["mid"],
              size=9, anchor="end")

    s += _hline(cfg.pad, 32, cfg.width - 2 * cfg.pad, p["fg"])
    return s


def _render_waveform(snap, y0, cfg):
    wf = snap.get("waveform")
    if not wf:
        return ""

    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad
    h = cfg.waveform_h

    s = ""
    s += _txt(cfg.pad, y0 + 11, "WAVEFORM", p["mid"], size=9)
    s += _txt(cfg.width - cfg.pad, y0 + 11,
              f'{wf["fundamental_hz"]:.1f}Hz  {wf["num_cycles"]}cyc',
              p["mid"], size=9, anchor="end")

    gx, gy = cfg.pad, y0 + 16
    gw, gh = pw, h - 20

    # Border
    s += f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" fill="none" stroke="{p["faint"]}"/>\n'

    # Center line
    cy = gy + gh // 2
    s += _hline(gx, cy, gw, p["faint"], dashed=True)

    # Step-interpolated waveform
    vals = wf["values"]
    n = len(vals)
    pts = [(gx + i * gw / (n - 1), cy - v * (gh // 2))
           for i, v in enumerate(vals)]
    s += _step_polyline(pts, p["trace"], sw=1)

    return s


def _render_envelope(snap, y0, cfg):
    env = snap.get("envelope")
    if not env:
        return ""

    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad
    h = cfg.envelope_h

    s = ""
    s += _txt(cfg.pad, y0 + 11, "ENVELOPE", p["mid"], size=9)
    s += _txt(cfg.width - cfg.pad, y0 + 11,
              f'{env["window_ms"]:.0f}ms win  {env["n_windows"]}pts',
              p["mid"], size=9, anchor="end")

    gx, gy = cfg.pad, y0 + 16
    gw, gh = pw, h - 32

    # Border
    s += f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" fill="none" stroke="{p["faint"]}"/>\n'

    left, right = env["left"], env["right"]
    n = len(left)
    if n == 0:
        return s

    mx = max(max(left, default=0), max(right, default=0)) or 1.0

    # Block bars for left channel
    s += _block_bars(gx, gy, gw, gh, left, mx, p["trace"])

    # If right differs from left, overlay with lighter trace
    if right != left:
        s += _block_bars(gx, gy, gw, gh, right, mx, p["trace2"])

    # Time ticks along bottom
    dur = snap["meta"]["duration_ms"]
    s += _hline(gx, gy + gh, gw, p["faint"])
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        tx = gx + frac * gw
        s += _vline(tx, gy + gh, 3, p["mid"])
        s += _txt(tx, gy + gh + 13, f'{frac * dur:.0f}', p["mid"],
                  size=8, anchor="middle")

    # Peak label
    s += _txt(gx + 2, gy + 10, f'{mx:.3f}', p["mid"], size=8)

    # L / R labels if different
    if right != left:
        lx = gx + gw - 40
        s += _txt(lx, gy + 10, "L", p["trace"], size=8, weight="700")
        s += _txt(lx + 14, gy + 10, "R", p["trace2"], size=8, weight="700")

    return s


def _render_timbre(snap, y0, cfg):
    timbre = snap.get("timbre", {})
    ch = timbre.get("channel", "?")
    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad

    s = ""
    s += _hline(cfg.pad, y0, pw, p["faint"])
    s += _txt(cfg.pad, y0 + 13, "TIMBRE", p["mid"], size=9)

    # Channel tag — raw box, no rounded corners
    tag_x = cfg.pad + 56
    tw = len(ch) * 7.5 + 8
    s += (f'<rect x="{tag_x}" y="{y0 + 3}" width="{tw:.0f}" height="14" '
          f'fill="{p["fg"]}" stroke="none"/>\n')
    s += _txt(tag_x + 4, y0 + 13, ch, p["bg"], size=9, weight="700")

    tx = cfg.pad + 12
    ty = y0 + 30

    if ch in ("PU1", "PU2"):
        duty = timbre.get("duty_cycle", "??")
        freq = timbre.get("fundamental_hz")

        s += _txt(tx, ty, f'DUTY  {duty}', p["fg"], size=11, weight="700")
        if freq:
            s += _txt(tx, ty + 16, f'FREQ  {freq:.1f} Hz', p["fg"], size=11)

        # ASCII-art duty cycle: ___----____----___
        # rendered as a blocky waveform diagram
        duty_map = {"12.5%": 0.125, "25%": 0.25, "50%": 0.5, "75%": 0.75}
        d = duty_map.get(duty, 0.5)

        dx = cfg.width // 2
        dy = y0 + 18
        dw, dh = 180, 40

        # Two cycles, step-rendered
        pts = []
        for cyc in range(2):
            cx = dx + cyc * (dw // 2)
            cw = dw // 2
            hi_w = int(d * cw)
            lo_w = cw - hi_w
            pts.extend([
                (cx, dy + dh),          # low start
                (cx, dy),               # rise
                (cx + hi_w, dy),        # high hold
                (cx + hi_w, dy + dh),   # fall
                (cx + hi_w + lo_w, dy + dh),  # low hold
            ])

        if pts:
            p_str = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            s += (f'<polyline points="{p_str}" fill="none" '
                  f'stroke="{p["fg"]}" stroke-width="2"/>\n')

    elif ch == "WAV":
        freq = timbre.get("fundamental_hz")
        if freq:
            s += _txt(tx, ty, f'FREQ  {freq:.1f} Hz', p["fg"], size=11, weight="700")

        spectrum = timbre.get("spectrum", [])
        if spectrum:
            sx = cfg.width // 2
            sh = cfg.timbre_h - 24
            sw = pw // 2 - 8

            all_mags = [pk[1] for pk in spectrum]
            min_db = min(all_mags) - 3
            max_db = max(all_mags) + 3
            db_range = max_db - min_db or 1.0

            bar_w = max(2, sw // (len(spectrum) + 1))
            for i, (freq_hz, mag) in enumerate(spectrum):
                bx = sx + i * (sw // len(spectrum))
                bh = ((mag - min_db) / db_range) * (sh - 4)
                by = y0 + 16 + sh - bh
                s += (f'<rect x="{bx:.0f}" y="{by:.0f}" '
                      f'width="{bar_w}" height="{bh:.0f}" fill="{p["fg"]}"/>\n')

    elif ch == "NOI":
        mode = timbre.get("lfsr_mode", "??")
        s += _txt(tx, ty, f'LFSR  {mode}', p["fg"], size=11, weight="700")
        desc = "(tonal / periodic)" if mode == "7-bit" else "(white noise)"
        s += _txt(tx, ty + 16, desc, p["mid"], size=10)

        # Chunky noise visualization
        nx = cfg.width // 2
        ny = y0 + 18
        nw, nh = 160, 44
        # Deterministic pseudo-noise
        seed = hash(mode) & 0xFFFFFFFF
        rng = seed
        bar_w = nw // 32
        for i in range(32):
            rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
            bh = ((rng >> 16) % 100) / 100.0 * nh
            bx = nx + i * bar_w
            by = ny + nh - bh
            s += (f'<rect x="{bx}" y="{by:.0f}" width="{bar_w - 1}" '
                  f'height="{bh:.0f}" fill="{p["fg"]}"/>\n')

    return s


def _render_panning(snap, y0, cfg):
    pan = snap.get("panning")
    if not pan:
        return ""

    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad

    s = ""
    s += _hline(cfg.pad, y0, pw, p["faint"])

    s += _txt(cfg.pad, y0 + 12, "PAN", p["mid"], size=9)

    # Parse RLE
    rle = pan["states"].split()
    states = []
    for tok in rle:
        if "x" in tok:
            ch, cnt = tok.split("x")
            states.extend([ch] * int(cnt))
        else:
            states.append(tok)

    n = len(states)
    if n == 0:
        return s

    gx = cfg.pad + 32
    gw = pw - 40
    bw = gw / n

    # Simple block representation:
    #   C = full height block
    #   L = top half
    #   R = bottom half
    #   - = empty
    bh = 16
    by = y0 + 4

    for i, st in enumerate(states):
        bx = gx + i * bw
        w = max(1, bw - 0.5)
        if st == "C":
            s += f'<rect x="{bx:.1f}" y="{by}" width="{w:.1f}" height="{bh}" fill="{p["fg"]}"/>\n'
        elif st == "L":
            s += f'<rect x="{bx:.1f}" y="{by}" width="{w:.1f}" height="{bh//2}" fill="{p["fg"]}"/>\n'
        elif st == "R":
            s += f'<rect x="{bx:.1f}" y="{by + bh//2}" width="{w:.1f}" height="{bh//2}" fill="{p["fg"]}"/>\n'
        # '-' = nothing drawn

    # RLE label
    s += _txt(cfg.width - cfg.pad, y0 + 26, pan["states"], p["mid"],
              size=8, anchor="end")

    return s


def _render_footer(snap, y0, cfg):
    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad

    s = ""
    s += _hline(cfg.pad, y0, pw, p["fg"])

    sm = snap["summary"]
    parts = []
    for ch, lbl in [("left", "L"), ("right", "R")]:
        c = sm[ch]
        parts.append(f'Pk{lbl}={c["peak"]:.3f} RMS{lbl}={c["rms"]:.3f} DC{lbl}={c["dc_offset"]:+.3f}')

    s += _txt(cfg.pad, y0 + 16, "  ".join(parts), p["fg"], size=9)
    return s


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_svg(snapshot: dict, config: Optional[RenderConfig] = None) -> str:
    if config is None:
        config = RenderConfig()

    y = 0
    sections = []

    sections.append(("header", y)); y += config.header_h

    if "waveform" in snapshot:
        sections.append(("waveform", y)); y += config.waveform_h + 4

    sections.append(("envelope", y)); y += config.envelope_h + 4
    sections.append(("timbre", y)); y += config.timbre_h + 4
    sections.append(("panning", y)); y += config.panning_h + 4
    sections.append(("footer", y)); y += config.footer_h

    p = _pal(config)
    svg = _svg_open(config.width, y, p["bg"])

    renderers = {
        "header": lambda s, y0, c: _render_header(s, c),
        "waveform": _render_waveform,
        "envelope": _render_envelope,
        "timbre": _render_timbre,
        "panning": _render_panning,
        "footer": _render_footer,
    }

    for name, y0 in sections:
        svg += renderers[name](snapshot, y0, config)

    svg += "</svg>\n"
    return svg
