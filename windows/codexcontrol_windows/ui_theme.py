from __future__ import annotations


CODEX_DARK_PALETTE = {
    "bg": "#070b10",
    "shell": "#0d131a",
    "panel": "#151d26",
    "panel_alt": "#1c2733",
    "selected": "#102822",
    "text": "#f3f7fb",
    "muted": "#b7c3d0",
    "subtle": "#8292a4",
    "hairline": "#2d3a46",
    "accent": "#31d18b",
    "accent_hover": "#3ee6a0",
    "accent_soft": "#123428",
    "accent_line": "#277b5a",
    "success": "#31d18b",
    "warning": "#f3bd5b",
    "danger": "#ff7a70",
    "info": "#63c5ff",
    "neutral": "#9fb0c0",
    "dark_icon": "#091016",
    "track": "#2a3642",
}


def contrast_ratio(foreground: str, background: str) -> float:
    fg = _relative_luminance(_hex_to_rgb_unit(foreground))
    bg = _relative_luminance(_hex_to_rgb_unit(background))
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def _hex_to_rgb_unit(value: str) -> tuple[float, float, float]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        raise ValueError("colors must be six-digit hex values")
    return tuple(int(cleaned[index:index + 2], 16) / 255.0 for index in (0, 2, 4))


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    red, green, blue = (_linearize(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _linearize(channel: float) -> float:
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4
