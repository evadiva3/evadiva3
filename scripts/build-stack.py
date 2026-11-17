#!/usr/bin/env python3
"""Build a transparent SVG stack with decorative dividers and real marks.

Run from any directory: python scripts/build-stack.py
Use --assets-dir to load marks/ and flower-white.svg from another checkout.
"""
from pathlib import Path
import argparse, copy, json, math, re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)

def element(name, attrs=None, text=None):
    node = ET.Element(f'{{{NS}}}{name}', {str(k):str(v) for k,v in (attrs or {}).items()})
    node.text = text
    return node

def text_width(value, size=16):
    """Conservative Arial/Segoe-like advance estimates for safe label wraps."""
    widths = {' ': .28, '·': .28, 'i': .23, 'l': .23, 'I': .28,
              'j': .25, 't': .28, 'f': .30, 'r': .34, 'm': .84,
              'w': .76, 'M': .86, 'W': .95, '/': .30, '-': .34,
              '.': .28, '+': .60}
    return sum(widths.get(c, .64 if c.isupper() else .56) * size for c in value)

def wrap_names(names, narrow):
    limit, pixels = (48, 368) if narrow else (105, 856)
    lines = []
    line = ''
    for name in names:
        proposed = f'{line} · {name}' if line else name
        if line and (len(proposed)>limit or text_width(proposed)>pixels):
            lines.append(line);line=name
        else:line=proposed
    if line:lines.append(line)
    assert all(text_width(line)<=pixels for line in lines)
    return lines

def inline_svg(path, prefix, x, y, width, height):
    node = copy.deepcopy(ET.parse(path).getroot())
    node.set('x',str(x));node.set('y',str(y))
    node.set('width',str(width));node.set('height',str(height))
    node.set('preserveAspectRatio','xMidYMid meet')
    ids = {e.get('id'): prefix+e.get('id') for e in node.iter() if e.get('id')}
    for e in node.iter():
        if e.get('id'):e.set('id',ids[e.get('id')])
        for attr,value in list(e.attrib.items()):
            if attr == 'id':continue
            if attr in {'aria-labelledby','aria-describedby'}:
                e.set(attr,' '.join(ids.get(part,part) for part in value.split()))
            else:
                for old,new in ids.items():
                    value=value.replace(f'url(#{old})',f'url(#{new})')
                    if value==f'#{old}':value=f'#{new}'
                e.set(attr,value)
        if e.tag.rsplit('}',1)[-1]=='style' and e.text:
            for old,new in ids.items():e.text=re.sub(r'#'+re.escape(old)+r'\b','#'+new,e.text)
    return node

