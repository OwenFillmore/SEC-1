# sec_full_scraper.py
import requests
import sqlite3
import time
from bs4 import BeautifulSoup

DB_PATH = "sec_articles.db"
USER_AGENT = "Mozilla/5.0 (compatible; SECDataFetcher/1.0; +https://yourdomain.com/contact)"
BASE_URL = "https://www.sec.gov"

# Feeds with archive pages only (explicitly scoped)
FEEDS = {
    "press_release": "https://www.sec.gov/newsroom/press-releases",
}

# Set maximum page number to stop after reaching last known page
MAX_PAGE = 146

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sec_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            pub_date TEXT,
            html TEXT,
            clean_text TEXT,
            feed_type TEXT
        );
    """)
    conn.commit()
    conn.close()

def is_url_in_db(link):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sec_articles WHERE link = ?", (link,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists

def fetch_article_html_and_text(link):
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(link, headers=headers, timeout=15)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    body_div = soup.find("div", class_="field--name-body")
    clean_text = ""
    if body_div:
        clean_text = "\n\n".join(p.get_text(strip=True) for p in body_div.find_all(["p", "li"]))
    return html, clean_text

def save_article_to_db(title, link, pub_date, html, clean_text, feed_type):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO sec_articles (title, link, pub_date, html, clean_text, feed_type)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (title, link, pub_date, html, clean_text, feed_type))
        conn.commit()
        print(f"✅ Saved [{feed_type}]: {title}")
    except sqlite3.IntegrityError:
        print(f"⚠️ Already in DB: {link}")
    finally:
        conn.close()

def scrape_archive(feed_type, base_url):
    print(f"\n📄 Crawling archive for: {feed_type}")
    page = 0
    while page <= MAX_PAGE:
        print(f"🔍 Scanning page {page} of {feed_type}...")
        url = base_url if page == 0 else f"{base_url}?page={page}"
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            all_links = [BASE_URL + a["href"] for a in soup.select("a[href^='/newsroom/']")]
            links = [
                link for link in all_links
                if f"/{feed_type.replace('_', '-')}" in link and link != base_url
            ]
        except Exception as e:
            print(f"❌ Error fetching page {page} of {feed_type}: {e}")
            break

        new_links = [link for link in links if not is_url_in_db(link)]
        if not new_links:
            print(f"⚠️ Page {page} has no new articles.")
        else:
            for link in new_links:
                try:
                    html, clean_text = fetch_article_html_and_text(link)
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.find("h1").text.strip()
                    pub_tag = soup.find("time")
                    pub_date = pub_tag.text.strip() if pub_tag else "Unknown"
                    save_article_to_db(title, link, pub_date, html, clean_text, feed_type)
                    time.sleep(1.5)
                except Exception as e:
                    print(f"❌ Error scraping article {link}: {e}")

        page += 1
        time.sleep(2)

def main():
    init_db()
    for feed_type, archive_url in FEEDS.items():
        scrape_archive(feed_type, archive_url)

if __name__ == "__main__":
    main()
