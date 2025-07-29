import requests
import sqlite3
from bs4 import BeautifulSoup
import time

RSS_FEED_URL = "https://www.sec.gov/news/pressreleases.rss"
DB_PATH = "sec_articles.db"


def init_db():
    """Initialize SQLite database and create table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sec_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            pub_date TEXT,
            html TEXT,
            clean_text TEXT
        );
    """)
    conn.commit()
    conn.close()


def fetch_rss_articles():
    """Fetch all items in RSS feed."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SECDataFetcher/1.0; +https://yourdomain.com/contact)"
    }
    resp = requests.get(RSS_FEED_URL, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "xml")

    items = soup.find_all("item")
    articles = []
    for item in items:
        title = item.title.text.strip()
        link = item.link.text.strip()
        pub_date = item.pubDate.text.strip()
        articles.append((title, link, pub_date))
    return articles


def fetch_article_content(url):
    """Download HTML and extract clean body text."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SECDataFetcher/1.0; +https://yourdomain.com/contact)"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("div", class_="field--name-body")

    if not body:
        return html, ""

    clean_text = "\n\n".join(p.get_text(strip=True) for p in body.find_all(["p", "li"]))
    return html, clean_text


def save_article_to_db(title, link, pub_date, html, clean_text):
    """Insert article data into the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO sec_articles (title, link, pub_date, html, clean_text)
            VALUES (?, ?, ?, ?, ?);
        """, (title, link, pub_date, html, clean_text))
        conn.commit()
        print(f"✅ Saved: {title}")
    except sqlite3.IntegrityError:
        print(f"⚠️ Already in DB: {title}")
    finally:
        conn.close()


def main():
    init_db()
    articles = fetch_rss_articles()

    for title, link, pub_date in articles:
        print(f"🔗 Processing: {title}")
        try:
            html, clean_text = fetch_article_content(link)
            save_article_to_db(title, link, pub_date, html, clean_text)
            time.sleep(1.5)  # Respect SEC rate limits
        except Exception as e:
            print(f"❌ Error with {link}: {e}")


if __name__ == "__main__":
    main()