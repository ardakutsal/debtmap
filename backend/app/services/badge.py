from __future__ import annotations


def color_for(score: float) -> str:
    if score <= 20:
        return "#2ea44f"
    if score <= 40:
        return "#7ec93f"
    if score <= 60:
        return "#e3b341"
    if score <= 75:
        return "#e86a2b"
    return "#d1242f"


def render_badge(score: float | None, grade: str | None) -> str:
    if score is None or grade is None:
        label = "debtmap"
        value = "pending"
        color = "#5c6773"
    else:
        label = "debtmap"
        value = f"{grade} · {score:.0f}"
        color = color_for(float(score))

    # shields.io-style flat badge
    label_w = max(60, 8 * len(label) + 10)
    value_w = max(70, 8 * len(value) + 12)
    total = label_w + value_w
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" aria-label="{label}: {value}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".7"/>
    <stop offset=".1" stop-color="#aaa" stop-opacity=".1"/>
    <stop offset=".9" stop-color="#000" stop-opacity=".3"/>
    <stop offset="1" stop-color="#000" stop-opacity=".5"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#24292f"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
    <rect width="{total}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_w/2}" y="15">{label}</text>
    <text x="{label_w + value_w/2}" y="15">{value}</text>
  </g>
</svg>'''
