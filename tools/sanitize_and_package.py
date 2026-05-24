import re
from pathlib import Path
import shutil

src=Path('overleaf/memoria_TFG_esqueleto.md')
text=src.read_text(encoding='utf-8')
# remove NUL and other C0 control chars except tab/newline/carriage
text = ''.join(ch for ch in text if (ord(ch) >= 32 or ch in '\n\t\r'))

lines=text.splitlines()
out_lines=[]
inside_fence=False
fence_re=re.compile(r'^(```|~~~)')
for line in lines:
    m=fence_re.match(line)
    if m:
        # toggle fence state
        if not inside_fence:
            inside_fence=True
        else:
            inside_fence=False
        out_lines.append(line)
        continue
    if inside_fence:
        out_lines.append(line)
        continue
    # process non-code line: handle inline code spans by splitting on `
    parts=line.split('`')
    for i in range(0,len(parts),2):
        seg=parts[i]
        # protect $$ pairs
        seg = seg.replace('$$','<<DOLLARS>>')
        # escape single $ remaining
        seg = seg.replace('$','\\$')
        # restore $$
        seg = seg.replace('<<DOLLARS>>','$$')
        # escape unescaped ampersand: replace & not preceded by backslash
        seg = re.sub(r'(?<!\\)&', r'\\&', seg)
        # escape percent signs (not already escaped)
        seg = re.sub(r'(?<!\\)%', r'\\%', seg)
        # escape hash marks if not a heading (we'll handle by checking original line's leading #)
        parts[i]=seg
    # if original line does not start with #, escape remaining # in non-code parts
    if not line.lstrip().startswith('#'):
        for i in range(0,len(parts),2):
            parts[i]=parts[i].replace('#','\\#')
    # rejoin preserving code spans
    newline='`'.join(parts)
    # add width attribute to images without attributes
    # pattern: ![alt](path) optionally followed by { ... }
    def add_width(m):
        whole=m.group(0)
        if whole.endswith('}'):
            return whole
        return whole + '{width=0.6\\linewidth}'
    newline = re.sub(r'!\[[^\]]*\]\([^\)]+\)(?:\{[^}]*\})?', lambda m: add_width(m), newline)
    out_lines.append(newline)

new_text='\n'.join(out_lines)
# quick fix: collapse repeated backslashes produced by replacements (\& etc) to single literal \&; keep as is
src.write_text(new_text,encoding='utf-8')
print('Sanitization complete: wrote',src)
# regenerate zip
shutil.make_archive('overleaf_project','zip','overleaf')
print('Regenerated overleaf_project.zip')
