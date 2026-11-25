"""Keyless newspaper adapter: LOC and California Digital Newspaper Collection.

CDNC exposes a searchable public website, not a guaranteed public JSON API.
Only actual article links present in search HTML can become result records.
"""
import html
from html.parser import HTMLParser
import re
import urllib.error
import urllib.parse
import urllib.request

LOC = 'https://www.loc.gov/collections/chronicling-america/'
CDNC = 'https://cdnc.ucr.edu/'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; DEADBYTE-public-archive-research/3.8)',
           'Accept': 'text/html,application/json;q=0.9,*/*;q=0.5'}

def _url(base,params):
    return base+'?'+urllib.parse.urlencode(params)

def public_links(term):
    return (_url(LOC, {'q':term}),
            _url(CDNC, {'a':'q','r':'1','results':'1','txf':'txIN','txq':term}))

def _download(url,timeout,size=1_500_000):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        status=getattr(resp,'status',200)
        if status != 200:
            raise ValueError('HTTP '+str(status))
        content=resp.read(size+1)
        charset=resp.headers.get_content_charset() or 'utf-8'
    if len(content)>size:
        raise ValueError('Response too large for safe parsing')
    return content.decode(charset,'replace')

def _loc(term):
    import json
    url=_url(LOC,{'fo':'json','at':'results','q':term,'c':'20','sp':'1'})
    payload=json.loads(_download(url,5,1_800_000))
    if not isinstance(payload,dict) or not isinstance(payload.get('results'),list):
        raise ValueError('Unexpected LOC response format')
    out=[]
    for item in payload['results']:
        if not isinstance(item,dict):continue
        link=item.get('id') or item.get('url') or ''
        if not isinstance(link,str) or not link.startswith(('https://www.loc.gov/','https://loc.gov/')):
            continue
        desc=item.get('description') or ''
        if isinstance(desc,list):desc='; '.join(map(str,desc[:3]))
        date=item.get('date') or ''
        out.append({'title':'LOC // '+str(item.get('title') or 'Newspaper record'),
                    'url':link,'description':str(desc),'date':str(date)})
    return out

class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[];self._href=None;self._parts=[]
    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        href=dict(attrs).get('href','')
        full=urllib.parse.urljoin(CDNC,href)
        parsed=urllib.parse.urlsplit(full)
        query=urllib.parse.parse_qs(parsed.query)
        if parsed.hostname in ('cdnc.ucr.edu','www.cdnc.ucr.edu') and (query.get('a')==['d'] or '/article/' in parsed.path):
            self._href=full;self._parts=[]
    def handle_data(self,data):
        if self._href:self._parts.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self._href:
            title=' '.join(''.join(self._parts).split())
            if len(title)>5:
                self.links.append((title,self._href))
            self._href=None;self._parts=[]

def _cdnc(term):
    search_url=public_links(term)[1]
    page=_download(search_url,10,2_500_000)
    # Never turn a search page or unrelated navigation into a fabricated article result.
    if 'captcha' in page.lower() or 'cf-chl-' in page.lower():
        raise ValueError('Automated CDNC access requires an interactive browser')
    parser=ArticleParser();parser.feed(page)
    out=[];seen=set()
    for title,link in parser.links:
        if link in seen:continue
        seen.add(link)
        out.append({'title':'CDNC // '+title[:220], 'url':link,
                    'description':'Historical newspaper article; open original for OCR and date. Source: California Digital Newspaper Collection.',
                    'date':''})
        if len(out)>=40:break
    if not out:
        raise ValueError('CDNC responded, but no individual article links were verified')
    return out

# DEADBYTE_NEWSPAPER_RECOVERY_V3_9

def _ia_newspaper_catalog(term):
    """Return verified IA item metadata from designated newspaper collections.

    An IA item is a digitized item/issue, NOT a verified individual newspaper article.
    """
    import json as _json
    words = re.findall(r"[\w'-]+", term.lower())
    noise = {'the','a','an','about','of','in','on','at','for','and','or','newspaper',
             'newspapers','historical','historic','reports','report','articles',
             'article','from','during','tell','me','find'}
    focus = [w for w in words if len(w) > 2 and w not in noise]
    if not focus:
        raise ValueError('No useful newspaper query words')
    # The user question stays intact for display; only search syntax is normalized.
    topic = ' AND '.join('"' + w.replace('"', '') + '"' for w in focus[:5])
    col = '(collection:newspapers OR collection:usnewspapers)'
    queries = [col + ' AND (' + topic + ')']
    if len(focus) > 2:
        queries.append(col + ' AND (' + ' AND '.join('"'+w+'"' for w in focus[:2]) + ')')
    errors=[]
    for q in queries:
        params = [('q', q),('fl[]','identifier'),('fl[]','title'),
                  ('fl[]','date'),('fl[]','year'),('fl[]','description'),
                  ('fl[]','collection'),('rows','40'),('page','1'),('output','json')]
        url = 'https://archive.org/advancedsearch.php?' + urllib.parse.urlencode(params)
        try:
            data=_json.loads(_download(url, 10, 2_000_000))
            docs=data.get('response',{}).get('docs',[])
            if not isinstance(docs,list): raise ValueError('Unexpected IA response')
            out=[]
            for d in docs:
                if not isinstance(d,dict): continue
                identifier=d.get('identifier')
                if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{2,180}', identifier):continue
                title=d.get('title') or identifier
                if isinstance(title,list): title='; '.join(map(str,title[:2]))
                description=d.get('description') or ''
                if isinstance(description,list): description='; '.join(map(str,description[:2]))
                date=d.get('date') or d.get('year') or ''
                if isinstance(date,list): date=date[0] if date else ''
                out.append({'title':'Internet Archive newspaper item // '+str(title)[:210],
                            'url':'https://archive.org/details/'+identifier,
                            'description':'DIGITIZED ITEM/ISSUE, NOT A VERIFIED ARTICLE. '+str(description)[:550],
                            'date':str(date),
                            'source':'Internet Archive / newspaper collection',
                            'record_type':'newspaper item metadata'})
            if out:return out
            errors.append('IA returned no newspaper collection items for query')
        except Exception as exc:
            errors.append('Internet Archive '+type(exc).__name__+': '+str(exc)[:130])
    raise ValueError(' | '.join(errors))

