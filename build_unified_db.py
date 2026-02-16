#!/usr/bin/env python3
"""Build a unified, deduplicated, searchable SQLite database from all Epstein email datasets."""

import sqlite3
import pandas as pd
import json
import re
import hashlib
import email as email_mod
from email import policy
from pathlib import Path
from html.parser import HTMLParser

DB_PATH = "datasets/unified_epstein.db"
DATASETS_DIR = Path("datasets")

def clean_html(text):
    if pd.isna(text) or not text:
        return ""
    text = str(text)
    # Remove style/script blocks entirely
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def content_hash(text):
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    return hashlib.md5(normalized.encode()).hexdigest()

def create_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_dataset TEXT,
            source_doc_id TEXT,
            from_address TEXT,
            to_address TEXT,
            other_recipients TEXT,
            subject TEXT,
            timestamp_raw TEXT,
            timestamp_iso TEXT,
            body_text TEXT,
            body_html TEXT,
            content_hash TEXT,
            thread_id TEXT,
            message_order INTEGER
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_dataset TEXT,
            doc_id TEXT,
            category TEXT,
            summary TEXT,
            full_text TEXT,
            date_earliest TEXT,
            date_latest TEXT,
            content_hash TEXT
        );

        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT,
            hop_distance INTEGER,
            source TEXT
        );

        CREATE TABLE IF NOT EXISTS triples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT,
            action TEXT,
            target TEXT,
            location TEXT,
            timestamp TEXT,
            explicit_topic TEXT,
            implicit_topic TEXT,
            doc_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_emails_from ON emails(from_address);
        CREATE INDEX IF NOT EXISTS idx_emails_to ON emails(to_address);
        CREATE INDEX IF NOT EXISTS idx_emails_subject ON emails(subject);
        CREATE INDEX IF NOT EXISTS idx_emails_hash ON emails(content_hash);
        CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(content_hash);
        CREATE INDEX IF NOT EXISTS idx_triples_actor ON triples(actor);
        CREATE INDEX IF NOT EXISTS idx_triples_target ON triples(target);
    """)

def ingest_hf_parquet(conn):
    """Ingest the HuggingFace to-be/epstein-emails Parquet."""
    path = DATASETS_DIR / "epstein-emails-hf" / "emails.parquet"
    if not path.exists():
        print(f"  Skipping: {path} not found")
        return 0

    df = pd.read_parquet(path)
    count = 0
    seen_hashes = set()

    for _, row in df.iterrows():
        body = clean_html(row.get('message_html', ''))
        if not body:
            continue
        ch = content_hash(body)
        if ch in seen_hashes:
            continue
        seen_hashes.add(ch)

        conn.execute("""
            INSERT INTO emails (source_dataset, source_doc_id, from_address, to_address,
                other_recipients, subject, timestamp_raw, timestamp_iso, body_text, body_html,
                content_hash, thread_id, message_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'hf_to-be',
            row.get('source_filename', ''),
            row.get('from_address', ''),
            row.get('to_address', ''),
            str(row.get('other_recipients', '')),
            row.get('subject', ''),
            str(row.get('timestamp_raw', '')),
            str(row.get('timestamp_iso', '')),
            body,
            str(row.get('message_html', '')),
            ch,
            str(row.get('email_document_id', '')),
            row.get('message_order', 0)
        ))
        count += 1

    conn.commit()
    return count

