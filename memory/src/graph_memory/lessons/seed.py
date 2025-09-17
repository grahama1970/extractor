from __future__ import annotations
import time, uuid, random
from typing import List
import typer
from ..arango_client import get_db

app = typer.Typer(add_completion=False)

TOPICS = [
    ("CDP discovery", ["cdp", "devtools", "puppeteer", "playwright"], "tabbed"),
    ("Vite proxy alignment", ["proxy", "vite", "backend", "api"], "tabbed"),
    ("pdf.js render cancelation", ["pdfjs", "render", "abort", "canvas"], "tabbed"),
    ("Thumbnails rail/filmstrip", ["thumbnails", "rail", "filmstrip", "cache"], "tabbed"),
    ("Resizable panes + ARIA", ["aria", "a11y", "resizer", "keyboard"], "tabbed"),
    ("Export dropdown rules", ["export", "json", "pdf", "zip"], "tabbed"),
    ("Exact JSON toggle", ["json", "strict", "canonical", "toggle"], "tabbed"),
    ("Pager placement", ["pager", "toolbar", "zoom"], "tabbed"),
    ("Lessons infra", ["codex", "uv", "docker", "arango", "redis"], "infra"),
    ("Gemini JSON reliability", ["gemini", "litellm", "json", "schema"], "pipeline"),
]

SUFFIXES = ["gotchas and fixes", "playbook", "stability guide", "troubleshooting", "pitfalls", "design notes"]

def build_keywords(tags: List[str], scope: str) -> str:
    syn = {"cdp":["chrome","chromium","devtools","browserless","puppeteer","playwright"],"proxy":["vite","backend","target","api","port","8000","8001"],"json":["response_format","schema","structured","wrap_json"],"smokes":["smoke","ci","tests","playwright","puppeteer"]}
    bag:list[str]=[]
    for t in tags or []: bag.append(t); bag.extend(syn.get(t.lower(),[]))
    if scope: bag.append(scope)
    seen=set(); out:list[str]=[]
    for w in bag:
        if w and w not in seen: seen.add(w); out.append(w)
    return ' '.join(out)

@app.command()
def seed(count:int=typer.Option(50), scope:str=typer.Option('', help='optional scope'), batch:str=typer.Option('', help='demo batch id')):
    db=get_db()
    col=db.collection('lessons')
    ts=int(time.time())
    batch_id=batch or uuid.uuid4().hex[:12]
    for i in range(count):
        base,base_tags,base_scope=random.choice(TOPICS)
        sc= scope or base_scope
        title=f'DEMO[{batch_id}] {base} #{i+1} {random.choice(SUFFIXES)}'
        problem=f'Exploration of {base} within the project: common pitfalls and how to avoid them.'
        playbook='- Identify root cause\n- Apply stable settings and add smokes\n- Document rationale and add graph edges'
        tags=list(set(random.sample(base_tags, min(3,len(base_tags)))))
        keywords=build_keywords(tags, sc)
        doc={ 'title':title,'problem':problem,'playbook':playbook,'tags':tags,'keywords':keywords,'scope':sc,'status':'active','added_by':'agent','updated_at':ts,'demo':True,'demo_batch':batch_id }
        aql= 'UPSERT { title:@t, scope:@s } INSERT @d UPDATE @d IN lessons RETURN NEW'
        db.aql.execute(aql, bind_vars={'t':title,'s':sc,'d':doc})
    print(f'Seeded {count} demo lessons (batch={batch_id}).')