def _db310_original_search(term):
    if not isinstance(term,str) or not term.strip():
        raise ValueError('Enter a newspaper search phrase')
    if len(term)>250: raise ValueError('Limit your search to 250 characters')
    term=term.strip()
    errors=[]
    # Prefer the independently accessible public archive index. Don't hammer sources
    # already proven unreachable if matching newspaper issues were actually found.
    for label,func in [('Internet Archive newspaper index',_ia_newspaper_catalog),
                       ('Library of Congress',_loc),('California Digital Newspaper Collection',_cdnc)]:
        try:
            items=func(term)
            if items:return items
            errors.append(label+' returned no matching records')
        except Exception as exc:
            errors.append(label+' '+type(exc).__name__+': '+str(exc)[:180])
    loc_url,cdnc_url=public_links(term)
    ia_url='https://archive.org/search?'+urllib.parse.urlencode({'query':'collection:newspapers '+term})
    raise RuntimeError(' | '.join(errors)+
       ' | MANUAL PUBLIC SEARCHES: IA '+ia_url+' ; LOC '+loc_url+' ; CDNC '+cdnc_url)

# DEADBYTE_NEWSPAPER_REFINERY_V3_10

def _db310_relevance(item, term):
    """Score source-provided metadata, not presumed contents of an issue."""
    import re as _re
    words = _re.findall(r"[a-z0-9]+", term.casefold())
    stop = {'the','a','an','about','of','in','on','at','for','and','or',
            'historical','historic','newspaper','newspapers','report','reports',
            'articles','article','find','show','me','from','during','tell'}
    topic = list(dict.fromkeys(w for w in words if len(w) >= 3 and w not in stop
                                  and not (len(w) == 4 and w.isdigit())))
    years = list(dict.fromkeys(w for w in words if len(w) == 4 and
                                   w.isdigit() and 1600 <= int(w) <= 2100))
    title = str(item.get('title') or '').casefold()
    desc = str(item.get('description') or '').casefold()
    # Dates from providers are metadata, not proof of a specific article date.
    date = str(item.get('date') or '')
    title_words = set(_re.findall(r'[a-z0-9]+', title))
    desc_words = set(_re.findall(r'[a-z0-9]+', desc))
    tm = sum(w in title_words for w in topic)
    dm = sum(w in desc_words for w in topic)
    score = 6 * tm + 2 * dm
    if topic and tm == len(topic):score += 10
    if topic and dm == len(topic):score += 5
    off_year = bool(years and _re.match(r'\d{4}', date) and
                    date[:4] not in years)
    same_year = bool(years and _re.match(r'\d{4}', date) and date[:4] in years)
    if same_year:score += 9
    if off_year:score -= 25
    if off_year:label = 'DATE OUTSIDE REQUESTED YEAR'
    elif topic and (tm == len(topic) or dm == len(topic)) and same_year:
        label = 'STRONG METADATA MATCH'
    elif topic and (tm == len(topic) or dm == len(topic)):
        label = 'TOPIC MATCH IN METADATA'
    elif (tm + dm):label = 'PARTIAL METADATA MATCH'
    else:label = 'WEAK METADATA MATCH'
    return score, label

def search(term):
    """Return ALL original records, sorted by source-metadata relevance."""
    original = _db310_original_search(term)
    if not isinstance(original, list):return original
    decorated = []
    for index, source_item in enumerate(original):
        if not isinstance(source_item, dict):
            decorated.append((float('-inf'), index, source_item))
            continue
        score, label = _db310_relevance(source_item, term)
        item = source_item.copy()
        item['relevance_label'] = label
        item['relevance_score'] = score
        item['description'] = ('RELEVANCE // '+label+'. '+str(item.get('description') or ''))
        decorated.append((score, index, item))
    decorated.sort(key=lambda x: (-x[0], x[1]))
    return [item for _, _, item in decorated]
