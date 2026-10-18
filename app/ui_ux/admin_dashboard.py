"""The admin dashboard: three server-rendered pages, plain HTML and CSS, bar
charts as inline SVG. No scripts, no libraries, nothing loaded from outside.
Built phone-first (375px) and widens to a two-column grid on a laptop.

Theme matches the app's dark tokens (app/static/app-v2/css/tokens.css):
base, elevated and floating surfaces, warm accent, serif for the big numbers.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

PAGES = [("today", "Today"), ("people", "People"), ("bot", "Bot and ads")]

CSS = """
:root{color-scheme:dark;--s0:#0a0a0b;--s1:#141417;--s2:#1c1c20;--line:#232327;--line-strong:#2e2e34;
--text:#f4f4f5;--muted:#9a9aa2;--faint:#7a7a82;--accent:#f2a866;--accent-deep:#ee7f2f;--accent-tint:rgba(242,168,102,.14);
--danger:#ff5b4d;--ok:#5fd39a;--serif:ui-serif,"New York",Georgia,"Noto Serif","Times New Roman",serif;
--sans:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--sh:0 1px 0 rgba(255,255,255,.035) inset,0 1px 2px rgba(0,0,0,.45),0 8px 24px rgba(0,0,0,.35);
--sh-float:0 1px 0 rgba(255,255,255,.05) inset,0 2px 6px rgba(0,0,0,.5),0 18px 48px rgba(10,6,2,.55),0 0 0 1px rgba(242,168,102,.08)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--s0);color:var(--text);font:16px/1.55 var(--sans);padding:0 16px 48px;
padding-left:max(16px,env(safe-area-inset-left));padding-right:max(16px,env(safe-area-inset-right))}
a{color:inherit}
.wrap{max-width:1040px;margin:0 auto}
header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:22px 0 6px}
h1{font:600 1.75rem/1.1 var(--serif);letter-spacing:-.02em;margin:0}
h1 em{color:var(--accent);font-style:italic}
.back{white-space:nowrap;font-size:.8125rem;color:var(--muted);text-decoration:none;padding:6px 10px;border-radius:999px;border:1px solid var(--line)}
.back:hover,.back:focus-visible{color:var(--text);border-color:var(--line-strong)}
.back:active{transform:scale(.97)}
.stamp{color:var(--faint);font-size:.75rem;margin:0 0 14px}
nav.tabs{display:flex;gap:6px;padding:4px;background:var(--s1);border:1px solid var(--line);border-radius:999px;box-shadow:var(--sh);margin-bottom:18px;position:sticky;top:8px;z-index:3}
nav.tabs a{flex:1;text-align:center;text-decoration:none;font-size:.875rem;font-weight:600;color:var(--muted);padding:9px 6px;border-radius:999px;
transition:transform .12s ease,opacity .12s ease;outline:none}
nav.tabs a:hover{color:var(--text)}
nav.tabs a:focus-visible{box-shadow:0 0 0 2px var(--accent)}
nav.tabs a:active{transform:scale(.97)}
nav.tabs a.on{background:linear-gradient(135deg,#f9a660,#ee7f2f);color:#1b1206}
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:18px}
.tile{background:var(--s1);border:1px solid var(--line);border-radius:16px;padding:14px 14px 12px;box-shadow:var(--sh);min-width:0}
.tile.hero{grid-column:1/-1;background:linear-gradient(160deg,#1a1510 0%,var(--s1)55%);border-color:rgba(242,168,102,.22);box-shadow:var(--sh-float)}
.tile .n{font:600 2.125rem/1 var(--serif);letter-spacing:-.03em;margin:0 0 6px;font-variant-numeric:tabular-nums}
.tile.hero .n{font-size:3rem}
.tile .l{font-size:.8125rem;color:var(--muted);margin:0}
.tile .d{font-size:.75rem;color:var(--faint);margin:4px 0 0}
.tile .d b{color:var(--accent);font-weight:600}
.card{background:var(--s1);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:var(--sh);margin-bottom:14px;min-width:0}
.card h2{font:600 1.125rem/1.2 var(--serif);letter-spacing:-.01em;margin:0 0 2px}
.card .sub{font-size:.8125rem;color:var(--muted);margin:0 0 12px}
.card .sub b{color:var(--text);font-weight:600}
.chart{display:block;width:100%;height:auto}
.axis{display:flex;justify-content:space-between;font-size:.6875rem;color:var(--faint);margin-top:4px;font-variant-numeric:tabular-nums}
.rows{display:flex;flex-direction:column;gap:8px}
.row{display:grid;grid-template-columns:minmax(0,1.25fr) 2fr 44px;align-items:center;gap:10px;font-size:.875rem}
.row .k{color:var(--muted);line-height:1.25;font-size:.8125rem;overflow-wrap:anywhere}
.rows+.chart{margin-top:16px}
.row .bar{height:12px;border-radius:6px;background:var(--s2);overflow:hidden;position:relative}
.row .bar i{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,var(--accent),var(--accent-deep));border-radius:6px;min-width:2px}
.row .bar i.muted{background:var(--line-strong)}
.row .v{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:.875rem}
th{font-size:.6875rem;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);font-weight:600;text-align:right;padding:0 0 8px}
th:first-child,td:first-child{text-align:left}
td{padding:8px 0;border-top:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
td:first-child{color:var(--muted)}
.note{font-size:.8125rem;color:var(--faint);margin:10px 0 0}
.empty{font-size:.875rem;color:var(--muted);padding:6px 0}
.grid{display:grid;grid-template-columns:1fr;gap:0 14px}
@media(min-width:760px){.tiles{grid-template-columns:repeat(4,1fr)}.tile.hero{grid-column:span 2}.grid{grid-template-columns:1fr 1fr}
h1{font-size:2.125rem}.tile .n{font-size:2.5rem}.tile.hero .n{font-size:3.5rem}}
"""


def _n(v: Any) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return escape(str(v))
    if f.is_integer():
        return f"{int(f):,}"
    return f"{f:,.2f}"


def _rs(v: float) -> str:
    return "Rs " + _n(round(float(v)))


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "0%"


def tile(n: Any, label: str, detail: str = "", hero: bool = False) -> str:
    cls = "tile hero" if hero else "tile"
    d = f'<p class="d">{detail}</p>' if detail else ""
    return f'<div class="{cls}"><p class="n">{n}</p><p class="l">{escape(label)}</p>{d}</div>'


def bars(values: list[int], days: list[str], color: str = "var(--accent)") -> str:
    """A 30-day bar chart as inline SVG. The last bar (today) is brighter.
    Scales to the card width; heights are relative to the biggest day."""
    n = max(len(values), 1)
    peak = max(values) if values and max(values) > 0 else 1
    w, h, gap = 300, 72, 1.6
    bw = (w - gap * (n - 1)) / n
    out = [f'<svg class="chart" viewBox="0 0 {w} {h + 4}" preserveAspectRatio="none" role="img" aria-label="Last {n} days">']
    for i, v in enumerate(values):
        x = i * (bw + gap)
        bh = max(2, round(h * v / peak, 1)) if v > 0 else 1.5
        fill = color if i == n - 1 else ("var(--line-strong)" if v == 0 else color)
        op = "1" if i == n - 1 else ("0.55" if v > 0 else "0.9")
        out.append(f'<rect x="{x:.1f}" y="{h - bh:.1f}" width="{bw:.1f}" height="{bh}" rx="1.2" fill="{fill}" opacity="{op}"><title>{escape(days[i])}: {v}</title></rect>')
    out.append("</svg>")
    first, last = (days[0], days[-1]) if days else ("", "")
    axis = f'<div class="axis"><span>{_pretty_day(first)}</span><span>peak {peak}</span><span>today</span></div>'
    return "".join(out) + axis


def _pretty_day(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%-d %b")
    except ValueError:
        return escape(d)


def hrows(items: list[tuple[str, int]], muted_zero: bool = True) -> str:
    peak = max((v for _, v in items), default=0) or 1
    out = ['<div class="rows">']
    for k, v in items:
        width = max(0.0, 100.0 * v / peak)
        cls = ' class="muted"' if (muted_zero and v == 0) else ""
        out.append(f'<div class="row"><span class="k">{escape(k)}</span><span class="bar"><i{cls} style="width:{width:.1f}%"></i></span><span class="v">{_n(v)}</span></div>')
    out.append("</div>")
    return "".join(out)


def card(title: str, sub: str, body: str, note: str = "") -> str:
    s = f'<p class="sub">{sub}</p>' if sub else ""
    n = f'<p class="note">{note}</p>' if note else ""
    return f'<section class="card"><h2>{escape(title)}</h2>{s}{body}{n}</section>'


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

def _page_today(d: dict[str, Any]) -> str:
    p, r, c, b = d["people"], d["reels"], d["cost"], d["bot"]
    days = d["days30"]
    tiles = '<div class="tiles">' + "".join([
        tile(_n(p["total"]), "People in total", f'<b>+{_n(p["today"])}</b> today, <b>+{_n(p["last_7"])}</b> this week', hero=True),
        tile(_n(r["total"]), "Reels saved in total", f'<b>+{_n(r["today"])}</b> today by {_n(r["savers_today"])} people', hero=True),
        tile(_n(p["today"]), "New people today"),
        tile(_n(r["today"]), "Reels saved today"),
        tile(_n(b["wrote_today"]), "Wrote to the bot today"),
        tile(_rs(c["today"]), "Cost today", f"at Rs {c['per_reel']} a reel"),
    ]) + "</div>"
    strips = f"""<table><tr><th>Window</th><th>New people</th><th>Reels</th><th>Cost</th></tr>
<tr><td>Today</td><td>{_n(p["today"])}</td><td>{_n(r["today"])}</td><td>{_rs(c["today"])}</td></tr>
<tr><td>Last 7 days</td><td>{_n(p["last_7"])}</td><td>{_n(r["last_7"])}</td><td>{_rs(r["last_7"] * c["per_reel"])}</td></tr>
<tr><td>Last 30 days</td><td>{_n(p["last_30"])}</td><td>{_n(r["last_30"])}</td><td>{_rs(r["last_30"] * c["per_reel"])}</td></tr>
<tr><td>This month</td><td>{_n(p["this_month"])}</td><td>{_n(r["this_month"])}</td><td>{_rs(c["this_month"])}</td></tr>
<tr><td>All time</td><td>{_n(p["total"])}</td><td>{_n(r["total"])}</td><td>{_rs(c["total"])}</td></tr></table>"""
    older = d["older"]
    older_note = f'Counting people who came through the bot. Not counted: {_n(older["people"])} older accounts with {_n(older["reels"])} reels (you and testers).'
    return tiles + '<div class="grid">' + "".join([
        card("New people per day", f"Last 30 days. <b>{_n(sum(p['per_day']))}</b> joined, <b>{_n(sum(p['ig_per_day']))}</b> of them through the bot.", bars(p["per_day"], days)),
        card("Reels saved per day", f"Last 30 days. <b>{_n(sum(r['per_day']))}</b> reels, <b>{_n(sum(r['failed_per_day']))}</b> failed.", bars(r["per_day"], days)),
    ]) + "</div>" + card("The windows side by side", "", strips, f"Cost is an estimate at Rs {c['per_reel']} per reel read. {older_note}")


def _page_people(d: dict[str, Any]) -> str:
    p, r, cap, egg = d["people"], d["reels"], d["cap"], d["egg"]
    days = d["days30"]
    tiles = '<div class="tiles">' + "".join([
        tile(_n(p["guests"]), "Guests", "saved reels, never signed in"),
        tile(_n(p["signed_in"]), "Signed in with Google"),
        tile(f'{_n(p["returned_after_week"])}<span style="font-size:.5em;color:var(--muted)"> of {_n(p["eligible_for_return"])}</span>', "Came back a week later",
             f'<b>{_pct(p["returned_after_week"], p["eligible_for_return"])}</b> of people older than 7 days'),
        tile(_n(p["guests_who_signed_in"]), "Guests who later signed in", f'of {_n(p["from_instagram"])} who came through the bot'),
    ]) + "</div>"
    bucket_items = [(x["label"] + (" reel" if x["label"] == "1" else " reels"), x["people"]) for x in d["buckets"]]
    bucket_card = card("Reels per person", f"How many reels each of the <b>{_n(p['total'])}</b> people has sent us.", hrows(bucket_items),
                       f'Counts every reel that reached us, failed ones included ({_n(r["failed"])} failed). '
                       f'0 reels is mostly people from the ad who only asked a question; {_n(d.get("zero_post_only", 0))} of them sent a post we could not save. '
                       f'Not counted: {_n(d.get("ad_items", 0))} copies of our own ad saved as ClipNest ad, and '
                       f'{_n(d["older"]["people"])} older accounts (you and testers) with {_n(d["older"]["reels"])} reels.')
    stays_card = _stays_card(d["stays"])
    reels_card = card(
        "Reels",
        f'<b>{_n(r["total"])}</b> saved, <b>{_n(r["failed"])}</b> failed, <b>{_n(r["in_progress"])}</b> in progress right now.',
        bars(r["failed_per_day"], days, "var(--danger)"),
        "Failed reels per day, last 30 days.",
    )
    if cap["cap"]:
        cap_body = hrows([("At the cap", cap["at_cap"]), ("Near it (80%+)", cap["near_cap"]), ("Reels refused", cap["refused"])])
        cap_note = f"Cap is {cap['cap']} reels a month (100 for Easter egg accounts). Counted since {escape(cap['since'][:10])}."
    else:
        cap_body = '<p class="empty">No monthly cap is set.</p>'
        cap_note = ""
    cap_card = card("Monthly cap", "", cap_body, cap_note)
    if not egg["live"]:
        egg_body = '<p class="empty">Not live on this server yet. It will show here on its own once the Easter egg change is deployed.</p>'
    elif not egg["groups"]:
        egg_body = '<p class="empty">Live, waiting for the first person to share our own reel back.</p>'
    else:
        rows = "".join(
            f'<tr><td>{escape({"egg": "Easter egg (100 a month)", "plain": "Plain answer"}.get(g["group"], g["group"]))}</td><td>{_n(g["people"])}</td><td>{_n(g["saved_a_reel"])}</td><td>{_pct(g["saved_a_reel"], g["people"])}</td></tr>'
            for g in egg["groups"]
        )
        egg_body = f"<table><tr><th>Group</th><th>People</th><th>Saved a reel</th><th>Rate</th></tr>{rows}</table>"
    egg_card = card("Easter egg test", "People who shared our own reel back, split 20 / 80.", egg_body)
    return tiles + stays_card + '<div class="grid">' + bucket_card + reels_card + cap_card + egg_card + "</div>"


def _stays_card(st: dict[str, Any]) -> str:
    d1 = _pct(st["d1_stayed"], st["d1_people"]) if st["d1_people"] else "not yet"
    d3 = _pct(st["d3_stayed"], st["d3_people"]) if st["d3_people"] else "not yet"
    head = '<div class="tiles" style="margin-bottom:12px">' + "".join([
        tile(d1, "Back after 1 day", f'{_n(st["d1_stayed"])} of {_n(st["d1_people"])} people'),
        tile(d3, "Back after 3 days", f'{_n(st["d3_stayed"])} of {_n(st["d3_people"])} people'),
    ]) + "</div>"

    def cell(stayed: Any, joined: int, so_far: bool) -> str:
        if stayed is None:
            return '<td style="color:var(--faint)">not yet</td>'
        tail = " so far" if so_far else ""
        return f"<td>{_pct(stayed, joined)} <span style=\"color:var(--faint)\">({_n(stayed)}){tail}</span></td>"

    if st["rows"]:
        rows = "".join(
            f'<tr><td>{_pretty_day(x["day"])}</td><td>{_n(x["joined"])}</td>{cell(x["day1"], x["joined"], x["day1_so_far"])}{cell(x["day3"], x["joined"], x["day3_so_far"])}</tr>'
            for x in st["rows"]
        )
        table = f"<table><tr><th>Joined</th><th>People</th><th>After 1 day</th><th>After 3 days</th></tr>{rows}</table>"
    else:
        table = '<p class="empty">No one has sent a reel yet.</p>'
    return card(
        "Who stays",
        "People grouped by the day of their first reel, and how many sent another reel later.",
        head + table,
        "After 1 day: sent a reel on any later day. After 3 days: sent one on the third day after joining or later. "
        "The two big numbers only use groups whose day is fully over; rows still running say so far. Days in India time. Our own ad is not counted as a reel.",
    )


def _page_bot(d: dict[str, Any]) -> str:
    b, p = d["bot"], d["people"]
    days = d["days30"]
    ad = b["ad"]
    arrivals = b["totals"].get("ad_referral", 0)
    hello = ad["m24_ad_hello"]["total"] + ad["m29_own_reel_egg"]["total"]
    tiles = '<div class="tiles">' + "".join([
        tile(_n(b["wrote_today"]), "Wrote to the bot today", f'<b>{_n(b["wrote_7"])}</b> in the last 7 days'),
        tile(_n(p["ig_per_day"][-1]), "New accounts from the bot today", f'<b>{_n(sum(p["ig_per_day"][-7:]))}</b> this week'),
        tile(_n(b["waiting_for_human_7d"]), "Messages waiting for you", "typed messages, last 7 days"),
        tile(_n(hello), "People from the ad", f'<b>{_n(ad["m24_ad_hello"]["today"] + ad["m29_own_reel_egg"]["today"])}</b> today'),
    ]) + "</div>"
    wrote_card = card("People who wrote per day", f"Anyone who sent the bot anything. <b>{_n(b['wrote_total_people'])}</b> different people so far.", bars(b["wrote_per_day"], days),
                      f"Daily bot history is kept from {_pretty_day(b['history_from']) if b['history_from'] else 'today'} onwards.")
    created_card = card("Accounts the bot created per day", "A stranger's first reel makes an account.", bars(p["ig_per_day"], days))
    q_rows = [(ad[k]["label"], ad[k]["total"]) for k in ("m25_ad_how", "m26_ad_free", "m27_ad_share")]
    ad_body = hrows([("Arrived from an ad", arrivals), ("Got the ad hello", hello)] + q_rows)
    ad_card = card("Ads", "Who tapped into the chat from an ad, and which question they tapped.", ad_body + bars(b["ad_hello_per_day"], days),
                   "Ad hellos per day, last 30 days. A question only counts when the bot answered it.")
    f = b["funnel"]
    funnel_rows = [(f[k]["label"], f[k]["people"]) for k in ("m1_first_ack", "m2_first_library", "m3_quiet_nudge", "m4_home_screen")]
    funnel_card = card("What the bot sent", "Different people who got each message, all time.", hrows(funnel_rows))
    return tiles + '<div class="grid">' + wrote_card + created_card + ad_card + funnel_card + "</div>"


def render(page: str, d: dict[str, Any]) -> str:
    page = page if page in dict(PAGES) else "today"
    body = {"today": _page_today, "people": _page_people, "bot": _page_bot}[page](d)
    tabs = "".join(
        f'<a href="/admin/dashboard{"" if key == "today" else "/" + key}" class="{"on" if key == page else ""}">{escape(label)}</a>'
        for key, label in PAGES
    )
    offset = d["utc_offset_minutes"]
    sign = "+" if offset >= 0 else "-"
    zone = f"UTC{sign}{abs(offset) // 60}:{abs(offset) % 60:02d}"
    stamp = f"Fresh on every open. Computed in {d['computed_in_ms']} ms. Days run on {zone}. Today is {_pretty_day(d['today'])}."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>ClipNest numbers</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<header><h1>ClipNest <em>numbers</em></h1><a class="back" href="/app">Back to app</a></header>
<p class="stamp">{escape(stamp)} <a href="/admin/comment-reels">Comment-to-get reels</a></p>
<nav class="tabs">{tabs}</nav>
{body}
</div></body></html>"""


PROMISE_LABELS = {"link": "Link", "recipe": "Recipe", "file": "File or PDF", "code": "Code or discount",
                  "list": "List", "product": "Product", "other": "Something else"}


def render_comment_reels(rows: list[dict[str, Any]]) -> str:
    """Reels where the creator says "comment LINK to get the link". Admin only."""
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["promise"]] = counts.get(r["promise"], 0) + 1
    summary = " ".join(
        f'<span class="pill">{escape(PROMISE_LABELS.get(k, k))} {v}</span>'
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
    )
    body = "".join(
        f"""<tr><td><a href="{escape(r['url'])}" target="_blank" rel="noopener noreferrer">{escape(r['title'] or r['reel_id'])}</a>
<div class="cb-id">{escape(r['reel_id'])}{f" · saved {r['saves']} times" if r['saves'] > 1 else ""}</div></td>
<td><b>{escape(r['trigger'])}</b></td><td>{escape(PROMISE_LABELS.get(r['promise'], r['promise']))}</td>
<td class="cb-snip">{escape(r['snippet'])}</td><td class="cb-id">{escape(r['tagged_at'][:10])}</td></tr>"""
        for r in rows
    ) or '<tr><td colspan="5">No reels tagged yet.</td></tr>'
    extra = """
.cb-table{width:100%;border-collapse:collapse;font-size:.875rem;margin-top:14px}
.cb-table th{text-align:left;color:var(--muted);font-weight:500;padding:8px 8px;border-bottom:1px solid var(--line-strong)}
.cb-table td{padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.cb-table a{text-decoration:none;border-bottom:1px solid var(--line-strong)}
.cb-table a:hover,.cb-table a:focus-visible{color:var(--accent);border-color:var(--accent)}
.cb-snip{color:var(--muted);max-width:420px}.cb-id{color:var(--faint);font-size:.75rem;margin-top:2px}
.pill{display:inline-block;padding:3px 10px;margin:0 6px 6px 0;border-radius:999px;background:var(--accent-tint);color:var(--accent);font-size:.8125rem}
.cb-wrap{overflow-x:auto;background:var(--s1);border:1px solid var(--line);border-radius:14px;padding:4px 12px;box-shadow:var(--sh)}
"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>Comment-to-get reels</title>
<style>{CSS}{extra}</style></head>
<body><div class="wrap">
<header><h1>Comment <em>to get</em></h1><a class="back" href="/admin/dashboard">Back to numbers</a></header>
<p class="stamp">{len(rows)} reels where the creator asks for a comment or DM to send something back. <a href="/admin/comment-reels.csv">Download CSV</a></p>
<p>{summary}</p>
<div class="cb-wrap"><table class="cb-table"><thead><tr><th>Reel</th><th>Word</th><th>Promised</th><th>What it says</th><th>Tagged</th></tr></thead>
<tbody>{body}</tbody></table></div>
</div></body></html>"""
