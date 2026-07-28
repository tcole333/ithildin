#!/usr/bin/env python3
"""Ingest and query official DOJ and SEC press releases.

Confirmed sources:
* DOJ News API v1: /api/v1/press_releases.json (max pagesize 50, <=4 req/s)
* SEC newsroom press-release index: 2012-present
* SEC official static press archive: 1997-2011
"""

from __future__ import annotations

import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
import html
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from tools.fts_query import literal_fts_query
    from tools.government_releases import DEFAULT_DB_PATH, connect, content_hash, refresh_fts
    from tools.output_util import add_output_args, write_output
except ImportError:
    from fts_query import literal_fts_query
    from government_releases import DEFAULT_DB_PATH, connect, content_hash, refresh_fts
    from output_util import add_output_args, write_output


UA = "Ithildin-OSINT/1.0 (osint-research@proton.me)"
DOJ_API = "https://www.justice.gov/api/v1/press_releases.json"
DOJ_API_SORT = "created"
DOJ_API_DIRECTION = "ASC"
DOJ_CURSOR_VERSION = "created-asc-v1"
SEC_BASE = "https://www.sec.gov"
SEC_INDEX = f"{SEC_BASE}/newsroom/press-releases"


class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "svg", "noscript", "template", "nav", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            clean = re.sub(r"\s+", " ", data).strip()
            if clean:
                self.parts.append(clean)


def strip_html(value: str | None) -> str:
    parser = TextExtractor()
    parser.feed(value or "")
    return "\n".join(parser.parts)


def extract_balanced_div(text: str, class_token: str) -> str | None:
    """Return the HTML inside a div class, preserving nested div containers."""
    start = re.search(
        rf'<div\b[^>]*class="[^"]*\b{re.escape(class_token)}\b[^"]*"[^>]*>',
        text,
        re.I,
    )
    if not start:
        return None
    depth = 1
    for token in re.finditer(r'<div\b[^>]*>|</div\s*>', text[start.end():], re.I):
        depth += -1 if token.group(0).lower().startswith("</") else 1
        if depth == 0:
            return text[start.end():start.end() + token.start()]
    return None


def get_bytes(url: str, timeout: int = 45, retries: int = 3) -> bytes:
    """Fetch an official source with bounded 429/5xx/network retries."""
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html,application/xhtml+xml"})
    attempt = 0
    while True:
        try:
            with urlopen(req, timeout=timeout) as response:
                return response.read()
        except HTTPError as exc:
            if attempt >= retries or exc.code not in {429,500,502,503,504}:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try: delay = float(retry_after) if retry_after else 2 ** attempt
            except ValueError: delay = 2 ** attempt
        except URLError:
            if attempt >= retries:
                raise
            delay = 2 ** attempt
        time.sleep(min(max(delay,0.5),30.0)); attempt += 1


