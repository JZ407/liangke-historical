"""
Merge historical v2 + v3 into historical_final.db.

Step 1: Copy v3 as base
Step 2: Migrate tags from v2 for overlapping articles
Step 3: Import v2-only articles (not in v3)
Step 4: Report stats on v3-only articles (need LLM tagging)
"""
import sqlite3, shutil, os, json

V2_PATH = 'D:/Claude_code/liangke_historical/historical_v2.db'
V3_PATH = 'D:/Claude_code/liangke_historical/historical_v3.db'
FINAL_PATH = 'D:/Claude_code/liangke_historical/historical_final.db'


def main():
    # Step 1: Copy v3 as base
    print('Step 1: Copying v3 as base...')
    if os.path.exists(FINAL_PATH):
        os.remove(FINAL_PATH)
    shutil.copy2(V3_PATH, FINAL_PATH)
    conn = sqlite3.connect(FINAL_PATH)
    cur = conn.cursor()

    # Ensure tags column exists
    cur.execute("PRAGMA table_info(articles)")
    cols = [r[1] for r in cur.fetchall()]
    if 'tags' not in cols:
        cur.execute('ALTER TABLE articles ADD COLUMN tags TEXT')
        conn.commit()

    # Step 2: Migrate tags from v2 for overlapping articles
    print('Step 2: Migrating tags from v2...')
    conn2 = sqlite3.connect(V2_PATH)
    # Get v2 tags: (article_type, liangke_id) -> tags
    v2_tags = {}
    for row in conn2.execute('SELECT article_type, liangke_id, tags FROM articles WHERE tags IS NOT NULL'):
        v2_tags[(row[0], row[1])] = row[2]
    conn2.close()

    tag_migrated = 0
    for (art_type, art_id), tags in v2_tags.items():
        cur.execute(
            'UPDATE articles SET tags=? WHERE article_type=? AND liangke_id=? AND (tags IS NULL OR tags="")',
            (tags, art_type, art_id)
        )
        if cur.rowcount > 0:
            tag_migrated += 1
    conn.commit()
    print(f'  Migrated tags: {tag_migrated} articles')

    # Step 3: Import v2-only articles
    print('Step 3: Importing v2-only articles...')
    # Get v3 IDs
    v3_ids = set()
    for row in cur.execute('SELECT article_type, liangke_id FROM articles'):
        v3_ids.add((row[0], row[1]))

    conn2 = sqlite3.connect(V2_PATH)
    imported = 0
    for row in conn2.execute(
        'SELECT article_type, liangke_url, liangke_id, title, content, reference_url, liangke_date, tags, dedup_status FROM articles WHERE detail_fetched=1'
    ):
        art_type, liangke_url, liangke_id, title, content, ref_url, date, tags, dedup = row
        if (art_type, liangke_id) in v3_ids:
            continue
        cur.execute(
            '''INSERT INTO articles (article_type, liangke_url, liangke_id, title, content, reference_url, liangke_date, tags, detail_fetched, dedup_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)''',
            (art_type, liangke_url, liangke_id, title, content, ref_url, date, tags, dedup)
        )
        imported += 1
    conn2.close()
    conn.commit()
    print(f'  Imported: {imported} v2-only articles')

    # Step 4: Stats
    cur.execute('SELECT COUNT(*) FROM articles')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM articles WHERE tags IS NOT NULL AND tags != "" AND tags != "[]"')
    tagged = cur.fetchone()[0]
    cur.execute('SELECT article_type, COUNT(*) FROM articles GROUP BY article_type')
    types = cur.fetchall()
    cur.execute('SELECT MIN(liangke_date), MAX(liangke_date) FROM articles WHERE liangke_date != ""')
    dates = cur.fetchone()

    print(f'\n===== Final DB Stats =====')
    print(f'Total: {total}')
    print(f'With tags: {tagged}/{total}')
    print(f'Need LLM tagging: {total - tagged}')
    for t, c in types:
        print(f'  {t}: {c}')
    print(f'Date range: {dates[0]} ~ {dates[1]}')

    conn.close()
    print(f'\nSaved to {FINAL_PATH}')


if __name__ == '__main__':
    main()
