from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/content/duel_cards.py'
OUT_DIR = ROOT / 'app/static/images/cards/generated'

PALETTES = [
    ('#54d6ca', '#f4cf63', '#172d54', '#0a1020'),
    ('#7fc8ff', '#f47ca8', '#21375f', '#0b1227'),
    ('#f48a52', '#8bd66b', '#3a1f40', '#120914'),
    ('#bba2ff', '#65e0bb', '#2b2358', '#0f1025'),
    ('#ffd166', '#6ccff6', '#35213b', '#100d18'),
    ('#ef5d75', '#f2d492', '#2b1b32', '#10070f'),
    ('#7de2d1', '#b5e48c', '#143b45', '#071719'),
    ('#9ad0ec', '#f7a072', '#1f2a44', '#090d18'),
]


def _card_ids() -> list[str]:
    text = SOURCE.read_text(encoding='utf-8')
    ids = set(re.findall(r"_item\(\s*'([^']+)'", text))
    ids.update(re.findall(r"_token\(\s*'([^']+)'", text))
    return sorted(ids)


def _points(center_x: int, center_y: int, radius: int, sides: int, offset: float) -> str:
    import math

    values = []
    for index in range(sides):
        angle = offset + math.tau * index / sides
        values.append(f'{center_x + math.cos(angle) * radius:.1f},{center_y + math.sin(angle) * radius:.1f}')
    return ' '.join(values)