def decode_html(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252",errors="replace")


def epoch_date(value) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def source_ref(agency: str, native_id: str, release_number: str | None = None) -> str:
    token = release_number if agency == "SEC" and release_number else native_id
    return f"{agency}-PR:{token}"


def doj_state_key(title: str | None = None) -> str:
    """Return a cursor key tied to the API ordering contract.

    A cursor from the API's unspecified default order must never be reused after
    adopting an explicit order, so the order version is part of the key.
    """
    key = f"doj_next_page:{DOJ_CURSOR_VERSION}"
    if title:
        key += ":title:" + re.sub(r"\W+", "-", title.casefold()).strip("-")
    return key


def doj_api_params(page: int, title: str | None = None) -> dict:
    params = {
        "pagesize": 50,
        "page": page,
        "sort": DOJ_API_SORT,
        "direction": DOJ_API_DIRECTION,
    }
    if title:
        params["parameters[title]"] = title
    return params


def upsert_release(db: sqlite3.Connection, record: dict) -> tuple[int, bool]:
    agency = record["agency"]
    native_id = str(record["native_id"])
    existing = db.execute(
        "SELECT id,current_version_id FROM government_release WHERE agency=? AND native_id=?",
        (agency,native_id),
    ).fetchone()
    if existing:
        release_id = existing["id"]
        db.execute(
            """UPDATE government_release SET release_number=COALESCE(?,release_number),title=?,
               canonical_url=?,published_at=COALESCE(?,published_at),updated_at=COALESCE(?,updated_at),
               component_text=COALESCE(?,component_text),topic_text=COALESCE(?,topic_text),
               teaser=COALESCE(?,teaser),last_seen_at=CURRENT_TIMESTAMP WHERE id=?""",
            (record.get("release_number"),record["title"],record["canonical_url"],record.get("published_at"),
             record.get("updated_at"),record.get("component_text"),record.get("topic_text"),record.get("teaser"),release_id),
        )
    else:
        cursor = db.execute(
            """INSERT INTO government_release(
               agency,native_id,source_ref,release_number,title,canonical_url,published_at,
               updated_at,component_text,topic_text,teaser,fetch_status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (agency,native_id,source_ref(agency,native_id,record.get("release_number")),record.get("release_number"),
             record["title"],record["canonical_url"],record.get("published_at"),record.get("updated_at"),
             record.get("component_text"),record.get("topic_text"),record.get("teaser"),
             "complete" if record.get("content_text") is not None else "pending"),
        )
        release_id = cursor.lastrowid
    changed = False
    if record.get("content_text") is not None:
        digest = content_hash(record["title"],record.get("content_text"),record.get("updated_at"))
        version = db.execute(
            "SELECT id FROM government_release_version WHERE release_id=? AND content_hash=?",
            (release_id,digest),
        ).fetchone()
        if not version:
            db.execute("UPDATE government_release_version SET version_status='superseded' WHERE release_id=? AND version_status='current'", (release_id,))
            cursor = db.execute(
                """INSERT INTO government_release_version(
                   release_id,content_text,content_hash,raw_metadata_json)
                   VALUES(?,?,?,?)""",
                (release_id,record["content_text"],digest,json.dumps(record.get("raw_metadata",{}),ensure_ascii=False,default=str)),
            )
            db.execute("UPDATE government_release SET current_version_id=?,fetch_status='complete',fetch_error=NULL WHERE id=?", (cursor.lastrowid,release_id))
            changed = True
    refresh_fts(db, release_id)
    return int(release_id), changed


def begin_run(db, agency, mode, params, cursor_start=None):
    db.execute(
        """UPDATE ingest_run SET completed_at=CURRENT_TIMESTAMP,
           error=COALESCE(error,'interrupted before completion; superseded by a later run')
           WHERE agency=? AND mode=? AND completed_at IS NULL""",
        (agency,mode),
    )
    cursor = db.execute(
        "INSERT INTO ingest_run(agency,mode,cursor_start,parameters_json) VALUES(?,?,?,?)",
        (agency,mode,cursor_start,json.dumps(params,sort_keys=True,default=str)),
    )
    db.commit()
    return cursor.lastrowid


def finish_run(db, run_id, seen, changed, cursor_end, error=None):
    db.execute(
        """UPDATE ingest_run SET completed_at=CURRENT_TIMESTAMP,records_seen=?,records_changed=?,
           cursor_end=?,error=? WHERE id=?""",
        (seen,changed,cursor_end,error,run_id),
    )
    db.commit()


def cmd_init(args):
    db = connect(args.db)
    schema_version = db.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()[0]
    print(f"Initialized {args.db}; schema {schema_version}")


def cmd_ingest_doj(args):
    db = connect(args.db)
    state_key = doj_state_key(args.title)
    if args.start_page is None:
        row = db.execute("SELECT value FROM ingest_state WHERE key=?",(state_key,)).fetchone()
        page = int(row[0]) if row else 0
    else:
        page = args.start_page
    run_id = begin_run(db,"DOJ","api",vars(args),str(page))
    seen = changed = pages = 0
    error = None
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            while args.max_pages == 0 or pages < args.max_pages:
                batch_size=min(args.workers,args.max_pages-pages) if args.max_pages else args.workers
                batch_pages=list(range(page,page+batch_size))
                def fetch_page(page_number):
                    params = doj_api_params(page_number, args.title)
                    payload=json.loads(get_bytes(f"{DOJ_API}?{urlencode(params)}",args.timeout).decode("utf-8",errors="replace"))
                    return page_number,payload.get("results",[])
                fetched=list(executor.map(fetch_page,batch_pages))
                reached_end=False
                for page_number,results in fetched:
                    if not results:
                        reached_end=True; break
                    for item in results:
                        components = "; ".join(x.get("name","") for x in item.get("component",[]) if isinstance(x,dict))
                        topics = "; ".join(x.get("name","") if isinstance(x,dict) else str(x) for x in (item.get("topic") or [])) if isinstance(item.get("topic"),list) else strip_html(str(item.get("topic") or ""))
                        _, was_changed = upsert_release(db,{
                            "agency":"DOJ","native_id":item["uuid"],"release_number":item.get("number"),
                            "title":html.unescape(item.get("title") or "Untitled DOJ release"),"canonical_url":item.get("url"),
                            "published_at":epoch_date(item.get("date")),"updated_at":None,"component_text":components,
                            "topic_text":topics,"teaser":strip_html(item.get("teaser")),"content_text":strip_html(item.get("body")),
                            "raw_metadata":item,
                        })
                        seen += 1; changed += int(was_changed)
                    page=page_number+1; pages+=1
                    db.execute("INSERT OR REPLACE INTO ingest_state(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)", (state_key,str(page)))
                    db.commit()
                if reached_end: break
                if args.delay: time.sleep(args.delay)
    except Exception as exc:
        error = str(exc)
    finish_run(db,run_id,seen,changed,str(page),error)
    print(f"DOJ: processed {seen} releases across {pages} pages; {changed} new versions; next page {page}")
    if error: raise RuntimeError(error)


def parse_sec_modern_listing(text: str) -> list[dict]:
    records=[]
    for block in re.findall(r'<tr class="pr-list-page-row">(.*?)</tr>',text,re.S|re.I):
        href=re.search(r'href="([^"]*/newsroom/press-releases/[^"]+)"[^>]*>(.*?)</a>',block,re.S|re.I)
        if not href: continue
        date=re.search(r'<time[^>]+datetime="([^"]+)"',block,re.I)
        cells=re.findall(r'<td[^>]*>(.*?)</td>',block,re.S|re.I)
        number=strip_html(cells[2]).strip() if len(cells)>=3 else None
        records.append({"url":urljoin(SEC_BASE,html.unescape(href.group(1))),"title":strip_html(href.group(2)),"published_at":date.group(1) if date else None,"release_number":number})
    return records


def parse_doj_archive_month(text: str, base_url: str = "https://www.justice.gov") -> list[dict]:
    records=[]; seen=set()
    pattern=r'<h3[^>]*>(.*?)<span[^>]*class="[^"]*small[^"]*"[^>]*>\s*\(([^)]+)\)\s*</span>\s*</h3>\s*<p[^>]*>(.*?)<a[^>]+href="([^"]+)"'
    for title_html,number,teaser_html,href in re.findall(pattern,text,re.S|re.I):
        absolute=urljoin(base_url,html.unescape(href))
        if not re.search(r'/archive/opa/pr/(?:Pre_96/[A-Za-z]+\d{2}|\d{4}/[A-Za-z]+(?:\d{2})?)/[^/?#]+\.(?:html?|txt(?:\.html)?)$',absolute,re.I): continue
        seen.add(absolute); records.append({"url":absolute,"title":strip_html(title_html),"release_number":strip_html(number),"teaser":strip_html(teaser_html)})
    for href,label in re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>',text,re.S|re.I):
        absolute=urljoin(base_url,html.unescape(href))
        if absolute not in seen and re.search(r'/archive/opa/pr/(?:Pre_96/[A-Za-z]+\d{2}|\d{4}/[A-Za-z]+(?:\d{2})?)/[^/?#]+\.(?:html?|txt(?:\.html)?)$',absolute,re.I):
            seen.add(absolute); records.append({"url":absolute,"title":strip_html(label) or absolute.rsplit("/",1)[-1].rsplit(".",1)[0],"release_number":None,"teaser":None})
    return records


def extract_doj_archive_body(text: str) -> tuple[str,str|None,str|None]:
    title_match=re.search(r'<h1[^>]*class="[^"]*prtitle[^"]*"[^>]*>(.*?)</h1>',text,re.S|re.I)
    if not title_match: title_match=re.search(r'<h1[^>]*>(.*?)</h1>',text,re.S|re.I)
    title=strip_html(title_match.group(1)) if title_match else None
    date_match=re.search(r'FOR IMMEDIATE RELEASE\s*<br[^>]*>\s*([A-Z]+,\s+[A-Z]+\s+\d{1,2},\s+\d{4})',text,re.S|re.I)
    published=None
    if date_match:
        try: published=datetime.strptime(strip_html(date_match.group(1)).title(),"%A, %B %d, %Y").date().isoformat()
        except ValueError: pass
    body_match=re.search(r'<h1[^>]*class="[^"]*prtitle[^"]*"[^>]*>.*?</h1>(.*?)(?:<p[^>]*>\s*###|###)',text,re.S|re.I)
    body=strip_html(body_match.group(1)) if body_match else strip_html(text)
    number_match=re.search(r'<p[^>]*class="[^"]*none[^"]*"[^>]*>\s*([\d-]+)\s*</p>',text,re.I)
    return body,title,published or None


def cmd_discover_doj_archive(args):
    db=connect(args.db); run_id=begin_run(db,"DOJ","archive_discover",vars(args)); seen=changed=0; error=None
    try:
        for year in range(args.start_year,args.end_year+1):
            months=range(1,13)
            if year==1994: months=range(7,13)
            if year==2009: months=range(1,2)
            for month in months:
                if year<=1995:
                    url=f"https://www.justice.gov/archive/opa/pr/Pre_96/{calendar.month_name[month]}{str(year)[-2:]}/"
                elif year<=1997:
                    url=f"https://www.justice.gov/archive/opa/pr/{year}/{calendar.month_name[month]}{str(year)[-2:]}/"
                else:
                    url=f"https://www.justice.gov/archive/opa/pr/{year}/{calendar.month_name[month]}/"
                try: text=decode_html(get_bytes(url,args.timeout))
                except HTTPError as exc:
                    if exc.code==404: continue
                    raise
                for item in parse_doj_archive_month(text,url):
                    native="legacy:"+item["url"].rsplit("/",1)[-1].rsplit(".",1)[0]
                    _,was_changed=upsert_release(db,{"agency":"DOJ","native_id":native,"release_number":item.get("release_number"),"title":item["title"],"canonical_url":item["url"],"published_at":f"{year:04d}-{month:02d}","teaser":item.get("teaser") or "DOJ Office of Public Affairs legacy archive release"})
                    seen+=1; changed+=int(was_changed)
                db.commit()
                if args.delay: time.sleep(args.delay)
    except Exception as exc: error=str(exc)
    finish_run(db,run_id,seen,changed,str(args.end_year),error)
    print(f"DOJ archive discovery: {seen} index records processed")
    if error: raise RuntimeError(error)


def cmd_fetch_doj_archive(args):
    db=connect(args.db); run_id=begin_run(db,"DOJ","archive_fetch",vars(args)); seen=changed=0
    limit_clause=" LIMIT ?" if args.limit else ""; params=(args.limit,) if args.limit else ()
    rows=db.execute("""SELECT * FROM government_release WHERE agency='DOJ' AND fetch_status IN ('pending','failed')
      AND canonical_url LIKE '%/archive/opa/pr/%' ORDER BY published_at DESC,id"""+limit_clause,params).fetchall()
    def fetch_one(row):
        try:
            body,title,published=extract_doj_archive_body(decode_html(get_bytes(row["canonical_url"],args.timeout)))
            if len(body)<50: raise ValueError("extracted body is unexpectedly short")
            return row,body,title,published,None
        except Exception as exc: return row,None,None,None,str(exc)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for start in range(0,len(rows),args.workers):
            for row,body,title,published,fetch_error in executor.map(fetch_one,rows[start:start+args.workers]):
                if fetch_error:
                    db.execute("UPDATE government_release SET fetch_status='failed',fetch_error=? WHERE id=?",(fetch_error[:1000],row["id"])); continue
                _,was_changed=upsert_release(db,{"agency":"DOJ","native_id":row["native_id"],"release_number":row["release_number"],"title":title or row["title"],"canonical_url":row["canonical_url"],"published_at":published or row["published_at"],"component_text":"Office of Public Affairs","teaser":row["teaser"],"content_text":body,"raw_metadata":{"fetched_url":row["canonical_url"]}})
                seen+=1; changed+=int(was_changed)
            db.commit()
            if args.delay: time.sleep(args.delay)
    finish_run(db,run_id,seen,changed,str(rows[-1]["id"] if rows else ""))
    print(f"DOJ archive fetch: attempted {len(rows)}, completed {seen}, new versions {changed}")


def parse_sec_archive_listing(text: str, year: int) -> list[dict]:
    records=[]
    for block in re.findall(r'<tr[^>]*>(.*?)</tr>',text,re.S|re.I):
        match=re.search(
            r'href="([^"]*/news/press/(?!pressarchive/\d{4}press\.shtml)[^"]+)"[^>]*>\s*((?:\d{2}|\d{4})-[A-Za-z0-9]+)\s*</a>',
            block,re.I,
        )
        if not match or "-xx" in match.group(2): continue
        cells=re.findall(r'<td[^>]*>(.*?)</td>',block,re.S|re.I)
        if len(cells)<3: continue
        date_raw=strip_html(cells[1])
        try: published=datetime.strptime(date_raw,"%b. %d, %Y").date().isoformat()
        except ValueError:
            try: published=datetime.strptime(date_raw,"%B %d, %Y").date().isoformat()
            except ValueError: published=None
        records.append({"url":urljoin(SEC_BASE,html.unescape(match.group(1))),"title":strip_html(cells[2]),"published_at":published,"release_number":strip_html(match.group(2))})
    return records


def sec_index_record(item: dict) -> dict:
    """Map an SEC index row to the shared release schema."""
    native=item.get("release_number") or item["url"].rsplit("/",1)[-1]
    return {"agency":"SEC","native_id":native,"canonical_url":item["url"],
            "release_number":item.get("release_number"),"title":item["title"],
            "published_at":item.get("published_at")}


def cmd_discover_sec(args):
    db=connect(args.db); run_id=begin_run(db,"SEC","discover",vars(args)); seen=changed=0; error=None
    try:
        for year in range(args.start_year,args.end_year+1):
            if year>=2012:
                page=0
                while args.max_pages_per_year==0 or page<args.max_pages_per_year:
                    url=f"{SEC_INDEX}?{urlencode({'year':year,'month':'All','page':page})}"
                    records=parse_sec_modern_listing(decode_html(get_bytes(url,args.timeout)))
                    if not records: break
                    for item in records:
                        _,was_changed=upsert_release(db,sec_index_record(item))
                        seen+=1; changed+=int(was_changed)
                    db.commit(); page+=1
                    if args.delay: time.sleep(args.delay)
            else:
                url=f"{SEC_BASE}/news/press/pressarchive/{year}press.shtml"
                records=parse_sec_archive_listing(decode_html(get_bytes(url,args.timeout)),year)
                for item in records:
                    _,was_changed=upsert_release(db,sec_index_record(item))
                    seen+=1; changed+=int(was_changed)
                db.commit()
                if args.delay: time.sleep(args.delay)
    except Exception as exc: error=str(exc)
    finish_run(db,run_id,seen,changed,str(args.end_year),error)
    print(f"SEC discovery: {seen} index records processed; {changed} body versions")
    if error: raise RuntimeError(error)


def extract_sec_body(text: str) -> tuple[str,str|None,str|None]:
    title_match=re.search(r'<meta property="og:title" content="([^"]+)"',text,re.I)
    body_html = extract_balanced_div(text, "field--name-body")
    body_match = None
    if body_html is None:
        legacy_markers = re.search(r'<!--\s*BEGIN TEXT\s*-->(.*?)<!--\s*END TEXT\s*-->', text, re.S|re.I)
        if legacy_markers:
            body_html = legacy_markers.group(1)
    if body_html is None:  # legacy fallback when explicit text markers are absent
        body_match=re.search(r'<h1[^>]*>.*?</h1>(.*?)(?:<hr|<!--\s*End|<div id="footer")',text,re.S|re.I)
    title=html.unescape(title_match.group(1)) if title_match else None
    body=strip_html(body_html if body_html is not None else (body_match.group(1) if body_match else text))
    updated_match=re.search(r'Last Reviewed or Updated:\s*</?[^>]*>*\s*([^<]+)',text,re.I)
    return body,title,strip_html(updated_match.group(1)) if updated_match else None


def cmd_fetch_sec(args):
    db=connect(args.db); run_id=begin_run(db,"SEC","fetch",vars(args)); seen=changed=0; error=None
    limit_clause=" LIMIT ?" if args.limit else ""
    params=(args.limit,) if args.limit else ()
    rows=db.execute("SELECT * FROM government_release WHERE agency='SEC' AND fetch_status IN ('pending','failed') ORDER BY published_at DESC,id"+limit_clause,params).fetchall()
    def fetch_one(row):
        try:
            text=decode_html(get_bytes(row["canonical_url"],args.timeout))
            body,title,updated=extract_sec_body(text)
            if len(body)<50: raise ValueError("extracted body is unexpectedly short")
            return row,body,title,updated,None
        except Exception as exc:
            return row,None,None,None,str(exc)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for start in range(0,len(rows),args.workers):
            batch=rows[start:start+args.workers]
            for row,body,title,updated,fetch_error in executor.map(fetch_one,batch):
                if fetch_error:
                    db.execute("UPDATE government_release SET fetch_status='failed',fetch_error=? WHERE id=?",(fetch_error[:1000],row["id"]))
                    continue
                _,was_changed=upsert_release(db,{"agency":"SEC","native_id":row["native_id"],"release_number":row["release_number"],"title":title or row["title"],"canonical_url":row["canonical_url"],"published_at":row["published_at"],"updated_at":updated,"component_text":row["component_text"],"topic_text":row["topic_text"],"teaser":row["teaser"],"content_text":body,"raw_metadata":{"fetched_url":row["canonical_url"]}})
                changed+=int(was_changed); seen+=1
            db.commit()
            if args.delay: time.sleep(args.delay)
    finish_run(db,run_id,seen,changed,str(rows[-1]["id"] if rows else ""),error)
    print(f"SEC fetch: attempted {len(rows)}, completed {seen}, new versions {changed}")


def cmd_search(args):
    db=connect(args.db,create=False)
    agency_clause=" AND r.agency=?" if args.agency else ""
    params=[literal_fts_query(args.query)]
    if args.agency: params.append(args.agency)
    params.append(args.limit)
    rows=db.execute(f"""SELECT r.id,r.agency,r.source_ref,r.release_number,r.title,r.published_at,
      r.canonical_url,snippet(government_release_fts,5,'>>>','<<<','…',48) snippet
      FROM government_release_fts JOIN government_release r ON r.id=government_release_fts.release_id
      WHERE government_release_fts MATCH ?{agency_clause} ORDER BY rank LIMIT ?""",params).fetchall()
    data=[dict(r) for r in rows]
    if write_output(data,args,summary=f"government releases search '{args.query}'"): return
    print(json.dumps(data,indent=2,default=str))


def cmd_show(args):
    db=connect(args.db,create=False)
    row=db.execute("""SELECT r.*,v.content_text,v.content_hash,v.retrieved_at FROM government_release r
      LEFT JOIN government_release_version v ON v.id=r.current_version_id WHERE r.id=? OR r.source_ref=?""",(args.identifier,args.identifier)).fetchone()
    if not row: raise ValueError(f"Release not found: {args.identifier}")
    data=dict(row)
    if write_output(data,args,summary=f"government release {args.identifier}"): return
    print(json.dumps(data,indent=2,default=str))


def cmd_stats(args):
    db=connect(args.db,create=False)
    data={"by_agency_status":[dict(r) for r in db.execute("SELECT agency,fetch_status,COUNT(*) records,MIN(published_at) earliest,MAX(published_at) latest FROM government_release GROUP BY agency,fetch_status")],"versions":db.execute("SELECT COUNT(*) FROM government_release_version").fetchone()[0],"runs":[dict(r) for r in db.execute("SELECT * FROM ingest_run ORDER BY id DESC LIMIT 20")]}
    if write_output(data,args,summary="government release corpus stats"): return
    print(json.dumps(data,indent=2,default=str))


def common(p): p.add_argument("--db",type=Path,default=DEFAULT_DB_PATH)


def main():
    parser=argparse.ArgumentParser(description="DOJ and SEC primary press-release corpus"); sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("init"); common(p); p.set_defaults(func=cmd_init)
    p=sub.add_parser("ingest-doj"); p.add_argument("--start-page",type=int); p.add_argument("--title",help="Official API title filter with an independent resume cursor"); p.add_argument("--max-pages",type=int,default=0); p.add_argument("--workers",type=int,choices=range(1,5),default=4); p.add_argument("--delay",type=float,default=.3); p.add_argument("--timeout",type=int,default=45); common(p); p.set_defaults(func=cmd_ingest_doj)
    p=sub.add_parser("discover-doj-archive"); p.add_argument("--start-year",type=int,default=1994); p.add_argument("--end-year",type=int,default=2008); p.add_argument("--delay",type=float,default=10,help="DOJ robots.txt crawl delay (default: 10s)"); p.add_argument("--timeout",type=int,default=45); common(p); p.set_defaults(func=cmd_discover_doj_archive)
    p=sub.add_parser("fetch-doj-archive"); p.add_argument("--limit",type=int,default=100); p.add_argument("--workers",type=int,choices=range(1,2),default=1); p.add_argument("--delay",type=float,default=10,help="DOJ robots.txt crawl delay (default: 10s)"); p.add_argument("--timeout",type=int,default=45); common(p); p.set_defaults(func=cmd_fetch_doj_archive)
    p=sub.add_parser("discover-sec"); p.add_argument("--start-year",type=int,default=1997); p.add_argument("--end-year",type=int,default=datetime.now().year); p.add_argument("--max-pages-per-year",type=int,default=0); p.add_argument("--delay",type=float,default=.15); p.add_argument("--timeout",type=int,default=45); common(p); p.set_defaults(func=cmd_discover_sec)
    p=sub.add_parser("fetch-sec"); p.add_argument("--limit",type=int,default=100); p.add_argument("--workers",type=int,choices=range(1,5),default=4); p.add_argument("--delay",type=float,default=.15); p.add_argument("--timeout",type=int,default=45); common(p); p.set_defaults(func=cmd_fetch_sec)
    p=sub.add_parser("search"); p.add_argument("query"); p.add_argument("--agency",choices=["DOJ","SEC"]); p.add_argument("--limit",type=int,default=50); add_output_args(p); common(p); p.set_defaults(func=cmd_search)
    p=sub.add_parser("show"); p.add_argument("identifier"); add_output_args(p); common(p); p.set_defaults(func=cmd_show)
    p=sub.add_parser("stats"); add_output_args(p); common(p); p.set_defaults(func=cmd_stats)
    args=parser.parse_args()
    try: args.func(args)
    except (ValueError,FileNotFoundError,sqlite3.Error,RuntimeError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); raise SystemExit(1)


if __name__=="__main__": main()
