"""
Take games already played off the web page (Oct 28, 2026; Joe, 7:16 AM: "Can we run an automated push every morning at 5am est to
clear the website of already played games? Go ahead and clear out last nights and push").

  python3 clear_played.py PAGE.html [--now 2026-10-29T04:32:00-04:00] [--hours 4.5] [--dry-run]

A game counts as played once its kickoff is HOURS (default 4.5) behind --now (default: the clock); a TBD kickoff counts as 11:59 PM
ET of its date, so it stays up through its day.  The page keeps its game rows in the <script id="card-data"> JSON, and the slate,
the day bands, the filter chips and the counts are all drawn from them, so dropping rows is the whole change.  The header's
records are untouched: finished games still count there.  make_web.py applies the same rule (clear_rows) when it builds the
page; the daily scheduled task runs this script on the published page (the site repository's tools/clear_played.py, copied there
by publish_site.sh).  Prints one line per removed game and "removed N of M"; writes only when it removed something.  Exit 2 when
the page has no card data.
"""
import sys, re, json, argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
MON = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}
PAT = re.compile(r'(<script id="card-data" type="application/json">)(.*?)(</script>)', re.S)


def kickoff(row, season):
    """the row's kickoff (aware datetime); a TBD game: 11:59 PM ET of its date ('Sat Oct 31'); None when neither can be read"""
    k = row.get('kick_iso')
    if k:
        t = datetime.fromisoformat(k)
        return t if t.tzinfo else t.replace(tzinfo=ET)
    m = re.match(r'\s*\w{3}\s+(\w{3})\s+(\d{1,2})', str(row.get('date', '')))
    if not m or m.group(1) not in MON or season is None:
        return None
    mo = MON[m.group(1)]
    yr = int(season) + (1 if mo <= 2 else 0)            # a January game belongs to the season before
    return datetime(yr, mo, int(m.group(2)), 23, 59, tzinfo=ET)


def played(row, now, season, hours=4.5):
    t = kickoff(row, season)
    return t is not None and t + timedelta(hours=hours) <= now


def clear_rows(D, now=None, hours=4.5):
    """drop the played games from D['rows'] in place; returns the removed rows"""
    now = now or datetime.now(timezone.utc)
    rows = D.get('rows') or []
    gone = [r for r in rows if played(r, now, D.get('season'), hours)]
    if gone:
        D['rows'] = [r for r in rows if not played(r, now, D.get('season'), hours)]
    return gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('page'); ap.add_argument('--now', default=None, help='ISO time (default: now)')
    ap.add_argument('--hours', type=float, default=4.5, help='hours after kickoff a game counts as played (default 4.5)')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    html = open(a.page, encoding='utf-8').read()
    m = PAT.search(html)
    if not m:
        print('no card data in %s' % a.page); sys.exit(2)
    D = json.loads(m.group(2))
    n0 = len(D.get('rows') or [])
    gone = clear_rows(D, now, a.hours)
    for r in gone:
        print('  played: %s %s  %s @ %s' % (r.get('date'), r.get('kick'), (r.get('away') or {}).get('team'), (r.get('home') or {}).get('team')))
    print('removed %d of %d games (kicked off %.1f+ hours before %s); %d left on the page' % (
        len(gone), n0, a.hours, now.astimezone(ET).strftime('%a %b %-d %-I:%M %p ET'), n0 - len(gone)))
    if gone and not a.dry_run:
        data = json.dumps(D, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')   # as make_web.py writes it
        open(a.page, 'w', encoding='utf-8').write(html[:m.start(2)] + data + html[m.end(2):])


if __name__ == '__main__':
    main()
