"""No-key, bounded JSON searches of the public LOC catalogs."""
import html, json, re, urllib.parse, urllib.request

BASE={3:'https://www.loc.gov/search/',
      6:'https://www.loc.gov/collections/chronicling-america/'}

def _txt(value):
    if isinstance(value, list):
        value='; '.join(str(x) for x in value[:4])
    elif isinstance(value, dict):
        value=value.get('text') or value.get('value') or str(value)
    return ' '.join(re.sub(r'<[^>]*>',' ',html.unescape(str(value or ''))).split())

def search(number, term):
    if number not in BASE: raise ValueError('Unsupported LOC switch')
    if len(term)>250: raise ValueError('Please use 250 or fewer characters')
    # at=results avoids transferring a large set of collection facets.
    params={'fo':'json','at':'results','q':term,'c':'25','sp':'1'}
    url=BASE[number]+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={
        'User-Agent':'DEADBYTE/3.7 (public library research; no API key)',
        'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=9) as resp:
            raw=resp.read(2_000_001)
        if len(raw)>2_000_000:
            raise ValueError('LOC response exceeds 2 MB; narrow the search')
        data=json.loads(raw.decode('utf-8'))
        rows=data.get('results',[]) if isinstance(data,dict) else []
        if not isinstance(rows,list): raise ValueError('LOC results not a list')
        out=[]
        for x in rows:
            if not isinstance(x,dict): continue
            link=x.get('id') or x.get('url') or x.get('link') or ''
            if not isinstance(link,str): link=''
            if not link.startswith('https://www.loc.gov/') and not link.startswith('https://loc.gov/'):
                continue
            out.append({'title':_txt(x.get('title')) or '(Untitled LOC record)',
                        'url':link,'description':_txt(x.get('description')),
                        'date':_txt(x.get('date'))})
        return out
    except Exception as exc:
        public=BASE[number]+'?'+urllib.parse.urlencode({'q':term})
        raise RuntimeError(type(exc).__name__+': '+str(exc)[:130]+
          ' | LOC website search (manual): '+public) from exc
