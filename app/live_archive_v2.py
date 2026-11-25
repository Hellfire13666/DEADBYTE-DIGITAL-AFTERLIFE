# DEADBYTE LIVE ARCHIVES 07-10 + SENTENCE 14 v2 (public provider APIs only)
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

VAULT = Path.home() / '.local/share/deadbyte'
UA = 'DEADBYTE/1.1 (public archive research; sequential requests)'
SOURCES = {7: 'Wayback Machine', 8: 'Common Crawl', 9: 'Archive-It', 10: 'Wikimedia Commons'}

def _fetch(url, params=None, fmt='json'):
    if params:
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json, application/xml, text/xml, text/plain'})
    with urllib.request.urlopen(req, timeout=22) as response:
        data = response.read(3000001)
    if len(data) > 3000000:
        raise ValueError('Provider response exceeded 3 MB; narrow search')
    text = data.decode('utf-8', errors='replace')
    if fmt == 'text': return text
    if fmt == 'xml': return ET.fromstring(text)
    return json.loads(text)

def _url_pattern(value):
    """Accept public domain/URL input; requests go only to provider endpoints."""
    raw = value.strip()
    if not raw or any(x.isspace() for x in raw) or len(raw) > 350:
        raise ValueError('Enter one public domain or URL without spaces')
    parts = urllib.parse.urlsplit(raw if '://' in raw else 'https://' + raw)
    domain = parts.hostname or ''
    if parts.scheme not in ('http','https') or not domain or '.' not in domain:
        raise ValueError('Enter a valid public domain or URL')
    if domain in ('localhost',) or domain.endswith(('.local','.internal','.test')):
        raise ValueError('Only public domains can be researched')
    # This string is passed to provider indexes, never fetched as a target URL.
    if parts.path in ('', '/') and not parts.query:
        return domain + '/*'
    return raw

def _rec(title, url, date='', description='', **extra):
    text = lambda x: re.sub(r'<[^>]+>', '', html.unescape(str(x or '')))
    item = {'title': text(title), 'url': str(url or ''), 'date': text(date), 'description': text(description)}
    item.update({k: str(v) for k,v in extra.items() if v is not None})
    return item

def _wayback(query, page):
    pattern = _url_pattern(query)
    # CDX list of lists: first row is column names.
    raw = _fetch('https://web.archive.org/cdx/search/cdx', {
        'url': pattern, 'output':'json', 'filter':'statuscode:200', 'limit':'100'})
    if not isinstance(raw,list) or len(raw)<2: return [], 'Provider returned no captures'
    header = raw[0]
    rows = []
    for values in raw[1:]:
        x = dict(zip(header, values)); stamp = x.get('timestamp',''); original = x.get('original','')
        rows.append(_rec(original, f'https://web.archive.org/web/{stamp}/{original}', stamp,
                         f"HTTP {x.get('statuscode','?')} | {x.get('mimetype','?')}", original=original))
    return rows, 'CDX first response; provider may limit records'

def _common(query, page):
    pattern = _url_pattern(query)
    indexes = _fetch('https://index.commoncrawl.org/collinfo.json')
    if not isinstance(indexes,list) or not indexes: raise ValueError('No Common Crawl index published')
    # Request only the most recent published index. Page parameter varies across indexes.
    base = indexes[0].get('cdx-api')
    if not base or not base.startswith('https://index.commoncrawl.org/'):
        raise ValueError('Index metadata did not include a valid Common Crawl API URL')
    try:
        data = _fetch(base, {'url':pattern,'output':'json','page':str(page-1)},'text')
    except urllib.error.HTTPError as e:
        if e.code==404: return [], 'No captures in the newest crawl index'
        raise
    rows=[]
    for line in data.splitlines():
        if not line.strip(): continue
        x=json.loads(line); original=x.get('url',''); stamp=x.get('timestamp','')
        rows.append(_rec(original, original, stamp,
                         f"Archived index: {indexes[0].get('id','?')} | HTTP {x.get('status','?')} | {x.get('mime','?')}",
                         archive_index=indexes[0].get('id',''), filename=x.get('filename',''),
                         offset=x.get('offset',''), length=x.get('length','')))
    return rows, 'Newest published Common Crawl index; source URL is original, not replay'

def _archiveit(query, page):
    root=_fetch('https://archive-it.org/search-master/opensearch',
                {'q':query, 'n':'30','p':str((page-1)*30)},'xml')
    rows=[]
    for item in root.findall('.//item'):
        def field(tag): return (item.findtext(tag) or '').strip()
        original=field('link'); stamp=field('date')
        coll=''; 
        for elem in item:
            if elem.tag.endswith('}collection'): coll=(elem.text or '').strip()
        replay = f'https://wayback.archive-it.org/{coll}/{stamp}/{original}' if coll and stamp and original else original
        rows.append(_rec(field('title') or original, replay, stamp, field('description'),
                         original=original, collection=coll))
    return rows, 'OpenSearch public results, 30 per page; provider displays at most 99'


