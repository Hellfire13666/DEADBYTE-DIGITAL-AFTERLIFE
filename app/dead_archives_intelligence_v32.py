"""DEADBYTE // DEAD ARCHIVES v3.3. Historical, evidence-first research.
Only public archive metadata and IEM's republished NWS Local Storm Reports.
No changes to main launcher/UI. Standard-library Python.
"""
import concurrent.futures
import csv
import datetime as dt
import html
import io
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

VERSION = '3.4'
ROOT = Path.home() / '.local/share/deadbyte'
STATES = dict(zip(
    ('alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota mississippi missouri montana nebraska nevada new hampshire new jersey new mexico new york north carolina north dakota ohio oklahoma oregon pennsylvania rhode island south carolina south dakota tennessee texas utah vermont virginia washington west virginia wisconsin wyoming').split('|' ) if False else [
    'alabama','alaska','arizona','arkansas','california','colorado','connecticut','delaware','florida','georgia','hawaii','idaho','illinois','indiana','iowa','kansas','kentucky','louisiana','maine','maryland','massachusetts','michigan','minnesota','mississippi','missouri','montana','nebraska','nevada','new hampshire','new jersey','new mexico','new york','north carolina','north dakota','ohio','oklahoma','oregon','pennsylvania','rhode island','south carolina','south dakota','tennessee','texas','utah','vermont','virginia','washington','west virginia','wisconsin','wyoming'],
    'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split()
))
WEATHER = {'tornado': ('tornado','funnel','waterspout'), 'hurricane': ('hurricane','tropical storm'),
           'flood': ('flood','flash flood'), 'hail': ('hail',), 'wind': ('wind','thunderstorm wind','damaging wind'),
           'storm': ('storm','thunderstorm','tornado','hurricane','flood','wind','hail'),
           'wildfire': ('wildfire','fire')}
STOP = {'the','a','an','of','in','on','at','for','with','from','and','or','about','show','find','give','me','during','reports','report','records','record','archive','archived','historical','history','damage','damages','involving','was','were','what','which','please','search','information','by','that','this','when','where','how','closest','nearest','nearby','latest'}


def plain(s):
    if isinstance(s,list):
        s='; '.join(map(str,s[:5]))
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', str(s or ''))).split())


def tokens(s):
    return re.findall(r'[a-z0-9]+',s.casefold())


def parse_question(question):
    q=question.casefold()
    years=re.findall(r'\b(?:19|20)\d\d\b',q)
    year=int(years[0]) if years else None
    state=next(((name,code) for name,code in sorted(STATES.items(),key=lambda x:-len(x[0])) if re.search(r'\b'+re.escape(name)+r'\b',q)),None)
    if not state:
        state=next(((name,code) for name,code in STATES.items() if re.search(r'\b'+code.casefold()+r'\b',q)),None)
    category=next((k for k in ('tornado','hurricane','flood','hail','wildfire','wind','storm') if re.search(r'\b'+k+r'(?:es|s)?\b',q)),None)
    words=[w for w in tokens(question) if w not in STOP and len(w)>2 and not w.isdigit()]
    essential=[category] if category else []
    if state: essential.append(state[0])
    if year: essential.append(str(year))
    primary=' '.join(dict.fromkeys(essential + words[:4]))
    fallback=' '.join(dict.fromkeys(essential[:-1] if year else essential))
    # Catalogs are different: books, manuscripts, newspapers, and URL captures are not interchangeable.
    is_url=bool(re.search(r'https?://\S+|\b[a-z0-9-]+\.(?:com|org|net|edu|gov)\b',q))
    book=bool(re.search(r'\b(book|books|novel|novels|author|authors|ebook|ebooks|literature|poem|poetry|manuscript|manuscripts)\b',q))
    press=bool(re.search(r'\b(newspaper|newspapers|press|headline|headlines|clipping|clippings|article|articles)\b',q))
    culture=bool(re.search(r'\b(art|painting|paintings|museum|museums|photograph|photographs|heritage|artifact|artifacts)\b',q))
    intent=('weather' if category else 'web-capture' if is_url else 'newspaper' if press else
            'books' if book else 'heritage' if culture else 'general')
    return {'year':year,'state':state,'category':category,'primary':primary or question,
            'fallback':fallback or ' '.join(words[:4]),'words':words,'intent':intent} 