def _shape(card_id: str, digest: bytes, accent: str, secondary: str, base: str) -> str:
    shape_id = digest[2] % 10
    rotation = digest[3] % 360
    opacity = 0.78 + (digest[4] % 16) / 100
    transform = f'rotate({rotation} 160 204)'
    if shape_id == 0:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <polygon points="160,72 185,154 270,154 201,202 226,286 160,236 94,286 119,202 50,154 135,154" fill="{secondary}" opacity="0.9"/>
    <polygon points="160,110 176,164 232,164 187,197 203,252 160,220 117,252 133,197 88,164 144,164" fill="{accent}"/>
  </g>'''
    if shape_id == 1:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <polygon points="160,68 258,204 160,340 62,204" fill="{base}" stroke="{accent}" stroke-width="12"/>
    <polygon points="160,108 224,204 160,300 96,204" fill="{secondary}" opacity="0.86"/>
    <circle cx="160" cy="204" r="42" fill="{accent}" opacity="0.9"/>
  </g>'''
    if shape_id == 2:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <circle cx="160" cy="204" r="118" fill="none" stroke="{secondary}" stroke-width="18"/>
    <circle cx="160" cy="204" r="72" fill="{base}" stroke="{accent}" stroke-width="10"/>
    <circle cx="160" cy="204" r="28" fill="{secondary}"/>
  </g>'''
    if shape_id == 3:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <polygon points="{_points(160, 204, 124, 6, 0.52)}" fill="{base}" stroke="{accent}" stroke-width="10"/>
    <polygon points="{_points(160, 204, 76, 6, 0.52)}" fill="{secondary}" opacity="0.9"/>
  </g>'''
    if shape_id == 4:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <path d="M96 86h92l48 48v188H96z" fill="{base}" stroke="{accent}" stroke-width="9"/>
    <path d="M188 86v48h48" fill="none" stroke="{secondary}" stroke-width="9"/>
    <path d="M124 178h72M124 212h92M124 246h62" stroke="{secondary}" stroke-width="11" stroke-linecap="round"/>
    <circle cx="226" cy="286" r="34" fill="{accent}" opacity="0.85"/>
  </g>'''
    if shape_id == 5:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <path d="M92 82h136c-8 62-35 89-68 122 33 33 60 60 68 122H92c8-62 35-89 68-122-33-33-60-60-68-122z" fill="{base}" stroke="{accent}" stroke-width="10"/>
    <path d="M124 112h72M124 296h72M160 204l38 80h-76z" fill="{secondary}" opacity="0.9"/>
  </g>'''
    if shape_id == 6:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <path d="M160 58c34 50 12 73 48 110 22 23 34 54 24 88-14 48-53 78-101 70-42-7-72-42-73-82-1-45 29-72 63-98 30-23 37-48 39-88z" fill="{secondary}" opacity="0.9"/>
    <path d="M159 147c23 35 12 54 31 78 11 14 14 34 5 51-12 25-38 39-66 28-23-9-36-31-34-54 2-27 20-43 41-59 15-12 20-25 23-44z" fill="{accent}"/>
  </g>'''
    if shape_id == 7:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <path d="M160 76l116 70v116l-116 70-116-70V146z" fill="{base}" stroke="{accent}" stroke-width="10"/>
    <path d="M160 76v256M44 146l232 116M276 146L44 262" stroke="{secondary}" stroke-width="8" opacity="0.85"/>
    <circle cx="160" cy="204" r="44" fill="{secondary}" opacity="0.9"/>
  </g>'''
    if shape_id == 8:
        return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <path d="M80 168c42-72 118-72 160 0 10 18 10 54 0 72-42 72-118 72-160 0-10-18-10-54 0-72z" fill="{base}" stroke="{accent}" stroke-width="10"/>
    <circle cx="160" cy="204" r="58" fill="{secondary}" opacity="0.9"/>
    <circle cx="160" cy="204" r="22" fill="{accent}"/>
  </g>'''
    return f'''
  <g transform="{transform}" opacity="{opacity:.2f}">
    <path d="M78 246c42-108 122-150 204-98-74 12-94 62-88 146-36-38-75-50-116-48z" fill="{secondary}" opacity="0.9"/>
    <path d="M92 286c52-76 116-104 176-70-50 10-72 42-76 92-30-24-63-30-100-22z" fill="{accent}"/>
  </g>'''


def _svg(card_id: str, index: int) -> str:
    digest = hashlib.sha256(card_id.encode('utf-8')).digest()
    accent, secondary, base, dark = PALETTES[digest[0] % len(PALETTES)]
    pattern_size = 18 + digest[5] % 22
    dot_x = 4 + digest[6] % max(5, pattern_size - 4)
    dot_y = 4 + digest[7] % max(5, pattern_size - 4)
    safe_title = html.escape(card_id)
    shape = _shape(card_id, digest, accent, secondary, base)
    gradient = f'g{index}'
    pattern = f'p{index}'
    glow = f'f{index}'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 448" role="img">
  <title>{safe_title}</title>
  <defs>
    <linearGradient id="{gradient}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{dark}"/>
      <stop offset="0.52" stop-color="{base}"/>
      <stop offset="1" stop-color="#070912"/>
    </linearGradient>
    <pattern id="{pattern}" width="{pattern_size}" height="{pattern_size}" patternUnits="userSpaceOnUse">
      <path d="M0 {pattern_size}L{pattern_size} 0" stroke="{accent}" stroke-width="1.4" opacity="0.24"/>
      <circle cx="{dot_x}" cy="{dot_y}" r="1.7" fill="{secondary}" opacity="0.42"/>
    </pattern>
    <filter id="{glow}" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="7" result="blur"/>
      <feColorMatrix in="blur" type="matrix" values="0 0 0 0 0.4 0 0 0 0 0.95 0 0 0 0 0.9 0 0 0 0.8 0"/>
      <feBlend in="SourceGraphic"/>
    </filter>
  </defs>
  <rect width="320" height="448" rx="22" fill="url(#{gradient})"/>
  <rect x="12" y="12" width="296" height="424" rx="20" fill="#07111d" opacity="0.72" stroke="{accent}" stroke-width="3"/>
  <rect x="28" y="30" width="264" height="286" rx="18" fill="url(#{pattern})" opacity="0.88"/>
  <path d="M38 344c42-24 76-24 118 0s82 24 126 0" fill="none" stroke="{secondary}" stroke-width="6" opacity="0.72" stroke-linecap="round"/>
  <path d="M52 366c32-14 64-14 96 0s72 14 118 0" fill="none" stroke="{accent}" stroke-width="4" opacity="0.72" stroke-linecap="round"/>
  <g filter="url(#{glow})">{shape}
  </g>
  <rect x="50" y="382" width="220" height="38" rx="12" fill="#070b13" opacity="0.74" stroke="{accent}" stroke-width="2"/>
  <text x="160" y="407" fill="#f6fbff" font-family="Arial, sans-serif" font-size="15" font-weight="700" text-anchor="middle">{safe_title}</text>
</svg>
'''


def main() -> None:
    ids = _card_ids()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for index, card_id in enumerate(ids):
        (OUT_DIR / f'{card_id}.svg').write_text(_svg(card_id, index), encoding='utf-8')
    print(f'generated {len(ids)} card svgs')


if __name__ == '__main__':
    main()
