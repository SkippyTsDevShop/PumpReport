#!/usr/bin/env python3
"""
Generate /news-sitemap.xml (Google News sitemap) for PumpReport.

Run this on every deploy (or on a schedule, e.g. hourly via a GitHub Action
or Cloudflare Pages build hook) so the file always reflects only articles
published in the last 48 hours. Re-running it is how stale articles get
"automatically removed" -- this script has no memory between runs; it
recomputes freshness from scratch, from the current system clock, every
time it's invoked.

It does NOT touch sitemap.xml -- that stays the permanent, full archive.

Usage:
    python3 generate_news_sitemap.py [--dry-run]

Exit code is 0 on success. With --dry-run, prints what would be written
without touching news-sitemap.xml.
"""
import argparse
import glob
import html as html_lib
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

SITE_ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLICATION_NAME = "PumpReport"
PUBLICATION_LANGUAGE = "en"
FRESHNESS_WINDOW_HOURS = 48

# Pages that are never eligible for the news sitemap even though they are
# real .html files in this directory: the homepage, utility/trust pages
# (no article:published_time, not editorial news), and anything explicitly
# marked as an unpublished draft.
NEVER_ELIGIBLE = {
    "index.html",
    "about.html", "advertise.html", "contact.html",
    "editorial-policy.html", "privacy-policy.html", "terms.html",
    "grow-nourish-marketplace-food-traceability.html",  # unpublished dry run -- never ships
}


def parse_published_date(date_str):
    """Parse an article:published_time value. Accepts YYYY-MM-DD or full
    ISO8601. A date-only value is treated as 00:00:00 UTC -- the start of
    that calendar day -- which is the conservative reading: we never claim
    an article is fresher than we can actually prove."""
    date_str = date_str.strip()
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_field(html, pattern):
    m = re.search(pattern, html)
    return m.group(1) if m else None


def is_eligible_article(fn, html, now_utc, cutoff_utc):
    """Apply every exclusion rule. Returns (ok, reason_if_excluded, data)."""
    # noindex check (indexability proxy -- see note in report_notes below)
    robots = extract_field(html, r'<meta name="robots" content="([^"]*)">')
    if robots and "noindex" in robots.lower():
        return False, "noindex", None

    # Must be an Article/NewsArticle per JSON-LD (excludes any non-article
    # utility page that might sneak into the article glob in the future)
    if not re.search(r'"@type":\s*"(Article|NewsArticle|BlogPosting)"', html):
        return False, "no Article/NewsArticle JSON-LD (not an editorial article)", None

    # Canonical URL -- required, and must be extensionless (no old .html URLs)
    canonical = extract_field(html, r'<link rel="canonical" href="(https://[^"]+)">')
    if not canonical:
        return False, "no canonical URL", None
    if canonical.endswith(".html"):
        return False, "canonical is an old .html URL", None

    # Publication date -- required and parseable
    pub_raw = extract_field(html, r'<meta property="article:published_time" content="([^"]+)">')
    if not pub_raw:
        return False, "no article:published_time", None
    pub_dt = parse_published_date(pub_raw)
    if pub_dt is None:
        return False, f"unparseable publication date: {pub_raw!r}", None

    # 48-hour freshness window
    if pub_dt < cutoff_utc:
        age_hours = (now_utc - pub_dt).total_seconds() / 3600
        return False, f"published {age_hours:.1f}h ago (outside {FRESHNESS_WINDOW_HOURS}h window)", None

    # Title -- required
    title_raw = extract_field(html, r"<title>(.*?)</title>")
    if not title_raw:
        return False, "no <title>", None
    # Strip the site suffix (" | PumpReport") for the news:title value --
    # Google News wants the article headline, not the branded page title.
    # Source HTML may contain HTML entities (e.g. &amp;) in the raw text;
    # decode them to plain Unicode here so ElementTree's own XML escaping
    # on output is the only escaping applied (avoids double-escaping).
    title = re.sub(r"\s*\|\s*PumpReport\s*$", "", title_raw).strip()
    title = html_lib.unescape(title)

    # Sponsored-content check: this site runs no sponsored content until it
    # independently qualifies as genuine editorial news (site policy), and
    # none currently exists. Defensive check for a future marker so this
    # script keeps working correctly if that changes.
    if re.search(r'data-sponsored=["\']true["\']', html, re.I):
        if "data-editorial-qualified=\"true\"" not in html:
            return False, "sponsored content not independently editorial-qualified", None

    return True, None, {
        "loc": canonical,
        "title": title,
        "pub_date": pub_raw if "T" not in pub_raw else pub_dt.date().isoformat(),
    }


def build_news_sitemap(entries):
    urlset = ET.Element("urlset", {
        "xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "xmlns:news": "http://www.google.com/schemas/sitemap-news/0.9",
    })
    for e in entries:
        url = ET.SubElement(urlset, "url")
        loc = ET.SubElement(url, "loc")
        loc.text = e["loc"]
        news = ET.SubElement(url, "news:news")
        pub = ET.SubElement(news, "news:publication")
        name = ET.SubElement(pub, "news:name")
        name.text = PUBLICATION_NAME
        lang = ET.SubElement(pub, "news:language")
        lang.text = PUBLICATION_LANGUAGE
        pubdate = ET.SubElement(news, "news:publication_date")
        pubdate.text = e["pub_date"]
        title = ET.SubElement(news, "news:title")
        title.text = e["title"]

    ET.indent(urlset, space="  ")
    xml_bytes = ET.tostring(urlset, encoding="UTF-8", xml_declaration=True)
    return xml_bytes.decode("utf-8") + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--now", help="Override current UTC time, ISO8601 (for testing)")
    args = parser.parse_args()

    now_utc = datetime.now(timezone.utc)
    if args.now:
        now_utc = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=FRESHNESS_WINDOW_HOURS)

    os.chdir(SITE_ROOT)
    files = sorted(glob.glob("*.html"))

    included = []
    excluded = []
    seen_locs = set()

    for fn in files:
        if fn in NEVER_ELIGIBLE:
            continue
        html = open(fn, encoding="utf-8").read()
        ok, reason, data = is_eligible_article(fn, html, now_utc, cutoff_utc)
        if not ok:
            excluded.append((fn, reason))
            continue
        if data["loc"] in seen_locs:
            excluded.append((fn, f"duplicate canonical URL: {data['loc']}"))
            continue
        seen_locs.add(data["loc"])
        included.append(data)

    included.sort(key=lambda e: e["pub_date"], reverse=True)

    xml_str = build_news_sitemap(included)

    # Validate well-formedness before writing
    ET.fromstring(xml_str)

    print(f"Now (UTC):    {now_utc.isoformat()}")
    print(f"Cutoff (UTC): {cutoff_utc.isoformat()}  (now - {FRESHNESS_WINDOW_HOURS}h)")
    print(f"\nIncluded ({len(included)}):")
    for e in included:
        print(f"  {e['pub_date']}  {e['loc']}")
    print(f"\nExcluded ({len(excluded)}):")
    for fn, reason in excluded:
        print(f"  {fn}: {reason}")

    if args.dry_run:
        print("\n--dry-run: not writing news-sitemap.xml")
        print(xml_str)
        return 0

    with open(os.path.join(SITE_ROOT, "news-sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"\nWrote news-sitemap.xml with {len(included)} article(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
