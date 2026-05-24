import shutil
from pathlib import Path
p=Path('docs/memoria_TFG_esqueleto.md')
q=Path('overleaf/memoria_TFG_esqueleto.md')
shutil.copy2(p,q)
text=q.read_text(encoding='utf-8')
repls = {
    'â–ª': '- ',
    '▪': '- ',
    'â†': '->',
    'â€”': '-',
    'â€“': '-',
}
for k,v in repls.items():
    text = text.replace(k,v)
q.write_text(text,encoding='utf-8')
print('patched', q)
print(text.splitlines()[:8])
