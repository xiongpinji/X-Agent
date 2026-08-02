import warnings
from fastapi.testclient import TestClient
from backend.app.main import app
import backend.app.main as m
print('main from:', m.__file__)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    with TestClient(app) as c:
        r = c.get('/openapi.json')
        print('openapi:', r.status_code)
dups = [str(x.message) for x in w if 'uplicate' in str(x.message)]
print('dup warnings:', len(dups))
for m_ in dups[:30]: print(m_)
cr = [r.path for r in app.routes if 'code-review' in getattr(r,'path','')]
from collections import Counter
print('code-review routes:')
for p, cnt in sorted(Counter(cr).items()): print(' ', cnt, p)
