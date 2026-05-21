"""
量科网历史新闻列表页爬虫
用法: python scrape_list.py [news|flash|reference]
"""
import sys
import time
import re
import pickle
from datetime import date, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from db import get_or_create_progress, update_progress, insert_list_article

BASE_URL = 'http://www.qtc.com.cn'
COOKIE_PATH = './qtc_cookies.pkl'
PAGE_DELAY = 1.0  # seconds between page requests


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


def parse_relative_time(text: str) -> date:
    """Convert relative time text to approximate absolute date."""
    text = text.strip().replace(' ', '')
    today = date.today()

    # Patterns: 11分钟前, 1小时前, 23小时前, 1天前, 2天前, 1周前, 1个月前
    m = re.search(r'(\d+)\s*分钟前', text)
    if m:
        return today

    m = re.search(r'(\d+)\s*小时前', text)
    if m:
        hours = int(m.group(1))
        if hours < 24:
            return today
        return today - timedelta(days=1)

    m = re.search(r'(\d+)\s*天前', text)
    if m:
        return today - timedelta(days=int(m.group(1)))

    m = re.search(r'(\d+)\s*周前', text)
    if m:
        return today - timedelta(weeks=int(m.group(1)))

    m = re.search(r'(\d+)\s*个月前', text)
    if m:
        return today - timedelta(days=int(m.group(1)) * 30)

    if '昨天' in text:
        return today - timedelta(days=1)

    return today


def parse_date_from_id(article_id: str) -> date:
    """Extract approximate date from article ID if possible."""
    # IDs look like 177925932432449
    # First digits may encode date: 1779259324 -> possibly 2025-??
    # This is speculative; we'll rely on detail pages for precise dates.
    return None


def extract_news_list(html: str):
    """Extract articles from /news list page."""
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.find('div', class_='news-list')
    if not container:
        return []

    articles = []
    for item in container.find_all('li', class_='item'):
        a = item.find('h3', class_='title')
        if not a:
            continue
        link = a.find('a', href=True)
        if not link:
            continue

        href = link['href']
        title = link.get_text(strip=True)
        full_url = urljoin(BASE_URL, href)
        m = re.search(r'/article/(\d+)\.html', href)
        if not m:
            continue
        article_id = m.group(1)

        # Category and area
        info_span = item.find('span', class_='info')
        area = ''
        category = ''
        if info_span:
            info_text = info_span.get_text(strip=True)
            parts = [p.strip() for p in info_text.split('/') if p.strip()]
            if parts:
                area = parts[0]
            if len(parts) > 1:
                category = parts[1]

        # Relative time
        status = item.find('span', class_='status')
        time_text = ''
        if status:
            time_text = status.get_text(strip=True)
        liangke_date = parse_relative_time(time_text)

        articles.append({
            'type': 'news',
            'id': article_id,
            'url': full_url,
            'title': title,
            'category': category,
            'area': area,
            'date': liangke_date,
        })
    return articles


def extract_flash_list(html: str):
    """Extract articles from /flash list page."""
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.find('div', class_='flash-box') or soup.find('div', class_='flash-list')
    if not container:
        return []

    articles = []
    for item in container.find_all('a', href=re.compile(r'/flash/\d+\.html')):
        href = item['href']
        title = item.get_text(strip=True)
        full_url = urljoin(BASE_URL, href)
        m = re.search(r'/flash/(\d+)\.html', href)
        if not m:
            continue
        article_id = m.group(1)

        # Time is usually in a sibling span with class 'time'
        time_text = ''
        parent = item.find_parent('div', class_='item') or item.find_parent('li')
        if parent:
            time_span = parent.find('span', class_='time') or parent.find('span', class_='flash-created')
            if time_span:
                time_text = time_span.get_text(strip=True)

        liangke_date = parse_relative_time(time_text)

        articles.append({
            'type': 'flash',
            'id': article_id,
            'url': full_url,
            'title': title,
            'category': '',
            'area': '',
            'date': liangke_date,
        })
    return articles


