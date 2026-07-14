from __future__ import annotations


CODEX_DARK_PALETTE = {
    "bg": "#ffffff",
    "shell": "#ffffff",
    "panel": "#f7f7f7",
    "panel_alt": "#f1f1f1",
    "selected": "#eaf4ff",
    "text": "#1a1c1f",
    "muted": "#5f6368",
    "subtle": "#8a8f96",
    "hairline": "#e3e3e3",
    "accent": "#339cff",
    "accent_hover": "#1687e8",
    "accent_soft": "#eaf4ff",
    "accent_line": "#8ec6ff",
    "success": "#16803c",
    "warning": "#a15c00",
    "danger": "#c62828",
    "info": "#006fbe",
    "neutral": "#687078",
    "dark_icon": "#1a1c1f",
    "track": "#dce1e6",
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
