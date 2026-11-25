"""Historical NOAA/NCEI Storm Events, 1950-2006, for DEADBYTE Switch 14.
Only actual NOAA bulk event rows are displayed. These are storm-event database
records, not verified counts of all US storms or certified records.
"""
import csv
import datetime as dt
import gzip
import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

INDEX = 'https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
DETAIL = 'https://www.ncei.noaa.gov/access/storm-events-database/'
FAMILIES = {'tornado': ('TORNADO',), 'hail': ('HAIL',), 'wind': ('THUNDERSTORM WIND',),
            'storm': ('TORNADO','HAIL','THUNDERSTORM WIND'),
            'hurricane': ('HURRICANE', 'TROPICAL STORM'),
            'flood': ('FLOOD','FLASH FLOOD'),
            'wildfire': ('WILDFIRE',)}

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.items=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a':
            addr=dict(attrs).get('href','')
            if isinstance(addr,str):self.items.append(addr)

def get_bytes(url, limit):
    req=Request(url,headers={'User-Agent':'DEADBYTE-Research/3.11 (public NOAA data)',
                             'Accept':'text/html,text/csv,application/gzip'})
    with urlopen(req,timeout=18) as resp:
        result=resp.read(limit+1)
    if len(result)>limit:raise ValueError('NOAA response above safe transfer size')
    return result

def choose_year_file(index_html,year):
    p=Links();p.feed(index_html)
    pattern=re.compile(r'^StormEvents_details-ftp_v[\d.]+_d'+str(year)+r'_c(\d{8})\.csv\.gz$')
    options=[]
    for address in p.items:
        name=address.split('/')[-1]
        m=pattern.match(name)
        if m:options.append((m.group(1),name))
    return sorted(options)[-1][1] if options else None

# DEADBYTE_WEATHER_CHRONICLE_V3_12
_MONTHS = {name: num for num, name in enumerate(
    ('JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'),1)}

def _chronological_key(stamp, year):
    """NOAA commonly formats dates as 01-AUG-80 00:45:00.
    Use known requested NOAA file year so 1950-1968 cannot turn into 2050-2068.
    Unknown formats sort last, without deleting their source records.
    """
    import re
    value = str(stamp or '').strip()
    match = re.match(r'^(\d{1,2})-([A-Za-z]{3})-\d{2,4}(?:\s+(\d{1,2}:\d{2}(?::\d{2})?))?', value)
    if match:
        day, month, clock = match.groups()
        mon = _MONTHS.get(month.upper())
        if mon:
            try:
                hour_parts = [int(x) for x in (clock or '00:00:00').split(':')]
                hour_parts += [0] * (3-len(hour_parts))
                return (0, dt.datetime(int(year),mon,int(day),*hour_parts).isoformat())
            except ValueError:
                pass
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d','%m/%d/%Y %H:%M:%S','%m/%d/%Y'):
        try:
            return (0,dt.datetime.strptime(value,fmt).isoformat())
        except ValueError:
            pass
    return (1,value)

# DEADBYTE_ELECTRIC_RAINBOW_WEATHER_V3_13
# Terminal-only ANSI styling; NO_COLOR=1 or a non-TTY disables escapes.
def _weather_color_enabled():
    import os, sys
    return (sys.stdout.isatty() and not os.environ.get('NO_COLOR')
            and os.environ.get('TERM', '') != 'dumb')


def _weather_ink(value, code):
    return ('\033[38;5;%dm%s\033[0m' % (code, value)
            if _weather_color_enabled() else str(value))


def _weather_bar(amount, maximum, width=28):
    # Preserve visibility of very small nonzero monthly counts.
    blocks = 0 if amount <= 0 else max(1, round(width * amount / max(1, maximum)))
    palette = (39, 45, 51, 48, 46, 129, 135, 201, 198, 93, 63, 33)
    if not _weather_color_enabled():
        return '█' * blocks
    return ''.join(_weather_ink('█', palette[i % len(palette)]) for i in range(blocks))


def _print_monthly_summary(records, year):
    labels = ('JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE',
              'JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER')
    buckets = [0] * 12
    unknown = 0
    for rec in records:
        key = _chronological_key(rec.get('date', ''), year)
        if key[0]:
            unknown += 1
        else:
            try:
                buckets[int(key[1][5:7]) - 1] += 1
            except (ValueError, IndexError):
                unknown += 1
    print('\n' + _weather_ink('☣ MONTHLY WEATHER INDEX // ' + str(year), 39))
    for i, (label, count) in enumerate(zip(labels, buckets)):
        label_ink = _weather_ink(f'{label:<11}', (51, 45, 39, 48, 46, 135,
                                                201, 198, 129, 93, 63, 33)[i])
        number_ink = _weather_ink(f'{count:>5,}', 51)
        print(f'{label_ink} // {number_ink}   {_weather_bar(count, max(buckets))}')
    print(_weather_ink('─' * 57, 63))
    print(_weather_ink('☣ TOTAL NOAA EVENT ROWS // ' + format(sum(buckets) + unknown, ','), 46))
    if unknown:
        print(_weather_ink('UNPARSED DATES // ' + str(unknown) + ' (records preserved)', 198))
    print('EVIDENCE // Event rows, not unique storm counts or certified totals.\n')