def ornament(y, index):
    """A tiny dotted binary ribbon, drawn as artwork rather than text."""
    group=element('g',{'transform':f'translate(53 {y:g})',
        'data-stack-divider':str(index+1),'aria-hidden':'true'})
    for x in (4,244):
        group.append(element('path',{'d':f'M{x} -5 L{x+1.4} -1.4 L{x+5} 0 L{x+1.4} 1.4 L{x} 5 L{x-1.4} 1.4 L{x-5} 0 L{x-1.4} -1.4 Z',
            'fill':'none','stroke':'#ffffff','stroke-width':'1','opacity':'.7'}))
    for start in (16,172):
        group.append(element('path',{'d':f'M{start} 0 c5 -4 9 -4 14 0 s9 4 14 0 s9 -4 14 0 s9 4 14 0',
            'fill':'none','stroke':'#ffffff','stroke-width':'1.35',
            'stroke-linecap':'round','opacity':'.62'}))
    glyphs={'0':['111','101','101','101','111'],
            '1':['010','110','010','010','111']}
    bits=['010110','101001','001101','110010'][index%4]
    for i,bit in enumerate(bits):
        for row,pattern in enumerate(glyphs[bit]):
            for col,on in enumerate(pattern):
                if on=='1':
                    group.append(element('circle',{'cx':90+i*13+col*3,
                        'cy':-6+row*3,'r':'.85','fill':'#ffffff','opacity':'.8'}))
    return group

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-dir',type=Path,default=ROOT/'assets')
    parser.add_argument('--output',type=Path,default=ROOT/'assets/stack-ornaments.svg')
    args=parser.parse_args()
    data=json.loads((ROOT/'data/stack.json').read_text())
    name_count=sum(len(g['names']) for g in data['groups'])
    mark_count=sum(len(g['marks']) for g in data['groups'])
    if not data['groups'] or not name_count:
        raise ValueError('The stack JSON must contain groups with visible names.')
    flower=data['flower']
    flower_root=ET.parse(args.assets_dir/flower['src']).getroot()
    view=[float(x) for x in flower_root.get('viewBox').split()]
    flower_height=flower['width']*view[3]/view[2]
    flower_bottom=flower['y']+flower_height
    cards=[];y=20
    for i,group in enumerate(data['groups']):
        if not group['narrow']:y=max(y,math.ceil(flower_bottom)+22)
        lines=wrap_names(group['names'],group['narrow'])
        rows=math.ceil(len(group['marks'])/group['columns'])
        names_y=62+(rows-1)*76+60+28
        height=names_y+(len(lines)-1)*22+22
        cards.append((group,y,height,lines,names_y))
        y+=height+data['gap']
    height=y-data['gap']+20
    root=element('svg',{'width':1000,'height':height,'viewBox':f'0 0 1000 {height}',
        'role':'img','aria-labelledby':'stack-title stack-desc'})
    root.append(element('title',{'id':'stack-title'},'Tech stack'))
    summary=' '.join(g['title']+': '+', '.join(g['names'])+'.' for g in data['groups'])
    root.append(element('desc',{'id':'stack-desc'},summary+' An ASCII flower overlaps the right side. Small dotted binary-and-tilde ornaments separate the departments.'))
    for i,(group,top,h,lines,names_y) in enumerate(cards):
        card=element('g',{'data-stack-card':str(i+1)})
        card.append(element('text',{'x':52,'y':top+38,'font-family':'Segoe UI, Arial, sans-serif',
            'font-size':24,'font-weight':600,'fill':'#ffffff'},group['title']))
        pitch=74 if group['narrow'] else 105
        for j,mark in enumerate(group['marks']):
            x=52+(j%group['columns'])*pitch
            icon_y=top+62+(j//group['columns'])*76
            icon=inline_svg(args.assets_dir/mark['src'],f'mark-{i}-{j}-',x,icon_y,60,60)
            icon.set('data-stack-mark',mark['id'])
            card.append(icon)
        for j,line in enumerate(lines):
            card.append(element('text',{'x':52,'y':top+names_y+j*22,
                'font-family':'Segoe UI, Arial, sans-serif','font-size':16,
                'fill':'#ffffff','fill-opacity':'.88'},line))
        root.append(card)
        if i<len(cards)-1:
            root.append(ornament(top+h+data['gap']/2,i))
    # LAST layer: the original flower overlaps the right side of the stack.
    # No outer frames, masks, raster references, backgrounds, or animation.
    overlay=inline_svg(args.assets_dir/flower['src'],'stack-flower-',
        flower['x'],flower['y'],flower['width'],f'{flower_height:.3f}')
    overlay.set('data-stack-flower','overlay')
    root.append(overlay)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(ET.tostring(root,encoding='unicode')+'\n')
    checked=ET.parse(args.output).getroot()
    assert checked[-1].get('data-stack-flower')=='overlay'
    assert len([e for e in checked.iter() if e.get('data-stack-mark')])==mark_count
    assert len([e for e in checked.iter() if e.get('data-stack-divider')])==len(cards)-1
    assert not any(e.tag.rsplit('}',1)[-1] in {'image','animate','animateTransform','filter','mask'} for e in checked.iter())
    print(f'{args.output}: 1000×{height}, {args.output.stat().st_size:,} bytes; {name_count} names, {mark_count} inline logos.')
    for group,top,h,lines,names_y in cards:
        print(f"{group['title']}: y={top}, h={h}, name lines={len(lines)}")
    print(f'Flower overlay: x=440 y=30 w=560 h={flower_height:.2f}; bottom={flower_bottom:.2f}')

if __name__=='__main__':main()