def ingest_threads(conn):
    """Ingest the notesbymuneeb thread dataset."""
    path = DATASETS_DIR / "notesbymuneeb_epstein_email_threads.parquet"
    if not path.exists():
        print(f"  Skipping: {path} not found")
        return 0

    df = pd.read_parquet(path)
    count = 0

    # Get existing hashes to deduplicate
    existing = set(r[0] for r in conn.execute("SELECT content_hash FROM emails").fetchall())

    for _, row in df.iterrows():
        msgs = row['messages']
        if isinstance(msgs, str):
            try:
                msgs = json.loads(msgs)
            except:
                continue

        for i, msg in enumerate(msgs):
            body = msg.get('body', '') or ''
            if not body or len(body) < 10:
                continue
            ch = content_hash(body)
            if ch in existing:
                continue
            existing.add(ch)

            conn.execute("""
                INSERT INTO emails (source_dataset, source_doc_id, from_address, to_address,
                    other_recipients, subject, timestamp_raw, timestamp_iso, body_text, body_html,
                    content_hash, thread_id, message_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'hf_notesbymuneeb',
                row.get('source_file', ''),
                msg.get('sender', ''),
                str(msg.get('recipients', '')),
                '',
                msg.get('subject', '') or row.get('subject', ''),
                msg.get('timestamp', ''),
                '',
                body,
                '',
                ch,
                row.get('thread_id', ''),
                i
            ))
            count += 1

    conn.commit()
    return count

def ingest_doc_explorer(conn):
    """Ingest documents and triples from the doc-explorer database."""
    db_path = DATASETS_DIR / "Epstein-doc-explorer" / "document_analysis.db"
    if not db_path.exists():
        print(f"  Skipping: {db_path} not found")
        return 0, 0

    src = sqlite3.connect(str(db_path))

    # Documents (deduplicated, skip TEXT- prefixed duplicates)
    docs = src.execute("""
        SELECT doc_id, category, one_sentence_summary, full_text,
               date_range_earliest, date_range_latest
        FROM documents
        WHERE doc_id NOT LIKE 'TEXT-%'
    """).fetchall()

    doc_count = 0
    seen_hashes = set()
    for doc in docs:
        text = doc[3] or ''
        if len(text) < 20:
            continue
        ch = content_hash(text[:2000])  # Hash first 2000 chars to handle split docs
        if ch in seen_hashes:
            continue
        seen_hashes.add(ch)

        conn.execute("""
            INSERT INTO documents (source_dataset, doc_id, category, summary, full_text,
                date_earliest, date_latest, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('doc_explorer', doc[0], doc[1], doc[2], text, doc[4], doc[5], ch))
        doc_count += 1

    # Triples
    triples = src.execute("""
        SELECT actor, action, target, location, timestamp,
               explicit_topic, implicit_topic, doc_id
        FROM rdf_triples
    """).fetchall()

    for t in triples:
        conn.execute("""
            INSERT INTO triples (actor, action, target, location, timestamp,
                explicit_topic, implicit_topic, doc_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, t)

    # Entities
    entities = src.execute("""
        SELECT canonical_name, hop_distance_from_principal FROM canonical_entities
    """).fetchall()

    for e in entities:
        conn.execute("""
            INSERT INTO entities (canonical_name, hop_distance, source)
            VALUES (?, ?, ?)
        """, (e[0], e[1], 'doc_explorer'))

    conn.commit()
    src.close()
    return doc_count, len(triples)

def is_spam_email(sender, subject, body):
    """Aggressively filter automated/commercial emails from Yahoo inbox."""
    sender_lower = (sender or '').lower()
    subj_lower = (subject or '').lower()
    body_lower = (body or '').lower()[:1000]

    # Check sender domain against known commercial/spam domains
    m = re.search(r'@([\w.-]+)', sender_lower)
    if m:
        domain = m.group(1)
        # Strip common subdomains
        parts = domain.split('.')
        if len(parts) > 2:
            base = '.'.join(parts[-2:])
        else:
            base = domain

        spam_base_domains = {
            'amazon.com', 'pandora.com', 'linkedin.com', 'facebook.com',
            'facebookmail.com', 'twitter.com', 'houzz.com', 'ebay.com',
            'paypal.com', 'groupon.com', 'yelp.com', 'fab.com',
            'audible.com', 'coursera.org', '23andme.com', 'mymms.com',
            'conciergeauctions.com', 'localadsoffers.com', 'treatsmagazine.com',
            'firmoo.com', 'numuses.com', 'designmixers.com', 'kicknumbers.com',
            'knowfinder.com', 'yourdatadaily.com', 'recipestastyvideos.com',
            'skillsandcareers.com', 'cnbc.com', 'washingtonpost.com',
            'nytimes.com', 'wsj.com', 'ditto.com', 'dailynews.vi',
            'smiledirectclub.com', 'kohls.com', 'geico.com', 'spotify.com',
            'netflix.com', 'hulu.com', 'apple.com', 'google.com',
            'instagram.com', 'pinterest.com', 'quora.com', 'reddit.com',
            'zillow.com', 'trulia.com', 'redfin.com', 'wayfair.com',
            'guideshere.com', 'orangeokaydeals.com', 'section8-assistance.org',
            'hexaem.com', 'limorsin.com', 'mixedstar.com', 'limorsinn.com',
            'constantcontact.com', 'mailchimp.com', 'sendgrid.net',
            'exacttarget.com', 'sailthru.com', 'returnpath.com',
            'uber.com', 'lyft.com', 'doordash.com', 'grubhub.com',
            'target.com', 'walmart.com', 'bestbuy.com', 'macys.com',
            'nordstrom.com', 'gap.com', 'oldnavy.com', 'jcrew.com',
            'williams-sonoma.com', 'potterybarn.com', 'crateandbarrel.com',
            'westelm.com', 'cb2.com', 'restorationhardware.com',
            'anthropologie.com', 'urbanoutfitters.com', 'zara.com',
            'etsy.com', 'wish.com', 'aliexpress.com',
            'expedia.com', 'booking.com', 'airbnb.com', 'hotels.com',
            'kayak.com', 'tripadvisor.com', 'priceline.com',
            'chase.com', 'bankofamerica.com', 'citi.com', 'capitalone.com',
            'americanexpress.com', 'discover.com', 'wellsfargo.com',
            'fidelity.com', 'schwab.com', 'vanguard.com', 'tdameritrade.com',
            'robinhood.com', 'mint.com', 'creditkarma.com',
            'bluecrossblueshield.com', 'uhc.com', 'aetna.com', 'cigna.com',
            'anthem.com', 'humana.com', 'kaiser.org',
            'comcast.com', 'verizon.com', 'att.com', 'tmobile.com',
            'sprint.com', 'cox.com', 'spectrum.com', 'directv.com',
            'siriusxm.com', 'pandora.com',
            'indeed.com', 'glassdoor.com', 'monster.com', 'ziprecruiter.com',
            'careerbuilder.com', 'dice.com', 'salary.com',
        }
        if base in spam_base_domains or domain in spam_base_domains:
            return True

        # Catch subdomains of known spam senders
        for sd in spam_base_domains:
            if domain.endswith('.' + sd):
                return True

    # Check keywords in subject/sender
    spam_keywords = [
        'unsubscribe', 'newsletter', 'noreply', 'no-reply', 'mailer-daemon',
        'postmaster', 'promo', 'marketing', 'notification', 'digest',
        'your order', 'shipping confirmation', 'delivery notification',
        'account update', 'password reset', 'verify your', 'confirm your',
        'sale ends', 'limited time', 'act now', 'free shipping',
        'click here to', 'opt out', 'manage preferences', 'your receipt',
        'order confirmation', 'your subscription', 'your invoice',
        'save up to', '% off', 'coupon', 'discount code', 'deal of the day',
        'flash sale', 'clearance', 'buy now', 'shop now', 'view in browser',
        'trouble viewing', 'images not showing', 'add us to your address',
        'email preferences', 'manage subscriptions', 'update preferences',
    ]
    for kw in spam_keywords:
        if kw in sender_lower or kw in subj_lower:
            return True

    # Additional bulk-sender domains found in jeeproject@yahoo.com inbox
    more_spam_domains = {
        'donaldtrump.com', 'newyorktimesinfo.com', 'surveyallstars.com',
        'sothebys.com', 'learni.st', 'investigativemanagement.com',
        'bradfordexchange.com', 'yahoo.net', 'creditassistedbenefit.com',
        'citrix.com', 'advisorshomecare.com', 'dailynewsdirect.com',
        'rnchq.com', 'adverzines.com', 'f1000.com', 'f1000biology.com',
        'airsquirrels.com', 'nahmadcontemporary.com', 'thehustle.co',
        'topfinancetips.org', 'moneyresourcenow.com', 'webshop-expert.com',
        'findnewstory.com', 'infostormdaily.com', 'themoodbooster.com',
        'housingbenefitsllc.org', 'theconservativecause.com',
        'seniorslivingways.com', 'homewaffle.com', 'assistance-programs.org',
        'nadinejohnson.com', 'senior-advice.com', 'issuewatchdaily.com',
        'sharefile.com', 'victory.donaldtrump.com', 'em.sothebys.com',
        'spotifymail.com', 'communications.yahoo.com',
    }
    if m:
        if base in more_spam_domains or domain in more_spam_domains:
            return True
        for sd in more_spam_domains:
            if domain.endswith('.' + sd):
                return True

    # Check for URL-heavy bodies (commercial emails)
    if body:
        url_count = body_lower.count('http')
        if url_count > 3:
            return True
        # Check for tracking pixel patterns
        if 'click.php' in body_lower or 'track.' in body_lower:
            return True
        # Check for common bulk-mail signatures
        if 'view in browser' in body_lower or 'view this email' in body_lower:
            return True
        if 'email preferences' in body_lower or 'manage your' in body_lower:
            return True

    # Check if addressed to "Jodi" (not Epstein, different inbox user)
    if 'jodi' in subj_lower and any(x in subj_lower for x in ['save', 'offer', 'eligible', 'approved', 'protect', 'available']):
        return True

    return False


def get_email_body(msg):
    if msg.is_multipart():
        text_part = None
        html_part = None
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain' and not text_part:
                try:
                    text_part = part.get_content()
                except:
                    pass
            elif ct == 'text/html' and not html_part:
                try:
                    html_part = part.get_content()
                except:
                    pass
        if text_part:
            return text_part
        if html_part:
            return clean_html(html_part)
        return ''
    else:
        try:
            content = msg.get_content()
            if msg.get_content_type() == 'text/html':
                return clean_html(content)
            return content
        except:
            return ''


def ingest_yahoo_eml(conn):
    """Ingest Yahoo .eml files, filtering spam."""
    eml_dir = DATASETS_DIR / "epstein-archive" / "data" / "emails" / "jeeproject_yahoo"
    if not eml_dir.exists():
        print(f"  Skipping: {eml_dir} not found")
        return 0, 0

    existing = set(r[0] for r in conn.execute("SELECT content_hash FROM emails").fetchall())
    count = 0
    spam_count = 0
    err_count = 0

    eml_files = sorted(eml_dir.glob("*.eml"))
    for eml_path in eml_files:
        try:
            with open(eml_path, 'rb') as f:
                msg = email_mod.message_from_binary_file(f, policy=policy.default)

            sender = str(msg.get('From', ''))
            to_addr = str(msg.get('To', ''))
            subject = str(msg.get('Subject', ''))
            date_str = str(msg.get('Date', ''))
            cc = str(msg.get('Cc', '') or '')

            body = get_email_body(msg)
            if not body or len(body.strip()) < 20:
                continue

            if is_spam_email(sender, subject, body):
                spam_count += 1
                continue

            ch = content_hash(body)
            if ch in existing:
                continue
            existing.add(ch)

            conn.execute("""
                INSERT INTO emails (source_dataset, source_doc_id, from_address, to_address,
                    other_recipients, subject, timestamp_raw, timestamp_iso, body_text, body_html,
                    content_hash, thread_id, message_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'ddosecrets_yahoo',
                eml_path.name,
                sender,
                to_addr,
                cc,
                subject,
                date_str,
                '',
                body.strip(),
                '',
                ch,
                '',
                0
            ))
            count += 1
        except Exception as e:
            err_count += 1

    conn.commit()
    if err_count:
        print(f"  Parse errors: {err_count}")
    return count, spam_count


def ingest_barak_emails(conn):
    """Ingest Ehud Barak email HTML files with .eml.meta JSON metadata."""
    barak_dir = DATASETS_DIR / "epstein-archive" / "data" / "emails" / "ehud_barak_emails"
    if not barak_dir.exists():
        print(f"  Skipping: {barak_dir} not found")
        return 0

    existing = set(r[0] for r in conn.execute("SELECT content_hash FROM emails").fetchall())
    count = 0

    # Build metadata lookup from .eml.meta files
    meta_lookup = {}
    for meta_path in barak_dir.glob("*.eml.meta"):
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            doc_id = meta.get('id', '')
            meta_lookup[doc_id] = meta
        except:
            pass

    # Process HTML files
    for html_path in sorted(barak_dir.glob("*.html")):
        try:
            # Extract doc ID from filename (leading digits)
            m = re.match(r'^(\d+)', html_path.name)
            doc_id = int(m.group(1)) if m else 0

            with open(html_path, 'r', errors='replace') as f:
                html_content = f.read()

            body = clean_html(html_content)
            if not body or len(body.strip()) < 20:
                continue

            ch = content_hash(body)
            if ch in existing:
                continue
            existing.add(ch)

            # Try to get metadata
            meta = meta_lookup.get(doc_id, {})
            sender = meta.get('sender', '')
            subject = meta.get('subject', html_path.stem)
            date_raw = str(meta.get('date', ''))

            conn.execute("""
                INSERT INTO emails (source_dataset, source_doc_id, from_address, to_address,
                    other_recipients, subject, timestamp_raw, timestamp_iso, body_text, body_html,
                    content_hash, thread_id, message_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'ehud_barak',
                html_path.name,
                sender,
                'jeeproject@yahoo.com',
                '',
                subject,
                date_raw,
                '',
                body.strip(),
                html_content,
                ch,
                '',
                0
            ))
            count += 1
        except:
            pass

    # Also process .eml files
    for eml_path in sorted(barak_dir.glob("*.eml")):
        if eml_path.name.endswith('.eml.meta'):
            continue
        try:
            with open(eml_path, 'rb') as f:
                msg = email_mod.message_from_binary_file(f, policy=policy.default)

            body = get_email_body(msg)
            if not body or len(body.strip()) < 20:
                continue

            ch = content_hash(body)
            if ch in existing:
                continue
            existing.add(ch)

            conn.execute("""
                INSERT INTO emails (source_dataset, source_doc_id, from_address, to_address,
                    other_recipients, subject, timestamp_raw, timestamp_iso, body_text, body_html,
                    content_hash, thread_id, message_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'ehud_barak',
                eml_path.name,
                str(msg.get('From', '')),
                str(msg.get('To', '')),
                str(msg.get('Cc', '') or ''),
                str(msg.get('Subject', '')),
                str(msg.get('Date', '')),
                '',
                body.strip(),
                '',
                ch,
                '',
                0
            ))
            count += 1
        except:
            pass

    conn.commit()
    return count


def ingest_theelderemo(conn):
    """Ingest the theelderemo FULL_EPSTEIN_INDEX CSV into documents table."""
    csv_path = DATASETS_DIR / "theelderemo_FULL_EPSTEIN_INDEX.csv"
    if not csv_path.exists():
        print(f"  Skipping: {csv_path} not found")
        return 0

    df = pd.read_csv(csv_path)
    existing = set(r[0] for r in conn.execute("SELECT content_hash FROM documents").fetchall())
    count = 0

    for _, row in df.iterrows():
        text = str(row.get('text', ''))
        if len(text) < 20:
            continue

        ch = content_hash(text[:2000])
        if ch in existing:
            continue
        existing.add(ch)

        doc_id = str(row.get('id', ''))

        conn.execute("""
            INSERT INTO documents (source_dataset, doc_id, category, summary, full_text,
                date_earliest, date_latest, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('theelderemo', doc_id, '', '', text, '', '', ch))
        count += 1

    conn.commit()
    return count


def create_fts(conn):
    """Create full-text search indexes."""
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
            from_address, to_address, subject, body_text,
            content=emails, content_rowid=id
        );
        INSERT INTO emails_fts(emails_fts) VALUES('rebuild');

        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            doc_id, summary, full_text,
            content=documents, content_rowid=id
        );
        INSERT INTO documents_fts(documents_fts) VALUES('rebuild');
    """)

def main():
    db_path = Path(DB_PATH)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))

    print("Creating schema...")
    create_schema(conn)

    print("Ingesting HF Parquet (to-be/epstein-emails)...")
    n = ingest_hf_parquet(conn)
    print(f"  Added {n} unique emails")

    print("Ingesting thread dataset (notesbymuneeb)...")
    n = ingest_threads(conn)
    print(f"  Added {n} new unique emails (after dedup)")

    print("Ingesting doc-explorer (documents + triples)...")
    nd, nt = ingest_doc_explorer(conn)
    print(f"  Added {nd} unique documents, {nt} triples")

    # NOTE: jeeproject@yahoo.com inbox is ~99% spam/commercial.
    # Only ~30 emails are from real people; rest are marketing/scams.
    # Skipping by default - the substantive Epstein emails are in House Oversight datasets.
    # Uncomment to include:
    # print("Ingesting Yahoo .eml files (DDoSecrets/jeeproject)...")
    # n_yahoo, n_spam = ingest_yahoo_eml(conn)
    # print(f"  Added {n_yahoo} unique emails (filtered {n_spam} spam)")

    print("Ingesting Ehud Barak emails...")
    n_barak = ingest_barak_emails(conn)
    print(f"  Added {n_barak} unique emails")

    print("Ingesting theelderemo FULL_EPSTEIN_INDEX...")
    n_elder = ingest_theelderemo(conn)
    print(f"  Added {n_elder} unique documents")

    print("Building FTS indexes...")
    create_fts(conn)

    # Stats
    email_count = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    triple_count = conn.execute("SELECT COUNT(*) FROM triples").fetchone()[0]
    entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]

    print(f"\n=== UNIFIED DATABASE BUILT ===")
    print(f"  Emails: {email_count}")
    print(f"  Documents: {doc_count}")
    print(f"  RDF Triples: {triple_count}")
    print(f"  Entities: {entity_count}")
    print(f"  Location: {db_path}")

    conn.close()

if __name__ == "__main__":
    main()