def rows_for_year(blob,year,info):
    # Prevent malformed gzip data from expanding beyond a reasonable size.
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as f:
        raw=f.read(35_000_001)
    if len(raw)>35_000_000:raise ValueError('NOAA decompressed file exceeds safety size')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig','replace')))
    if not {'BEGIN_YEARMONTH','EVENT_TYPE','STATE','EVENT_ID'}.issubset(reader.fieldnames or []):
        raise ValueError('NOAA record columns changed; stopped without substituting metadata')
    wanted=FAMILIES.get(info.get('category'),FAMILIES['storm'])
    state_name=(info.get('state') or ('',))[0].upper()
    records=[];all_year=0;selected=0
    for entry in reader:
        date=str(entry.get('BEGIN_YEARMONTH',''))
        if not date.startswith(str(year)):continue
        all_year+=1
        kind=(entry.get('EVENT_TYPE') or '').strip().upper()
        if not any(x in kind for x in wanted):continue
        if state_name and (entry.get('STATE') or '').upper()!=state_name:continue
        selected+=1
        eid=str(entry.get('EVENT_ID','')).strip()
        source=DETAIL+'?id='+eid if eid.isdigit() else DETAIL
        description=' '.join((entry.get('EPISODE_NARRATIVE','')+' '+entry.get('EVENT_NARRATIVE','')).split())
        place=', '.join(x for x in [entry.get('CZ_NAME',''),entry.get('STATE','')] if x)
        stamp=(entry.get('BEGIN_DATE_TIME') or date).strip()
        records.append({'source':'NOAA NCEI Storm Events Database',
          'title':kind+' // '+place, 'url':source, 'date':stamp,
          'event_date':stamp, 'event_type':kind,'state':entry.get('STATE',''),
          'county':entry.get('CZ_NAME',''),'event_id':eid,'episode_id':entry.get('EPISODE_ID',''),
          'description':description or 'NOAA storm event record (narrative unavailable)',
          'tier':'NOAA EVENT RECORD', 'verification':'Official NOAA database entry; not a certified report',
          'begin_date_time':entry.get('BEGIN_DATE_TIME',''),
          'end_date_time':entry.get('END_DATE_TIME',''),
          'injuries_direct':entry.get('INJURIES_DIRECT',''),
          'deaths_direct':entry.get('DEATHS_DIRECT',''),
          'damage_property':entry.get('DAMAGE_PROPERTY',''),
          'damage_crops':entry.get('DAMAGE_CROPS','')})
    records.sort(key=lambda r:(_chronological_key(r['date'],year),r['state'],r['event_id']))
    return records,all_year,selected

def persist(root,question,info,records,source_file,all_year,matched):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    payload={'source':'DEAD ARCHIVES // NOAA HISTORICAL WEATHER v3.11',
       'question':question,'searched_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
       'interpretation':{'year':info['year'],'state':info['state'],'category':info['category']},
       'scope':'1950-1995 standardized tornado, thunderstorm wind, and hail records only; incomplete historical weather coverage. Entries are not certified totals.',
       'provider_counts':{'NOAA NCEI Storm Events Database':matched},'provider_errors':{},
       'source_file':source_file,'year_rows':all_year,'records':records}
    j=root/(stamp+'.json');t=root/(stamp+'.txt')
    with j.open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2,ensure_ascii=False)
    with t.open('x',encoding='utf-8') as f:
        f.write('DEADBYTE // HISTORICAL WEATHER v3.11\nQUESTION: '+question+'\nSOURCE FILE: '+source_file+'\n\n')
        for n,r in enumerate(records,1):
            f.write('[%03d] %s\nDATE: %s\nLINK: %s\nDETAILS: %s\n\n'%(n,r['title'],r['date'],r['url'],r['description']))
    return j,t

