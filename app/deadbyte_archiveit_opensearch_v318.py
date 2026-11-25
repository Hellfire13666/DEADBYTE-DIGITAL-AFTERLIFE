"""Archive-It public OpenSearch keyword discovery, not generic website scraping."""
import html
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://archive-it.org/search-master/opensearch'
LIMIT = 25
MAX_RESPONSE = 1_500_000

def _plain(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', str(s or ''))).split())

def parse_feed(data):
    root=ET.fromstring(data)
    if root.tag!='rss' and not root.tag.endswith('}rss'):
        raise ValueError('Unexpected OpenSearch XML root')
    channel=root.find('channel')
    if channel is None:raise ValueError('Missing OpenSearch channel')
    ns='{https://web.archive.org/-/spec/opensearchrss/1.0/}'
    rows=[]
    for item in channel.findall('item'):
        title=_plain(item.findtext('title','Untitled archived page'))[:240]
        original=(item.findtext('link') or '').strip()
        dt=(item.findtext('date') or '').strip()
        coll=(item.findtext(ns+'collection') or '').strip()
        description=_plain(item.findtext('description',''))[:700]
        # Only attach source links returned by Archive-It; do not invent captures.
        if not original.startswith(('https://','http://')):continue
        archive_link=''
        if coll.isdigit() and re.fullmatch(r'\d{14}',dt):
            archive_link='https://wayback.archive-it.org/'+coll+'/'+dt+'/'+original
        rows.append({
            'title':'Archive-It archived web page // '+title,
            'url':archive_link or original,
            'description':('ARCHIVED WEB PAGE METADATA; CAPTURE AVAILABILITY NOT VERIFIED. '
                           +('ORIGINAL URL // '+original+' | ') + description),
            'date':dt,
            'source':'Archive-It OpenSearch public index',
            'collection':coll,
            'original_url':original,
            'capture_link':archive_link,
            'record_type':'archived web page search hit',
        })
    return rows

def search(term):
    if not isinstance(term,str) or not term.strip():raise ValueError('Enter an Archive-It keyword')
    term=term.strip()
    if len(term)>180:raise ValueError('Search phrase too long (180 chars max)')
    params={'q':term,'n':str(LIMIT),'p':'0'}
    url=BASE+'?'+urllib.parse.urlencode(params)
    request=urllib.request.Request(url,headers={
        'User-Agent':'DEADBYTE-Research/3.18 (public archive OpenSearch; keyless)',
        'Accept':'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.5'})
    try:
        with urllib.request.urlopen(request,timeout=12) as r:
            data=r.read(MAX_RESPONSE+1)
        if len(data)>MAX_RESPONSE:raise ValueError('Archive-It response too large')
        rows=parse_feed(data)
        if rows:return rows
        raise ValueError('Archive-It returned no indexed web pages on first page')
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError,ET.ParseError) as exc:
        # Distinguish no results/provider errors from actual returned records.
        raise RuntimeError('Archive-It OpenSearch '+type(exc).__name__+': '+str(exc)[:160]
                           +' | PUBLIC SEARCH // '+url) from exc