def extract_reference_list(html: str):
    """Extract articles from /reference list page."""
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.find('div', class_='term-list') or soup.find('div', class_='item-list')
    if not container:
        return []

    articles = []
    for item in container.find_all('a', href=re.compile(r'/reference/\d+\.html')):
        href = item['href']
        title = item.get_text(strip=True)
        full_url = urljoin(BASE_URL, href)
        m = re.search(r'/reference/(\d+)\.html', href)
        if not m:
            continue
        article_id = m.group(1)

        # Time
        time_text = ''
        parent = item.find_parent('div', class_='item')
        if parent:
            time_span = parent.find('span', class_='time') or parent.find('div', class_='flash-created')
            if time_span:
                time_text = time_span.get_text(strip=True)

        liangke_date = parse_relative_time(time_text)

        articles.append({
            'type': 'reference',
            'id': article_id,
            'url': full_url,
            'title': title,
            'category': '',
            'area': '',
            'date': liangke_date,
        })
    return articles


EXTRACTORS = {
    'news': extract_news_list,
    'flash': extract_flash_list,
    'reference': extract_reference_list,
}


def scrape_list(list_type: str, max_pages: int = None):
    session = load_session()
    if not session:
        return

    progress = get_or_create_progress(list_type)
    start_page = progress.current_page
    extractor = EXTRACTORS.get(list_type)
    if not extractor:
        print(f'Unknown list type: {list_type}')
        return

    print(f'Starting {list_type} from page {start_page}')

    page = start_page
    empty_streak = 0
    dup_streak = 0
    total_inserted = 0
    prev_first_id = None

    while True:
        if max_pages is not None and page >= max_pages:
            print(f'Reached max_pages limit: {max_pages}')
            break

        url = f'{BASE_URL}/{list_type}?page={page}'
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            html = resp.text
        except Exception as e:
            print(f'Page {page}: fetch error - {e}')
            empty_streak += 1
            if empty_streak >= 5:
                print('5 consecutive fetch errors, stopping.')
                break
            time.sleep(PAGE_DELAY * 2)
            continue

        articles = extractor(html)
        if not articles:
            empty_streak += 1
            print(f'Page {page}: no articles found ({empty_streak}/5)')
            if empty_streak >= 5:
                print('5 consecutive empty pages, stopping.')
                break
        else:
            empty_streak = 0
            # Duplicate detection: if first article ID repeats for 3+ pages, stop
            first_id = articles[0]['id']
            if first_id == prev_first_id:
                dup_streak += 1
                print(f'Page {page}: first article ID repeated ({dup_streak}/3)')
                if dup_streak >= 3:
                    print('3 consecutive duplicate pages, stopping.')
                    break
            else:
                dup_streak = 0
                prev_first_id = first_id

            for a in articles:
                result = insert_list_article(
                    article_type=a['type'],
                    liangke_url=a['url'],
                    liangke_id=a['id'],
                    title=a['title'],
                    category=a['category'],
                    area=a['area'],
                )
                if result['action'] == 'inserted':
                    total_inserted += 1
            print(f'Page {page}: {len(articles)} articles, inserted {total_inserted} total')

        update_progress(list_type, page, total_inserted, finished=False)
        page += 1
        time.sleep(PAGE_DELAY)

    update_progress(list_type, page - 1, total_inserted, finished=True)
    print(f'{list_type} complete. Total inserted: {total_inserted}')


def main():
    if len(sys.argv) > 1:
        list_type = sys.argv[1]
        max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else None
        scrape_list(list_type, max_pages)
    else:
        print('Usage: python scrape_list.py [news|flash|reference] [max_pages]')
        print('Examples:')
        print('  python scrape_list.py news')
        print('  python scrape_list.py flash 100')
        print('  python scrape_list.py reference 50')


if __name__ == '__main__':
    main()