def run_noaa_historical(question,info,root):
    year=info['year']; cat=info.get('category') or 'storm'
    print('\n☣ HISTORICAL WEATHER // NOAA NCEI STORM EVENTS',flush=True)
    print('QUESTION //',question)
    print('YEAR //',year,'| REGION //',(info.get('state') or ('UNITED STATES',))[0])
    if year<=1995:
        print('COVERAGE LIMIT // Pre-1996 standardized records mainly tornado, thunderstorm wind and hail.')
        print('NOT a census of every storm, flood, hurricane or winter weather event.')
    if cat in ('hurricane','flood','wildfire') and year<1996:
        print('NOT AVAILABLE // This historical NOAA structured dataset does not comprehensively cover '+cat+'.')
        print('SOURCE //',DETAIL)
        return
    print('CONNECTING // NOAA public yearly detail archive',flush=True)
    try:
        index=get_bytes(INDEX,3_000_000).decode('utf-8','replace')
        filename=choose_year_file(index,year)
        if not filename:raise ValueError('No NOAA details file listed for year '+str(year))
        url=urljoin(INDEX,filename)
        raw=get_bytes(url,25_000_000)
        records,total,matched=rows_for_year(raw,year,info)
    except Exception as exc:
        print('PROVIDER ERROR // NOAA',type(exc).__name__+':',str(exc))
        print('PUBLIC DATA FILE INDEX //',INDEX)
        print('No unrelated Internet Archive items will be substituted for storm events.')
        return
    print(_weather_ink('SOURCE //', 45),url)
    print(_weather_ink('NOAA YEAR RECORDS //',39),_weather_ink(format(total,','),51),'|',_weather_ink('MATCHING EVENT ROWS //',39),_weather_ink(format(matched,','),46))
    print('EVIDENCE // Database event rows, NOT counts of unique storms or certified totals.')
    print('ORDER // Chronological by NOAA event date (oldest first)')
    _print_monthly_summary(records,year)
    if not records:
        print('NO MATCHES // no entries matching the requested type and location in this yearly file.')
        return
    # DEADBYTE_STORM_FILTERS_V3_14
    # All filtering is done on a view. `records` stays untouched for vault saving.
    import sys
    view = list(records)
    shown = 0
    selected_detail = None  # DEADBYTE_EVIDENCE_NAVIGATOR_V3_16
    state_filter = ''
    type_filter = ''

    def _state_names():
        return sorted({str(r.get('state') or '').strip().upper() for r in records if r.get('state')})

    def _event_types():
        return sorted({str(r.get('event_type') or '').strip().upper() for r in records if r.get('event_type')})

    def _refresh():
        nonlocal view, shown, selected_detail
        selected_detail = None
        view = [r for r in records
                if (not state_filter or str(r.get('state','')).strip().upper() == state_filter)
                and (not type_filter or str(r.get('event_type','')).strip().upper() == type_filter)]
        shown = 0
        print(_weather_ink('☣ ACTIVE VIEW // ' + format(len(view), ',') +
                           ' of ' + format(len(records), ',') + ' NOAA rows', 46))
        print('STATE //', state_filter or 'ALL', '| EVENT TYPE //', type_filter or 'ALL')
        print('YEAR //',year,'(change year by starting a new Switch 14 search)')
        _next_page()

    def _display(i, detail=False):
        r = view[i]
        print('\n' + _weather_ink('[%03d] [NOAA EVENT RECORD]' % (i + 1), 39) +
              ' ' + _weather_ink(r['title'], 51))
        print(_weather_ink('DATE //', 135), r['date'], '|',
              _weather_ink('EVENT ID //', 135), r['event_id'])
        print(_weather_ink('SOURCE //', 45), r['url'])
        desc = r['description']
        print(_weather_ink('DETAILS //', 129),
              desc if detail or len(desc) < 420 else desc[:420] + ' … [number for more]')
        if detail:
            print(_weather_ink('☣ EVENT EVIDENCE // NOAA SOURCE FIELDS', 39))
            for label, field in (
                ('EVENT TYPE', 'event_type'), ('STATE', 'state'),
                ('COUNTY / ZONE', 'county'), ('EVENT ID', 'event_id'),
                ('EPISODE ID', 'episode_id'), ('BEGIN', 'begin_date_time'),
                ('END', 'end_date_time'), ('DIRECT INJURIES', 'injuries_direct'),
                ('DIRECT DEATHS', 'deaths_direct'),
                ('PROPERTY DAMAGE (SOURCE)', 'damage_property'),
                ('CROP DAMAGE (SOURCE)', 'damage_crops')):
                value = r.get(field)
                print(_weather_ink(label + ' //', 51),
                      str(value).strip() if value is not None and str(value).strip() else 'NOT REPORTED')
            print(_weather_ink('SOURCE //', 45), r.get('url',''))
            print('CAVEAT // NOAA database entry; source damage fields not re-estimated.')

    # DEADBYTE_EVENT_INTELLIGENCE_V3_15
    def _type_index():
        from collections import Counter
        counts = Counter(str(r.get('event_type') or 'UNSPECIFIED').strip().upper()
                         for r in view)
        print('\n' + _weather_ink('☣ STORM TYPE INDEX // FILTERED NOAA RESULTS', 39))
        maximum = max(counts.values(), default=1)
        for name, amount in sorted(counts.items(), key=lambda item:(-item[1],item[0])):
            print(_weather_ink(f'{name:<22}', 135), '//',
                  _weather_ink(f'{amount:>6,}', 51), ' ', _weather_bar(amount, maximum, 28))
        print(_weather_ink('TOTAL EVENT ROWS // ' + format(len(view), ','), 46))
        print('EVIDENCE // Counts are database rows, not distinct storms.')

    def _show_detail(index):
        nonlocal selected_detail
        if not view:
            print('NO MATCHING EVENT ROWS')
            return
        if not 0 <= index < len(view):
            print('END OF FILTERED EVENT RECORDS')
            return
        selected_detail = index
        _display(index, True)
        print(_weather_ink('☣ DETAIL NAV // [J] Next  [K] Previous  [number] Jump', 39))

    def _next_page():
        nonlocal shown
        if shown >= len(view):
            print('END OF FILTERED RESULTS')
            return
        upper = min(shown + 10, len(view))
        for i in range(shown, upper):
            _display(i)
        shown = upper
        if shown == len(view):
            print('END OF FILTERED RESULTS')

    def _select_filter(kind):
        nonlocal state_filter, type_filter
        choices = _state_names() if kind == 'state' else _event_types()
        print('\n' + _weather_ink('☣ ' + kind.upper() + ' FILTER // OPTIONS',39))
        for i, value in enumerate(choices, 1):
            count = sum(1 for r in records if str(r.get(kind if kind=='state' else 'event_type','')).strip().upper()==value)
            print('[%02d] %s // %s rows' % (i, value, format(count,',')))
        print('[0] ALL ' + kind.upper() + 'S (remove this filter)')
        try:
            pick = input('SELECT NUMBER or EXACT NAME [ENTER cancels] > ').strip()
        except (EOFError,KeyboardInterrupt):
            print('FILTER CANCELED')
            return
        if not pick:
            return
        if pick == '0' or pick.lower() == 'all':
            selected = ''
        elif pick.isdigit() and 1 <= int(pick) <= len(choices):
            selected = choices[int(pick)-1]
        elif pick.upper() in choices:
            selected = pick.upper()
        else:
            print('INVALID FILTER // No changes')
            return
        if kind == 'state':
            state_filter = selected
        else:
            type_filter = selected
        _refresh()

    _refresh()
    if sys.stdin.isatty():
        while True:
            try:
                ans = input('\n☣ READER // [N]ext [M]onths [F]ilters [S]tate [T]ype '
                            '[R]eset [C]ounts [J/K] Detail [number] [A]ll [Q]uit > ').lower().strip()
            except (EOFError, KeyboardInterrupt):
                break
            if ans in ('q','quit','0',''):
                break
            if ans == 'c':
                _type_index()
            elif ans == 'm':
                _print_monthly_summary(view, year)
            elif ans in ('f','filters'):
                print('FILTERS // [S] State  |  [T] Storm type  |  [R] Reset all')
                print('CURRENT //',state_filter or 'ALL STATES','/',type_filter or 'ALL TYPES')
            elif ans == 's':
                _select_filter('state')
            elif ans == 't':
                _select_filter('event_type')
            elif ans == 'r':
                state_filter = ''
                type_filter = ''
                _refresh()
            elif ans == 'n':
                _next_page()
            elif ans == 'a':
                for i in range(shown, len(view)):
                    _display(i)
                shown = len(view)
            elif ans in ('j', '>'):
                if selected_detail is None:
                    print('OPEN AN EVENT NUMBER FIRST, THEN J FOR NEXT')
                else:
                    _show_detail(selected_detail + 1)
            elif ans in ('k', '<'):
                if selected_detail is None:
                    print('OPEN AN EVENT NUMBER FIRST, THEN K FOR PREVIOUS')
                else:
                    _show_detail(selected_detail - 1)
            elif ans.isdigit() and 1 <= int(ans) <= len(view):
                _show_detail(int(ans)-1)
            else:
                print('ENTER N / M / C / F / S / T / R / J / K / A / NUMBER / Q')
    # Persist the UNFILTERED source `records` via the existing v3.11 vault path.
    try:
        j,t=persist(root,question,info,records,url,total,matched)
        print('\n'+_weather_ink('☣ DEAD VAULT // SAVED JSON',46),j.name)
        print(_weather_ink('☣ DEAD VAULT // SAVED TXT ',46),t.name)
    except Exception as exc:print('VAULT ERROR //',type(exc).__name__,str(exc))