def fetch_csv(url, timeout=10, max_bytes=6500000):
    request=Request(url,headers={'User-Agent':'DEADBYTE-ArchiveResearch/3.3 (public records)','Accept':'text/csv'})
    with urlopen(request,timeout=timeout) as response:
        data=response.read(max_bytes+1)
        if len(data)>max_bytes:
            raise ValueError('Report exceeds 6.5 MB safety limit; use a narrower date range')
    content=data.decode('utf-8-sig',errors='replace')
    if '<html' in content[:250].lower():
        raise ValueError('Provider returned HTML instead of CSV')
    return list(csv.DictReader(io.StringIO(content)))


def quarters(year):
    for month in (1,4,7,10):
        start=dt.datetime(year,month,1,tzinfo=dt.timezone.utc)
        end=dt.datetime(year+1,1,1,tzinfo=dt.timezone.utc) if month==10 else dt.datetime(year,month+3,1,tzinfo=dt.timezone.utc)
        yield start,end


def iem_chunk(year,state,category,start,end):
    params={'state':state,'sts':start.strftime('%Y-%m-%dT%H:%MZ'),'ets':end.strftime('%Y-%m-%dT%H:%MZ'),'fmt':'csv'}
    url='https://mesonet.agron.iastate.edu/cgi-bin/request/gis/lsr.py?'+urlencode(params)
    data=fetch_csv(url)
    matches=[]
    for row in data:
        r={str(k).upper():v for k,v in row.items() if k}
        event_type=plain(r.get('TYPETEXT',''))
        remark=plain(r.get('REMARK',''))
        combined=(event_type+' '+remark).casefold()
        if category:
            acceptable=WEATHER[category]
            if not any(term in combined for term in acceptable):
                continue
        date=plain(r.get('VALID',''))
        if not date.startswith(str(year)):
            continue
        location=', '.join(filter(None,[plain(r.get('CITY','')),plain(r.get('COUNTY','')),state]))
        title=f'{event_type or "Local Storm Report"} // {location}'
        description=f'{remark}. Reporting source: {plain(r.get("SOURCE",""))}. Office: {plain(r.get("WFO",""))}.'
        matches.append({'source':'NWS Local Storm Reports via Iowa Mesonet','title':title,'url':url,
                        'date':format_event_utc(date),'description':description,'event_date':date,'event_date_utc':format_event_utc(date),
                        'event_type':event_type,'state':state,'tier':'EVENT REPORT',
                        'verification':'Archived local storm report, not a final certified storm-event record',
                        'latitude':r.get('LAT',''),'longitude':r.get('LON','')})
    return matches,len(data)


def bounded(fn,timeout=11):
    result={}
    def worker():
        try:result['rows']=fn()
        except Exception as exc:result['error']=f'{type(exc).__name__}: {exc}'
    thread=threading.Thread(target=worker,daemon=True)
    thread.start();thread.join(timeout)
    if thread.is_alive():return None,f'TIMEOUT after {timeout}s'
    if 'error' in result:return None,result['error']
    return result.get('rows'),None


def catalog(source_id,search_function,query):
    values=search_function(source_id,query)
    if not isinstance(values,list):raise ValueError('Unexpected provider record format')
    rows=[]
    for item in values:
        if not isinstance(item,dict):continue
        u=plain(item.get('url',''))
        if urlparse(u).scheme not in ('http','https'):continue
        rows.append({'source':{1:'Internet Archive',2:'Open Library',3:'Library of Congress',4:'Wikisource',5:'Project Gutenberg',6:'Historical Newspapers / LOC'}.get(source_id,'Archive'),
                     'title':plain(item.get('title','')),'url':u,
                     'date':plain(item.get('date','')),'description':plain(item.get('description',''))})
    return rows


