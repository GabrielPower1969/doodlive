"""Shared colour palette for the DoodLive themed colouring sheets.

Six colours chosen to sit together across all three angel themes (fiery / wrath / holy):
warm half (ember, gold, ivory) + cool half (indigo, violet, sky). Every coloured example page
uses ONLY these colours, so the three sheets read as one family.
"""

PALETTE = [
    # key,     hex,       Chinese name, English name
    ("ember",  "#E4572E", "烬红",   "Ember"),
    ("gold",   "#F5B841", "金焰",   "Gold"),
    ("ivory",  "#FFF3D6", "象牙白", "Ivory"),
    ("indigo", "#2B2F77", "夜靛蓝", "Indigo"),
    ("violet", "#6C4AB6", "风暴紫", "Storm violet"),
    ("sky",    "#7CC4F0", "天空蓝", "Sky blue"),
]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


COL = {key: hex_to_rgb(hx) for key, hx, _, _ in PALETTE}