def _commons(query, page):
    """Wikimedia Commons public file search, no API key."""
    data = _fetch('https://commons.wikimedia.org/w/api.php', {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': query,
        'gsrnamespace': '6',
        'gsrlimit': '20',
        'gsroffset': str((page-1)*20),
        'prop': 'imageinfo',
        'iiprop': 'url|timestamp|extmetadata',
        'iiextmetadatafilter': 'Artist|LicenseShortName|ImageDescription',
        'format': 'json',
        'formatversion': '2'
    })
    if 'error' in data:
        raise ValueError(str(data['error'].get('info', 'Provider error')))

    pages = data.get('query', {}).get('pages', [])
    rows = []

    def metadata(info, key):
        raw = info.get('extmetadata', {}).get(key, {})
        value = html.unescape(str(raw.get('value', '')))
        return re.sub(r'<[^>]+>', ' ', value).strip()

    for item in sorted(pages, key=lambda x: x.get('index', 999999)):
        title = item.get('title', '')
        info = (item.get('imageinfo') or [{}])[0]
        if not title or not info.get('url'):
            continue

        link = 'https://commons.wikimedia.org/wiki/' + (
            urllib.parse.quote(title.replace(' ', '_'), safe=':()')
        )
        uploaded = info.get('timestamp', '')
        description = metadata(info, 'ImageDescription')
        if not description:
            description = 'Description unavailable'
        if uploaded:
            description += ' | Uploaded: ' + uploaded
            description += ' (not the historical event date)'

        rows.append(_rec(
            title, link, '', description[:800],
            original=info['url'],
            creator=metadata(info, 'Artist'),
            license=metadata(info, 'LicenseShortName')
        ))

    return rows, (
        'Wikimedia Commons public media files; '
        'upload dates are not historical event dates'
    )

def _europeana(query, page):
    key=os.environ.get('EUROPEANA_API_KEY','').strip()
    if not key:
        raise ValueError('Europeana requires an API key. Set EUROPEANA_API_KEY in your terminal; no key has been stored.')
    d=_fetch('https://api.europeana.eu/record/v2/search.json',
             {'wskey':key, 'query':query,'rows':'30','start':str((page-1)*30+1)})
    rows=[]
    for x in d.get('items',[]):
        name=x.get('title',['Untitled']); name=name[0] if isinstance(name,list) and name else name
        url=x.get('guid',''); desc=x.get('dcDescription',['']); desc=desc[0] if isinstance(desc,list) and desc else desc
        date=x.get('year',['']); date=date[0] if isinstance(date,list) and date else date
        rows.append(_rec(name,url,date,desc,provider=x.get('dataProvider','')))
    return rows, f"Europeana search result page; provider total {d.get('totalResults','unknown')}"

SEARCH = {7: _wayback, 8: _common, 9: _archiveit, 10: _commons}

def run_live_archive(number):
    name = SOURCES[number]
    mode = 'PUBLIC DOMAIN OR URL' if number in (7,8) else 'PUBLIC RESEARCH KEYWORD'
    try:
        q = input(f'{name.upper()} // {mode} > ').strip()
        if not q: print('No query supplied'); return
        page_txt=(input('RESULT PAGE [1] > ').strip() or '1') if number != 7 else '1'
        page=int(page_txt)
        if page<1 or page>1000: raise ValueError('Page must be 1-1000')
        print(f'\nCONNECTING // {name} // page {page}')
        rows,note=SEARCH[number](q,page)
    except (KeyboardInterrupt,EOFError):
        print('Search cancelled'); return
    except Exception as exc:
        print(f'PROVIDER ERROR // {name} // {type(exc).__name__}: {exc}')
        return
    for i,item in enumerate(rows,1):
        print(f"\n[{i:03}] {item['title']}\n{item['url']}\n{item['date']} // {item['description'][:800]}")
        for k in ('original','collection','archive_index','creator','license'):
            if item.get(k): print(f'{k.upper()}: {item[k]}')
    print(f'\n{name} // {len(rows)} records // {note}')
    if rows:
        VAULT.mkdir(mode=0o700,parents=True,exist_ok=True)
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        path=VAULT/(stamp+'.json')
        payload={'source':name,'query':q,'page':page,'note':note,'records':rows}
        with path.open('x', encoding='utf-8') as f:
            json.dump(payload,f,ensure_ascii=False,indent=2)
        print(f'DEAD VAULT // SAVED {path.name}')
    else:
        print('NO RECORDS // nothing written to vault')