def classify(item,info):
    title=plain(item.get('title','')).casefold();desc=plain(item.get('description','')).casefold();date=plain(item.get('date',''))
    full=title+' '+desc
    category=info['category'];state=info['state'];year=info['year']
    if item.get('tier')=='EVENT REPORT':return 'EVENT REPORT',100
    if not category:
        important=[w for w in info['words'] if len(w)>3 and w not in ('book','books','newspaper','newspapers','article','articles','author','authors','year')]
        if not important:important=[w for w in info['words'] if len(w)>2]
        in_title=sum(1 for w in important if re.search(r'\b'+re.escape(w)+r'\b',title))
        in_desc=sum(1 for w in important if re.search(r'\b'+re.escape(w)+r'\b',desc))
        topic_score=in_title*6+in_desc*2
        if important and not (in_title or in_desc):return 'WEAK / UNRELATED',0
        if state and state[0] not in full and not re.search(r'\b'+re.escape(state[1].casefold())+r'\b',full):
            return 'WEAK / UNRELATED',topic_score
        if year and str(year) not in date[:10]:return 'RELATED / DATE UNVERIFIED',topic_score
        return 'RELATED ARCHIVE',topic_score+10
    subject=bool(category and any(t in full for t in WEATHER[category])) if category else True
    place=bool(state and (state[0] in full or re.search(r'\b'+re.escape(state[1].casefold())+r'\b',full))) if state else True
    # This date may be an upload/publication date, never certify it as an event date.
    date_match=bool(year and str(year) in date[:10]) if year else True
    title_hits=sum(1 for w in info['words'] if len(w)>3 and w in title)
    score=8*int(subject)+8*int(place)+3*int(date_match)+2*title_hits
    if category and not subject:return 'WEAK / UNRELATED',score
    if state and not place:return 'WEAK / UNRELATED',score
    if year and not date_match:return 'RELATED / DATE UNVERIFIED',score
    return 'RELATED ARCHIVE',score


def format_event_utc(raw):
    """Convert IEM/NWS VALID (UTC) without guessing local timezone."""
    s=plain(raw)
    for fmt in ('%Y%m%d%H%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'):
        try:return dt.datetime.strptime(s,fmt).strftime('%b %d, %Y · %H:%M UTC')
        except ValueError:pass
    return s or 'Date unknown'


def parse_event_time(raw):
    try:return dt.datetime.strptime(plain(raw),'%Y%m%d%H%M')
    except ValueError:return None


def event_rank(item):
    """Prefer a correction and substantive NWS survey while retaining other observations."""
    details=plain(item.get('description','')).casefold()
    return (int('corrects previous' in details),
            int('nws storm survey' in details or 'nws damage survey' in details),
            len(details))


def group_near_duplicate_reports(records):
    """Group likely repeat reports, not tornado tracks or independent incidents.

    Same type + same county + same locality + within 30 minutes of the
    representative. Keeps all full original entries as nested observations.
    Other locations along one tornado path remain distinct report locations.
    """
    groups=[]
    for item in records:
        if item.get('tier') != 'EVENT REPORT':
            groups.append({'primary':item,'members':[item]})
            continue
        category=plain(item.get('event_type','')).casefold()
        title=plain(item.get('title','')).casefold()
        locality=title.split('//',1)[-1].strip()
        # Only collapse identical named location, county, event type, and close UTC time.
        when=parse_event_time(item.get('event_date',''))
        found=None
        if when and locality and category:
            for g in groups:
                base=g['primary']
                if base.get('tier')!='EVENT REPORT':continue
                if plain(base.get('event_type','')).casefold()!=category:continue
                if plain(base.get('title','')).casefold().split('//',1)[-1].strip()!=locality:continue
                other=parse_event_time(base.get('event_date',''))
                if other and abs((when-other).total_seconds())<=30*60:
                    found=g;break
        if found is None:groups.append({'primary':item,'members':[item]})
        else:
            found['members'].append(item)
            if event_rank(item)>event_rank(found['primary']):found['primary']=item
    result=[]
    for group in groups:
        main=dict(group['primary'])
        members=group['members']
        if len(members)>1:
            main['report_count']=len(members)
            main['additional_reports']=[dict(r) for r in members if r is not group['primary']]
        else:main['report_count']=1
        result.append(main)
    return result


