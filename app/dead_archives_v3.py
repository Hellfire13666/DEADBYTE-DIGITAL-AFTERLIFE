# DEADBYTE // DEAD ARCHIVES v3
"""Archive metadata research only. No direct target page fetching."""
import datetime, html, json, os, re
from pathlib import Path
from urllib.parse import urlparse

STOP={'a','an','the','of','at','in','on','from','to','for','with','by','and','or','was',
      'were','is','are','be','been','do','did','does','please','find','search','show',
      'give','me','what','which','who','where','when','how','about','some','records',
      'information','can','you','tell','look','up','i','want','would','like','could',
      'there','any','have','has','had','closest','nearest','nearby','recent','latest'}
SOURCES={1:'Internet Archive',2:'Open Library',3:'Library of Congress',
         4:'Wikisource',5:'Project Gutenberg',6:'Historical Newspapers / LOC',
         9:'Archive-It',10:'Europeana'}

def _plain(val):
    if isinstance(val,(list,tuple)):
        val='; '.join(str(x) for x in val[:5])
    return ' '.join(re.sub(r'<[^>]*>',' ',html.unescape(str(val or ''))).split())

def terms(question):
    words=re.findall(r"[^\W_]+(?:['’-][^\W_]+)*",question.lower(),flags=re.UNICODE)
    useful=[w for w in words if (len(w)>2 or w.isdigit()) and w not in STOP]
    return useful[:25], ' '.join(useful[:25]) or question.strip()

def _rank(record,keywords):
    title=_plain(record.get('title','')).casefold()
    desc=_plain(record.get('description','')).casefold()
    score=0
    for word in keywords:
        if word in title: score+=4
        elif word in desc: score+=1
    return score

def _save(question,query,records,errors,counts):
    vault=Path.home()/'.local/share/deadbyte'
    vault.mkdir(parents=True,exist_ok=True,mode=0o700)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    payload={'source':'DEAD ARCHIVES v3', 'question':question, 'query':query,
             'searched_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'scope':'Public archive metadata, keyword relevance only; not current weather or nearest-storm verification',
             'provider_counts':counts,'provider_errors':errors, 'records':records}
    path=vault/(stamp+'.json')
    with path.open('x',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2,default=str)
    text=vault/(stamp+'.txt')
    with text.open('x',encoding='utf-8') as f:
        f.write('DEADBYTE // DEAD ARCHIVES v3\nQUESTION: '+question+'\nQUERY: '+query+'\n\n')
        for i,r in enumerate(records,1):
            f.write(f"[{i:03}] {r['title']}\nSOURCE: {r['source']}\nDATE: {r['date']}\nURL: {r['url']}\nDETAILS: {r['description']}\n\n")
        f.write('PROVIDER ERRORS: '+json.dumps(errors,ensure_ascii=False)+'\n')
    return path,text


def run(search_function, archive_module_path):
    """Delegates search only; visual layout and existing menu are unchanged."""
    import importlib.util
    from pathlib import Path
    path = Path.home()/'.local/share/deadbyte/dead_archives_intelligence_v32.py'
    spec = importlib.util.spec_from_file_location('deadbyte_reaper_intelligence_v32', path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine.run(search_function, archive_module_path)

# DEADBYTE_REAPER_INTELLIGENCE_V3_2

# DEADBYTE_SEARCH_ROUTER_V3_1
