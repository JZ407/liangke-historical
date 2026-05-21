"""
量科网历史详情页爬虫 - 补充文章内容和参考链接
用法: python scrape_detail.py [news|flash|reference] [batch_size]
"""
import sys
import time
import pickle
import re
from datetime import date
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from db import get_articles_without_detail, update_article_detail

BASE_URL = 'http://www.qtc.com.cn'
COOKIE_PATH = './qtc_cookies.pkl'
REQUEST_DELAY = 1.5  # seconds between detail page requests


def load_session():
    session = requests.Session()
    try:
        with open(COOKIE_PATH, 'rb') as f:
            cookies = pickle.load(f)
    except Exception as e:
        print(f'Cookie load failed: {e}')
        return None

    if isinstance(cookies, dict):
        for k, v in cookies.items():
            session.cookies.set(k, v)
    else:
        for c in cookies:
            session.cookies.set(c['name'], c['value'], domain=c.get('domain'), path=c.get('path'))

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': BASE_URL + '/',
    })
    return session


def extract_original_date(html: str, url: str) -> date:
    """Extract original publication date from external reference page HTML."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception:
        return None

    # 1. Open Graph article:published_time
    meta = soup.find('meta', property='article:published_time')
    if meta and meta.get('content'):
        d = _parse_date(meta['content'])
        if d:
            return d

    # 2. Open Graph updated_time
    meta = soup.find('meta', property='og:updated_time')
    if meta and meta.get('content'):
        d = _parse_date(meta['content'])
        if d:
            return d

    # 3. meta name=date / pubdate
    for name in ['date', 'pubdate', 'publish-date', 'article:published_time']:
        meta = soup.find('meta', attrs={'name': name})
        if meta and meta.get('content'):
            d = _parse_date(meta['content'])
            if d:
                return d

    # 4. <time datetime="...">
    time_tag = soup.find('time')
    if time_tag and time_tag.get('datetime'):
        d = _parse_date(time_tag['datetime'])
        if d:
            return d

    # 5. JSON-LD datePublished
    for script in soup.find_all('script', type='application/ld+json'):
        text = script.string or ''
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', text)
        if m:
            d = _parse_date(m.group(1))
            if d:
                return d

    # 6. URL pattern /YYYY/MM/DD/ or /YYYY/M/D/
    path = urlparse(url).path
    m = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', path)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    return None


def _parse_date(text: str) -> date:
    """Parse various date formats to date object."""
    if not text:
        return None
    text = text.strip()[:10]
    patterns = [
        r'(\d{4})-(\d{2})-(\d{2})',
        r'(\d{4})/(\d{2})/(\d{2})',
        r'(\d{4})\.(\d{2})\.(\d{2})',
    ]
    for pat in patterns:
        m = re.match(pat, text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
    return None


def fetch_detail(session, url: str) -> str:
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as e:
        print(f'  Fetch error: {e}')
        return None


def parse_article_detail(html: str, url: str, article_type: str, session=None):
    """Parse article detail page. Returns dict with content, reference_url, etc."""
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    is_reference = article_type == 'reference'

    # Title
    title = ''
    if is_reference:
        h2 = soup.find('h2')
        if h2:
            title = h2.get_text(strip=True)
    else:
        h1 = soup.find('h1', class_='page-header')
        if h1:
            title = h1.get_text(strip=True)
    if not title:
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split('|')[0].strip()

    # Content
    content = ''
    if is_reference:
        content_div = soup.find('div', class_='refer-txt')
    else:
        content_div = soup.find('div', class_='content')
    if content_div:
        # Remove script, style
        for tag in content_div.find_all(['script', 'style']):
            tag.decompose()
        content = content_div.get_text(separator='\n', strip=True)

    # Reference link
    reference_url = ''
    reference_title = ''
    if is_reference:
        ref_a = soup.find('a', text=re.compile(r'参考来源'))
    else:
        ref_a = soup.find('a', text=re.compile(r'参考链接|参考来源'))
    if ref_a and ref_a.get('href'):
        reference_url = ref_a['href'].strip()
        reference_title = ref_a.get_text(strip=True)
        if reference_url.startswith('/'):
            reference_url = urljoin(BASE_URL, reference_url)

    source_domain = ''
    if reference_url:
        source_domain = urlparse(reference_url).netloc

    return {
        'title': title,
        'content': content,
        'reference_url': reference_url,
        'reference_title': reference_title,
        'source_domain': source_domain,
    }


def scrape_details(article_type: str = None, batch_size: int = 50):
    session = load_session()
    if not session:
        return

    processed = 0
    failed = 0

    while True:
        articles = get_articles_without_detail(article_type, batch_size)
        if not articles:
            print('No more articles to process.')
            break

        for article in articles:
            print(f'[{article.id}] {article.liangke_url}')
            html = fetch_detail(session, article.liangke_url)
            if not html:
                failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            try:
                detail = parse_article_detail(html, article.liangke_url, article.article_type, session)
            except Exception as e:
                print(f'  Parse error: {e}')
                failed += 1
                time.sleep(REQUEST_DELAY)
                continue
            if not detail:
                failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            update_article_detail(
                liangke_id=article.liangke_id,
                article_type=article.article_type,
                content=detail['content'],
                reference_url=detail['reference_url'],
                reference_title=detail['reference_title'],
                source_domain=detail['source_domain'],
                tags=[],
            )
            processed += 1
            time.sleep(REQUEST_DELAY)

        print(f'Batch complete. Processed: {processed}, Failed: {failed}')

    print(f'Done. Total processed: {processed}, Failed: {failed}')


def main():
    article_type = sys.argv[1] if len(sys.argv) > 1 else None
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    scrape_details(article_type, batch_size)


if __name__ == '__main__':
    main()
