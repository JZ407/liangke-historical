"""
LLM batch tag 2,839 v3-only articles in historical_final.db.
"""
import sys, os, json, time, sqlite3, yaml

sys.path.insert(0, 'D:/Claude_code/rag_system/rag_system')
from llm_client import LLMClient

DB_PATH = 'D:/Claude_code/liangke_historical/historical_final.db'
CONFIG_PATH = 'D:/Claude_code/rag_system/config.yaml'
BATCH_SIZE = 20
DELAY = 3.0

TAGS_LIST = [
    '量子计算', '科技前沿', '产品动态', '量子通信', '行业应用',
    '企业与机构', '硬件平台', '融资商业', '宏观态势', 'AI/ML',
    '半导体', '量子物理', '后量子密码', '融资', 'PQC', 'QKD',
    '量子纠错', '超导', 'NIST', '量子传感', '企业资讯',
    '光量子', '资本运作', '离子阱', '政策标准', '后量子迁移', 'arXiv',
]


def load_llm():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)['llm']
    return LLMClient(
        provider='openai',
        api_key=cfg['api_key'],
        api_base=cfg['api_base'],
        model=cfg['model'],
        temperature=cfg.get('temperature') if cfg.get('temperature') else 1,
        max_tokens=2048,
        timeout=60,
    )


def tag_batch(client, articles):
    """Tag a batch of articles via LLM."""
    prompt_lines = [
        f'从以下标签中为每篇文章选择1-4个最相关的标签：{", ".join(TAGS_LIST)}',
        '输出格式：序号|标签1,标签2,标签3',
        '',
    ]
    for i, (title, content) in enumerate(articles, 1):
        snippet = (content or '')[:200].replace('\n', ' ')
        prompt_lines.append(f'{i}. {title} | {snippet}')

    messages = [
        {'role': 'system', 'content': '你是量子科技新闻分类专家。只输出要求的格式，不要解释。'},
        {'role': 'user', 'content': '\n'.join(prompt_lines)},
    ]

    try:
        resp = client.chat(messages)
        result = {}
        for line in resp.strip().split('\n'):
            if '|' not in line:
                continue
            parts = line.split('|', 1)
            try:
                idx = int(parts[0].strip()) - 1
                tags_str = parts[1].strip()
                tags = [t.strip() for t in tags_str.split(',') if t.strip() in TAGS_LIST]
                if tags and 0 <= idx < len(articles):
                    result[idx] = tags
            except ValueError:
                continue
        return result
    except Exception as e:
        print(f'  LLM batch error: {e}')
        return {}


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get untagged articles
    cur.execute('''SELECT id, title, content FROM articles
        WHERE (tags IS NULL OR tags = "" OR tags = "[]") AND detail_fetched=1
        ORDER BY liangke_date DESC''')
    untagged = cur.fetchall()
    print(f'{len(untagged)} articles need tags')

    if not untagged:
        print('All done!')
        conn.close()
        return

    client = load_llm()
    tagged_count = 0

    for batch_start in range(0, len(untagged), BATCH_SIZE):
        batch = untagged[batch_start:batch_start + BATCH_SIZE]
        articles = [(r[1], r[2]) for r in batch]

        print(f'  Batch {batch_start//BATCH_SIZE + 1}/{(len(untagged) + BATCH_SIZE - 1)//BATCH_SIZE}: {len(batch)} articles...')
        results = tag_batch(client, articles)

        for idx, tags in results.items():
            row_id = batch[idx][0]
            cur.execute('UPDATE articles SET tags=? WHERE id=?', (json.dumps(tags), row_id))
            tagged_count += 1
        conn.commit()

        if results:
            print(f'    Tagged {len(results)} in this batch, total: {tagged_count}')
        time.sleep(DELAY)

    conn.commit()
    cur.execute('SELECT COUNT(*) FROM articles WHERE tags IS NOT NULL AND tags != "" AND tags != "[]"')
    total_tagged = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM articles')
    total = cur.fetchone()[0]
    print(f'\nDone: {total_tagged}/{total} tagged')
    conn.close()


if __name__ == '__main__':
    main()
