"""
SQLite database for 量科网 historical scraping.
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'historical.db')

engine = create_engine(f'sqlite:///{DB_PATH}', pool_pre_ping=True, echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Article(Base):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_type = Column(String(20), nullable=False, default='news')  # news, flash, reference
    liangke_url = Column(String(1000), nullable=False)
    liangke_id = Column(String(50), nullable=False, index=True)  # numeric ID from URL
    title = Column(String(500), nullable=False)
    content = Column(Text)
    reference_url = Column(String(1000))
    reference_title = Column(String(200))
    source_domain = Column(String(200))
    published_at = Column(DateTime)  # precise publish time from liangke_id timestamp
    category = Column(String(100))  # e.g. 量子计算, 量子通信
    area = Column(String(50))  # 国内, 国际
    tags = Column(JSON)
    # Tracking
    list_scraped_at = Column(DateTime, default=datetime.now)
    detail_fetched_at = Column(DateTime)
    fetch_status = Column(String(20), default='listed')  # listed, detailed, failed
    __table_args__ = (
        UniqueConstraint('article_type', 'liangke_id', name='uix_type_id'),
    )


class ScrapeProgress(Base):
    """Tracks scraping progress per list type so we can resume."""
    __tablename__ = 'scrape_progress'

    id = Column(Integer, primary_key=True)
    list_type = Column(String(20), nullable=False, unique=True)  # news, flash, reference
    current_page = Column(Integer, default=0)
    total_articles = Column(Integer, default=0)
    last_scraped_at = Column(DateTime, default=datetime.now)
    finished = Column(Integer, default=0)  # 0/1


Base.metadata.create_all(engine)


def get_session():
    return Session()


def get_or_create_progress(list_type: str) -> ScrapeProgress:
    session = get_session()
    try:
        p = session.query(ScrapeProgress).filter_by(list_type=list_type).first()
        if not p:
            p = ScrapeProgress(list_type=list_type)
            session.add(p)
            session.commit()
            session.refresh(p)
        return p
    finally:
        session.close()


def update_progress(list_type: str, page: int, total: int, finished: bool = False):
    session = get_session()
    try:
        p = session.query(ScrapeProgress).filter_by(list_type=list_type).first()
        if p:
            p.current_page = page
            p.total_articles = total
            p.last_scraped_at = datetime.now()
            p.finished = 1 if finished else 0
            session.commit()
    finally:
        session.close()


def insert_list_article(article_type, liangke_url, liangke_id, title, category, area, liangke_date=None):
    session = get_session()
    try:
        existing = session.query(Article).filter_by(article_type=article_type, liangke_id=liangke_id).first()
        if existing:
            return {'action': 'exists', 'id': existing.id}
        a = Article(
            article_type=article_type,
            liangke_url=liangke_url,
            liangke_id=liangke_id,
            title=title,
            category=category,
            area=area,
            fetch_status='listed',
        )
        session.add(a)
        session.commit()
        return {'action': 'inserted', 'id': a.id}
    except Exception as e:
        session.rollback()
        return {'action': 'error', 'error': str(e)}
    finally:
        session.close()


def get_articles_without_detail(article_type=None, limit=100):
    session = get_session()
    try:
        q = session.query(Article).filter(Article.fetch_status == 'listed')
        if article_type:
            q = q.filter(Article.article_type == article_type)
        return q.limit(limit).all()
    finally:
        session.close()


def update_article_detail(liangke_id, article_type, content, reference_url, reference_title, source_domain, tags):
    session = get_session()
    try:
        a = session.query(Article).filter_by(article_type=article_type, liangke_id=liangke_id).first()
        if a:
            a.content = content
            a.reference_url = reference_url
            a.reference_title = reference_title
            a.source_domain = source_domain
            a.tags = tags
            a.detail_fetched_at = datetime.now()
            a.fetch_status = 'detailed'
            session.commit()
            return {'action': 'updated', 'id': a.id}
        return {'action': 'not_found'}
    except Exception as e:
        session.rollback()
        return {'action': 'error', 'error': str(e)}
    finally:
        session.close()


def get_counts():
    session = get_session()
    try:
        total = session.query(Article).count()
        detailed = session.query(Article).filter(Article.fetch_status == 'detailed').count()
        listed = session.query(Article).filter(Article.fetch_status == 'listed').count()
        failed = session.query(Article).filter(Article.fetch_status == 'failed').count()
        return {'total': total, 'detailed': detailed, 'listed': listed, 'failed': failed}
    finally:
        session.close()


if __name__ == '__main__':
    print(f'SQLite DB ready at: {DB_PATH}')
    counts = get_counts()
    print(f'Articles: {counts}')