def persist(question,info,records,errors,counts,skipped):
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    payload={'source':'DEAD ARCHIVES // RESEARCH REFINERY v3.4', 'question':question,
             'interpretation':{'year':info['year'],'state':info['state'],'category':info['category']},
             'searched_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
             'scope':'Source-specific catalog metadata plus IEM-redistributed NWS Local Storm Reports; neither guarantees completeness or event verification.',
             'provider_counts':counts,'provider_errors':errors,'provider_skipped':skipped,'records':records}
    p=ROOT/(stamp+'.json');t=ROOT/(stamp+'.txt')
    with p.open('x',encoding='utf-8') as out:json.dump(payload,out,ensure_ascii=False,indent=2)
    with t.open('x',encoding='utf-8') as out:
        out.write('DEADBYTE // RESEARCH REFINERY v3.4\nQUESTION: '+question+'\n\n')
        for idx,item in enumerate(records,1):
            out.write(f'[{idx:03d}] [{item["tier"]}] {item["title"]}\nSOURCE: {item["source"]}\nDATE: {item["date"]}\nURL: {item["url"]}\nREPORTS GROUPED: {item.get("report_count",1)}\nDETAILS: {item["description"]}\n\n')
        out.write('PROVIDERS: '+json.dumps(counts,ensure_ascii=False)+'\nERRORS: '+json.dumps(errors,ensure_ascii=False)+'\nSKIPPED: '+json.dumps(skipped,ensure_ascii=False)+'\n')
    return p,t


