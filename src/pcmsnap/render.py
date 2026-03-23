"""SVG renderer for GB synth snapshots.

Brutalist / lo-fi aesthetic: monochrome, blocky, no anti-aliasing,
step-interpolated waveforms, monospace everything.  Looks like it
came off a dot-matrix printer or a logic analyzer from 1989.

Two palettes:
  - "paper"  (default): black on off-white, like a printout
  - "dmg":   classic Game Boy dot-matrix green
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._types import (
    NoiseTimbre,
    PulseTimbre,
    Snapshot,
    WavTimbre,
)


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


def _pal(cfg: RenderConfig) -> dict[str, str]:
    return _PALETTES.get(cfg.palette, _PALETTES["paper"])


def _svg_open(w: int, h: int, bg: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'shape-rendering="crispEdges">\n'
        f'<rect width="{w}" height="{h}" fill="{bg}"/>\n'
    )


def _txt(
    x: float, y: float, text: str, color: str,
    size: int = 10, anchor: str = "start", weight: str = "400",
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" '
        f"font-family=\"'Courier New', Courier, monospace\" "
        f'dominant-baseline="auto">{text}</text>\n'
    )


def _hline(x: float, y: float, w: float, color: str, dashed: bool = False) -> str:
    d = ' stroke-dasharray="2,4"' if dashed else ""
    return (
        f'<line x1="{x}" y1="{y}" x2="{x + w}" y2="{y}" '
        f'stroke="{color}" stroke-width="1"{d}/>\n'
    )


def _vline(x: float, y: float, h: float, color: str) -> str:
    return (
        f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + h}" '
        f'stroke="{color}" stroke-width="1"/>\n'
    )


def _step_polyline(points: list[tuple[float, float]], color: str, sw: int = 1) -> str:
    """Step-interpolated polyline (no smooth lines — each sample holds
    its value until the next one, like a real DAC output)."""
    if len(points) < 2:
        return ""
    segs: list[str] = []
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, _y1 = points[i + 1]
        segs.append(f"{x0:.0f},{y0:.0f}")
        segs.append(f"{x1:.0f},{y0:.0f}")  # hold value
    segs.append(f"{points[-1][0]:.0f},{points[-1][1]:.0f}")
    pts = " ".join(segs)
    return (
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="{sw}"/>\n'
    )


def _block_bars(
    x: float, y: float, w: float, h: float,
    values: list[float], max_val: float, color: str, bar_gap: float = 0,
) -> str:
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
        s += (
            f'<rect x="{bx:.0f}" y="{by:.0f}" '
            f'width="{bw:.0f}" height="{bh:.0f}" fill="{color}"/>\n'
        )
    return s


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _render_header(snap: Snapshot, _y0: int, cfg: RenderConfig) -> str:
    p = _pal(cfg)
    m = snap.meta
    ch = _channel_name(snap)

    s = ""
    s += _hline(cfg.pad, 4, cfg.width - 2 * cfg.pad, p["fg"])

    title = f"[{ch}]  {m.sample_rate}Hz  {m.duration_ms:.0f}ms  {m.n_samples}smp"
    s += _txt(cfg.pad, 24, title, p["fg"], size=12, weight="700")

    s += _txt(
        cfg.width - cfg.pad, 24, f"v{m.version}", p["mid"],
        size=9, anchor="end",
    )

    s += _hline(cfg.pad, 32, cfg.width - 2 * cfg.pad, p["fg"])
    return s


def _render_waveform(snap: Snapshot, y0: int, cfg: RenderConfig) -> str:
    wf = snap.waveform
    if not wf:
        return ""

    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad
    h = cfg.waveform_h

    s = ""
    s += _txt(cfg.pad, y0 + 11, "WAVEFORM", p["mid"], size=9)
    s += _txt(
        cfg.width - cfg.pad, y0 + 11,
        f"{wf.fundamental_hz:.1f}Hz  {wf.num_cycles}cyc",
        p["mid"], size=9, anchor="end",
    )

    gx, gy = cfg.pad, y0 + 16
    gw, gh = pw, h - 20

    s += (
        f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" '
        f'fill="none" stroke="{p["faint"]}"/>\n'
    )

    cy = gy + gh // 2
    s += _hline(gx, cy, gw, p["faint"], dashed=True)

    vals = wf.values
    n = len(vals)
    pts = [
        (gx + i * gw / (n - 1), cy - v * (gh // 2))
        for i, v in enumerate(vals)
    ]
    s += _step_polyline(pts, p["trace"], sw=1)

    return s


def _render_envelope(snap: Snapshot, y0: int, cfg: RenderConfig) -> str:
    env = snap.envelope

    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad
    h = cfg.envelope_h

    s = ""
    s += _txt(cfg.pad, y0 + 11, "ENVELOPE", p["mid"], size=9)
    s += _txt(
        cfg.width - cfg.pad, y0 + 11,
        f"{env.window_ms:.0f}ms win  {env.n_windows}pts",
        p["mid"], size=9, anchor="end",
    )

    gx, gy = cfg.pad, y0 + 16
    gw, gh = pw, h - 32

    s += (
        f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" '
        f'fill="none" stroke="{p["faint"]}"/>\n'
    )

    left, right = env.left, env.right
    n = len(left)
    if n == 0:
        return s

    mx = max(max(left, default=0), max(right, default=0)) or 1.0

    s += _block_bars(gx, gy, gw, gh, left, mx, p["trace"])

    if right != left:
        s += _block_bars(gx, gy, gw, gh, right, mx, p["trace2"])

    dur = snap.meta.duration_ms
    s += _hline(gx, gy + gh, gw, p["faint"])
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        tx = gx + frac * gw
        s += _vline(tx, gy + gh, 3, p["mid"])
        s += _txt(tx, gy + gh + 13, f"{frac * dur:.0f}", p["mid"], size=8, anchor="middle")

    s += _txt(gx + 2, gy + 10, f"{mx:.3f}", p["mid"], size=8)

    if right != left:
        lx = gx + gw - 40
        s += _txt(lx, gy + 10, "L", p["trace"], size=8, weight="700")
        s += _txt(lx + 14, gy + 10, "R", p["trace2"], size=8, weight="700")

    return s


def _render_timbre(snap: Snapshot, y0: int, cfg: RenderConfig) -> str:
    timbre = snap.timbre
    ch = _channel_name(snap)
    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad

    s = ""
    s += _hline(cfg.pad, y0, pw, p["faint"])
    s += _txt(cfg.pad, y0 + 13, "TIMBRE", p["mid"], size=9)

    tag_x = cfg.pad + 56
    tw = len(ch) * 7.5 + 8
    s += (
        f'<rect x="{tag_x}" y="{y0 + 3}" width="{tw:.0f}" height="14" '
        f'fill="{p["fg"]}" stroke="none"/>\n'
    )
    s += _txt(tag_x + 4, y0 + 13, ch, p["bg"], size=9, weight="700")

    tx = cfg.pad + 12
    ty = y0 + 30

    if isinstance(timbre, PulseTimbre):
        duty = timbre.duty_cycle or "??"
        freq = timbre.fundamental_hz

        s += _txt(tx, ty, f"DUTY  {duty}", p["fg"], size=11, weight="700")
        if freq:
            s += _txt(tx, ty + 16, f"FREQ  {freq:.1f} Hz", p["fg"], size=11)

        duty_map = {"12.5%": 0.125, "25%": 0.25, "50%": 0.5, "75%": 0.75}
        d = duty_map.get(duty, 0.5)

        dx = cfg.width // 2
        dy = y0 + 18
        dw, dh = 180, 40

        pts: list[tuple[float, float]] = []
        for cyc in range(2):
            cx = dx + cyc * (dw // 2)
            cw = dw // 2
            hi_w = int(d * cw)
            lo_w = cw - hi_w
            pts.extend([
                (cx, dy + dh),
                (cx, dy),
                (cx + hi_w, dy),
                (cx + hi_w, dy + dh),
                (cx + hi_w + lo_w, dy + dh),
            ])

        if pts:
            p_str = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            s += (
                f'<polyline points="{p_str}" fill="none" '
                f'stroke="{p["fg"]}" stroke-width="2"/>\n'
            )

    elif isinstance(timbre, WavTimbre):
        freq = timbre.fundamental_hz
        if freq:
            s += _txt(tx, ty, f"FREQ  {freq:.1f} Hz", p["fg"], size=11, weight="700")

        spectrum = timbre.spectrum
        if spectrum:
            sx = cfg.width // 2
            sh = cfg.timbre_h - 24
            sw = pw // 2 - 8

            all_mags = [pk.mag_db for pk in spectrum]
            min_db = min(all_mags) - 3
            max_db = max(all_mags) + 3
            db_range = max_db - min_db or 1.0

            bar_w = max(2, sw // (len(spectrum) + 1))
            for i, pk in enumerate(spectrum):
                bx = sx + i * (sw // len(spectrum))
                bh = ((pk.mag_db - min_db) / db_range) * (sh - 4)
                by = y0 + 16 + sh - bh
                s += (
                    f'<rect x="{bx:.0f}" y="{by:.0f}" '
                    f'width="{bar_w}" height="{bh:.0f}" fill="{p["fg"]}"/>\n'
                )

    elif isinstance(timbre, NoiseTimbre):
        mode = timbre.lfsr_mode or "??"
        s += _txt(tx, ty, f"LFSR  {mode}", p["fg"], size=11, weight="700")
        desc = "(tonal / periodic)" if mode == "7-bit" else "(white noise)"
        s += _txt(tx, ty + 16, desc, p["mid"], size=10)

        nx = cfg.width // 2
        ny = y0 + 18
        nw, nh = 160, 44
        seed = hash(mode) & 0xFFFFFFFF
        rng = seed
        bar_w = nw // 32
        for i in range(32):
            rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
            bh = ((rng >> 16) % 100) / 100.0 * nh
            bx = nx + i * bar_w
            by = ny + nh - bh
            s += (
                f'<rect x="{bx}" y="{by:.0f}" width="{bar_w - 1}" '
                f'height="{bh:.0f}" fill="{p["fg"]}"/>\n'
            )

    return s


def _render_panning(snap: Snapshot, y0: int, cfg: RenderConfig) -> str:
    pan = snap.panning
    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad

    s = ""
    s += _hline(cfg.pad, y0, pw, p["faint"])
    s += _txt(cfg.pad, y0 + 12, "PAN", p["mid"], size=9)

    states = pan.expand()
    n = len(states)
    if n == 0:
        return s

    gx = cfg.pad + 32
    gw = pw - 40
    bw = gw / n

    bh = 16
    by = y0 + 4

    for i, st in enumerate(states):
        bx = gx + i * bw
        w = max(1, bw - 0.5)
        if st == "C":
            s += f'<rect x="{bx:.1f}" y="{by}" width="{w:.1f}" height="{bh}" fill="{p["fg"]}"/>\n'
        elif st == "L":
            s += f'<rect x="{bx:.1f}" y="{by}" width="{w:.1f}" height="{bh // 2}" fill="{p["fg"]}"/>\n'
        elif st == "R":
            s += f'<rect x="{bx:.1f}" y="{by + bh // 2}" width="{w:.1f}" height="{bh // 2}" fill="{p["fg"]}"/>\n'

    s += _txt(
        cfg.width - cfg.pad, y0 + 26, pan.states_str,
        p["mid"], size=8, anchor="end",
    )

    return s


def _render_footer(snap: Snapshot, y0: int, cfg: RenderConfig) -> str:
    p = _pal(cfg)
    pw = cfg.width - 2 * cfg.pad

    s = ""
    s += _hline(cfg.pad, y0, pw, p["fg"])

    sm = snap.summary
    parts = []
    for ch_data, lbl in [(sm.left, "L"), (sm.right, "R")]:
        parts.append(
            f"Pk{lbl}={ch_data.peak:.3f} "
            f"RMS{lbl}={ch_data.rms:.3f} "
            f"DC{lbl}={ch_data.dc_offset:+.3f}"
        )

    s += _txt(cfg.pad, y0 + 16, "  ".join(parts), p["fg"], size=9)
    return s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _channel_name(snap: Snapshot) -> str:
    return snap.timbre.channel


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_svg(snapshot: Snapshot, config: Optional[RenderConfig] = None) -> str:
    if config is None:
        config = RenderConfig()

    y = 0
    sections: list[tuple[str, int]] = []

    sections.append(("header", y))
    y += config.header_h

    if snapshot.waveform is not None:
        sections.append(("waveform", y))
        y += config.waveform_h + 4

    sections.append(("envelope", y))
    y += config.envelope_h + 4
    sections.append(("timbre", y))
    y += config.timbre_h + 4
    sections.append(("panning", y))
    y += config.panning_h + 4
    sections.append(("footer", y))
    y += config.footer_h

    p = _pal(config)
    svg = _svg_open(config.width, y, p["bg"])

    renderers = {
        "header": _render_header,
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
