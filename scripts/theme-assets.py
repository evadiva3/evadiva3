#!/usr/bin/env python3
"""Normalize profile SVGs with stdlib; preserve transparency and readable text.

No flags (or --initial): derive themes from stats.svg, top-langs.svg, snake.svg.
--stats/--snake: normalize freshly generated themed files in place. Workflows
use these flags so an old snapshot never overwrites newly generated API data.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
HEX = re.compile(r'#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{4}\b|#[0-9a-fA-F]{3}\b')
THEMES = {
    'light': {'ink': '#1f2328', 'text': '#59636e', 'track': '#ebedf0',
              'grays': ['#424242', '#5a5a5a', '#717171', '#858585', '#9a9a9a', '#adadad', '#bfbfbf', '#cecece', '#dcdcdc', '#e8e8e8'],
              'dots': ['#ebebeb', '#c6c6c6', '#969696', '#666666', '#3a3a3a'], 'border': '#1f232812'},
    'dark': {'ink': '#e6edf3', 'text': '#9da7b3', 'track': '#24282e',
             'grays': ['#d1d1d1', '#bcbcbc', '#a6a6a6', '#929292', '#7f7f7f', '#6c6c6c', '#5e5e5e', '#535353', '#494949', '#414141'],
             'dots': ['#242424', '#414141', '#686868', '#939393', '#bdbdbd'], 'border': '#e6edf312'},
}

def tag(e):
    return e.tag.rsplit('}', 1)[-1]

def is_background(e, root):
    if e.get('data-testid') == 'card-bg' or 'card-bg' in e.get('class', '').split():
        return True
    return (tag(e) == 'rect' and e.get('width') in {'100%', root.get('width')}
            and e.get('height') in {'100%', root.get('height')}
            and e.get('x', '0') in {'0', '0.0'} and e.get('y', '0') in {'0', '0.0'})

def clear_backgrounds(root):
    def visit(e, definition=False):
        definition = definition or tag(e) in {'defs', 'mask', 'clipPath'}
        if not definition and is_background(e, root):
            e.set('fill', 'none'); e.set('stroke', 'none')
            e.set('fill-opacity', '0'); e.set('stroke-opacity', '0')
            if 'style' in e.attrib:
                e.set('style', re.sub(r'(?:fill|stroke)\s*:[^;]+;?', '', e.get('style', '')))
        for child in e:
            visit(child, definition)
    visit(root)

def write(root, target):
    clear_backgrounds(root)
    serialized = ET.tostring(root, encoding='unicode')
    target.write_text('\n'.join(line.rstrip() for line in serialized.splitlines()) + '\n')
    checked = ET.parse(target).getroot()
    for e in checked.iter():
        if is_background(e, checked):
            assert e.get('fill') == 'none', f'Opaque background in {target}'

def stats(source, target, theme):
    root = ET.parse(source).getroot(); p = THEMES[theme]
    language_colors = []
    for e in root.iter():
        if e.get('data-testid') == 'lang-progress':
            color = e.get('fill', '').lower()
            if color.startswith('#') and color not in language_colors:
                language_colors.append(color)
    lang_map = {color: p['grays'][i % len(p['grays'])] for i, color in enumerate(language_colors)}
    def color(value):
        v = value.lower()
        if v in lang_map: return lang_map[v]
        if v in {'#171717', '#181818', '#151515', '#1f2328', '#e6edf3'}: return p['ink']
        if v in {'#52524b', '#59636e', '#9da7b3'}: return p['text']
        if v in {'#ddd', '#dddddd', '#ebedf0', '#24282e'}: return p['track']
        if v in {'#0000', '#00000000', 'transparent', 'none'}: return value
        return p['text']
    def visit(e, definition=False):
        definition = definition or tag(e) in {'defs', 'mask', 'clipPath'}
        # Definitions may use white masks or black clipping; preserve those.
        if definition: return
        if tag(e) == 'style' and e.text:
            e.text = HEX.sub(lambda m: color(m.group()), e.text)
        if not is_background(e, root):
            for attr in ('fill', 'stroke', 'stop-color', 'color'):
                value = e.get(attr)
                if value and HEX.fullmatch(value): e.set(attr, color(value))
            if 'style' in e.attrib:
                e.set('style', HEX.sub(lambda m: color(m.group()), e.get('style', '')))
        for child in e: visit(child, definition)
    visit(root)
    for existing in list(root):
        if tag(existing) == 'style' and (existing.text or '').startswith('.header,.icon{fill:'):
            root.remove(existing)
    override = ET.SubElement(root, f'{{{NS}}}style')
    override.text = (f'.header,.icon{{fill:{p["ink"]}}}'
                     f'.stat,.rank-text,.lang-name{{fill:{p["text"]}}}'
                     f'.progress-background{{fill:{p["track"]}}}'
                     '.card-bg{fill:none;stroke:none;fill-opacity:0}')
    write(root, target)

def snake(source, target, theme):
    root = ET.parse(source).getroot(); p = THEMES[theme]
    replacements = {'--cb': p['border'], '--cs': p['ink'], '--ce': p['dots'][0],
                    **{f'--c{i}': v for i, v in enumerate(p['dots'])}}
    for e in root.iter():
        if tag(e) == 'style' and e.text:
            for name, value in replacements.items():
                e.text = re.sub(re.escape(name) + r'\s*:\s*[^;}]+', name + ':' + value, e.text)
    write(root, target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initial', action='store_true')
    parser.add_argument('--stats', action='store_true')
    parser.add_argument('--snake', action='store_true')
    args = parser.parse_args()
    initial = args.initial or not (args.stats or args.snake)
    changed = []
    for theme in THEMES:
        if initial or args.stats:
            for stem in ('stats', 'top-langs'):
                source = ASSETS / (f'{stem}.svg' if initial else f'{stem}-{theme}.svg')
                target = ASSETS / f'{stem}-{theme}.svg'
                stats(source, target, theme); changed.append(target.name)
        if initial or args.snake:
            source = ASSETS / ('snake.svg' if initial else f'snake-{theme}.svg')
            target = ASSETS / f'snake-{theme}.svg'
            snake(source, target, theme); changed.append(target.name)
    print('Validated transparent theme assets: ' + ', '.join(changed))

if __name__ == '__main__':
    main()