def run(search_function,archive_module_path):
    try: question=input('☠ DEAD ARCHIVES // ASK A FULL QUESTION > ').strip()
    except (EOFError,KeyboardInterrupt): print('\nCANCELLED');return
    if not question:return print('EMPTY QUERY')
    if len(question)>400:return print('QUESTION TOO LONG (400 CHARACTERS MAX)')
    info=parse_question(question)
    # DEADBYTE_HISTORICAL_WEATHER_V3_11
    if (info.get('intent') == 'weather' and info.get('year') is not None
            and 1950 <= info['year'] <= 2006):
        import importlib.util
        spec = importlib.util.spec_from_file_location('deadbyte_noaa_historical_v311', ROOT / 'deadbyte_noaa_historical_v311.py')
        weather_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(weather_module)
        weather_module.run_noaa_historical(question, info, ROOT)
        return
    print('\n☣ QUESTION //',question)
    print('⛓ TOPIC //',info['primary'])
    print('⚑ EVENT TYPE //',info['category'] or 'GENERAL ARCHIVE')
    print('⚑ PLACE //',info['state'][0] if info['state'] else 'NOT GIVEN')
    print('⚑ YEAR //',info['year'] or 'NOT GIVEN')
    print('⚑ RESEARCH LANE //',info['intent'].upper())
    print('SCOPE // Archive metadata is not proof of an event or an event date.')
    errors={};counts={};skipped={};items=[]
    now=dt.datetime.now(dt.timezone.utc).year
    weather=bool(info['category'] and info['category']!='wildfire')
    if weather and info['year'] and info['state'] and 2007<=info['year']<=now:
        name='NWS Local Storm Reports via Iowa Mesonet'
        print('\n☣ NWS STORM REPORT ARCHIVE // 4 quarterly queries',flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures={pool.submit(bounded,lambda a=a,b=b:iem_chunk(info['year'],info['state'][1],info['category'],a,b),12):(a,b) for a,b in quarters(info['year'])}
            for future in concurrent.futures.as_completed(futures):
                a,b=futures[future]
                response,error=future.result()
                if error:
                    errors[f'{name} {a.date()}'] = error
                    print(f'  {a.strftime("%b")}-{(b-dt.timedelta(days=1)).strftime("%b")}: {error}')
                else:
                    records,seen=response
                    print(f'  {a.strftime("%b")}-{(b-dt.timedelta(days=1)).strftime("%b")}: {len(records)} matching / {seen} total reports')
                    items.extend(records)
                    counts[name]=counts.get(name,0)+len(records)
        print('NOTE // Mesonet archive is incomplete; these are reported incidents, not certified totals.')
    elif weather:
        skipped['NWS Local Storm Reports']='Specify US state and year (2007-present) for historical report retrieval.'
    # Archive search is deliberately supportive, not a replacement for dated storm-event records.
    # Source-aware routing. Only use existing proven search adapters; do not fabricate new live APIs.
    profiles={1:'Internet Archive: mixed-media archive (books, audio, video, reports, websites)',
              2:'Open Library: books, authors, editions and bibliographic metadata',
              4:'Wikisource: transcribed public-domain texts and documents',
              5:'Gutendex: Project Gutenberg ebook titles, authors, subjects'}
    lane=info['intent']
    ids=([1] if lane=='weather' else [2,5,1,4] if lane=='books' else
         [1,4] if lane=='newspaper' else [1,4] if lane=='heritage' else
         [1] if lane=='web-capture' else [1,4,2,5])
    print('☣ PROVIDER ROUTE // '+ ' + '.join({1:'Internet Archive',2:'Open Library',4:'Wikisource',5:'Gutendex'}[i] for i in ids))
    for i in ids:print('  SOURCE ROLE //',profiles[i])
    skipped['Library of Congress / Chronicling America / Archive-It']='Previously timed out in Switch 14; no claim of live availability. Individual switches remain unchanged.'
    skipped['Wayback / Common Crawl']='URL capture indexes, not general sentence/full-text search; use their individual switches for URL history.'
    skipped['Europeana']='European cultural heritage catalog; requires configured API key.'
    if weather:skipped['Book collections']='Not useful as primary sources for dated weather incidents.'
    else:skipped['NWS Local Storm Reports']='Only queried for US-state + year + weather-event questions.'
    if lane=='newspaper' and info['year'] and info['year']>=2000:
        print('PERIOD NOTE // Chronicling America is a historical newspaper collection, not comprehensive contemporary news.')
    def archive_query(i):
        q=info['primary']
        res,err=bounded(lambda:catalog(i,search_function,q),9)
        if not err and not res and info['fallback'] and info['fallback']!=q:
            res,err=bounded(lambda:catalog(i,search_function,info['fallback']),9)
        return res,err
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ids)) as pool:
        futures={pool.submit(archive_query,i):i for i in ids}
        for future in concurrent.futures.as_completed(futures):
            i=futures[future];name={1:'Internet Archive',2:'Open Library',4:'Wikisource',5:'Project Gutenberg'}[i]
            res,err=future.result()
            if err:
                errors[name]=err
                print(f'  {name}: {err}')
            else:
                counts[name]=len(res)
                items.extend(res)
                print(f'  {name}: {len(res)} metadata matches (unverified)')
    unique={}
    for item in items:
        key=(item['source'],item.get('date',''),item['title']) if item.get('tier')=='EVENT REPORT' else item['url'].lower().rstrip('/')
        tier,score=classify(item,info)
        item['tier']=tier;item['relevance_score']=score
        if key not in unique or score>unique[key]['relevance_score']:unique[key]=item
    raw_event_reports=sum(1 for x in unique.values() if x.get('tier')=='EVENT REPORT')
    records_grouped=group_near_duplicate_reports(list(unique.values()))
    order={'EVENT REPORT':0,'RELATED ARCHIVE':1,'RELATED / DATE UNVERIFIED':2,'WEAK / UNRELATED':3}
    records=sorted(records_grouped,key=lambda r:(order.get(r['tier'],4),-r['relevance_score'],r.get('event_date','') or r.get('date','')))
    print('\n☠ DEAD ARCHIVES // RESEARCH REFINERY v3.4 RESULTS')
    by_tier={}
    for item in records:by_tier[item['tier']]=by_tier.get(item['tier'],0)+1
    if raw_event_reports:
        print(f'REPORT GROUPING // {raw_event_reports} local reports organized into {sum(1 for r in records if r.get("tier")=="EVENT REPORT")} location/time groups')
        print('NOTE // Groups are NOT counts of distinct tornadoes. Corrections and original reports remain saved.')
    print('QUALITY // '+' | '.join(f'{k}: {v}' for k,v in by_tier.items()) if records else 'NO MATCHES // no verified events returned')
    visible=[x for x in records if x['tier']!='WEAK / UNRELATED']
    print('☣ RESEARCH BRIEF //',len(visible),'relevant/related entries from',len(counts),'responding catalogs')
    if weather:
        event_count=sum(1 for x in visible if x['tier']=='EVENT REPORT')
        print('EVIDENCE //',event_count,'report location/time groups; NOT distinct storm totals')
        print('SCOPE // NWS local storm reports may be corrected, repeated or incomplete.')
    if not visible:print('NO TOPICAL MATCHES // Catalogs queried, but no relevant records verified.')
    import sys
    def show_entry(idx, expanded=False):
        item=visible[idx]
        print(f'\n[{idx+1:03}] [{item["tier"]}] {item["title"]}')
        print('SOURCE //',item['source'])
        print('LINK //',item['url'])
        print('DATE //',item['date'] or 'Unknown')
        if item.get('report_count',1)>1:print('GROUPED REPORTS //',item['report_count'],'observations (complete records in JSON vault)')
        desc=item['description']
        limit=6500 if expanded else 450
        print('DETAILS //',desc if len(desc)<=limit else desc[:limit]+' … [enter result number for more]')
    if sys.stdin.isatty():
        shown=min(10,len(visible))
        for idx in range(shown):show_entry(idx)
        while visible:
            try:choice=input('\n☣ READER // [N]ext 10, [number] detail, [A]ll, [Q]uit > ').strip().lower()
            except (EOFError,KeyboardInterrupt):break
            if choice in ('q','quit','', '0'):break
            if choice in ('n','next'):
                if shown>=len(visible):print('END OF RESULTS');continue
                upto=min(shown+10,len(visible))
                for idx in range(shown,upto):show_entry(idx)
                shown=upto
            elif choice in ('a','all'):
                for idx in range(shown,len(visible)):show_entry(idx)
                shown=len(visible)
            elif choice.isdigit() and 1<=int(choice)<=len(visible):show_entry(int(choice)-1, expanded=True)
            else:print('ENTER N / A / NUMBER / Q')
    else:
        for idx in range(min(10,len(visible))):show_entry(idx)
        if len(visible)>10:print('READOUT // Showing first 10 in noninteractive mode; complete results are saved in DEAD VAULT.')
    if len(records)>len(visible):
        print(f'\nFILTERED // {len(records)-len(visible)} weak/unrelated records omitted from terminal; preserved in vault.')
    print(f'\nTOTAL // {len(records)} displayed source groups/records // {len(errors)} provider warnings')
    for k,v in skipped.items():print('SKIPPED //',k+':',v)
    for k,v in errors.items():print('PROVIDER ERROR //',k+':',v)
    try:
        j,t=persist(question,info,records,errors,counts,skipped)
        print('☣ DEAD VAULT // SAVED JSON',j.name)
        print('☣ DEAD VAULT // SAVED TXT ',t.name)
    except Exception as e:print('VAULT ERROR //',type(e).__name__,str(e))
