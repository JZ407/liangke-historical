"""
Export historical_final.db articles to Excel.
"""
import os
import pandas as pd
from sqlalchemy import create_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'historical_final.db')
engine = create_engine(f'sqlite:///{DB_PATH}')

df = pd.read_sql("""
    SELECT
        article_type AS 类型,
        liangke_id AS 量科ID,
        title AS 标题,
        content AS 正文,
        reference_url AS 参考链接,
        reference_title AS 参考标题,
        source_domain AS 来源域名,
        published_at AS 量科发布时间,
        category AS 分类,
        area AS 地区,
        list_scraped_at AS 列表抓取时间,
        detail_fetched_at AS 详情抓取时间,
        fetch_status AS 状态
    FROM articles
    ORDER BY published_at DESC
""", engine)

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'historical_export_v2.xlsx')
df.to_excel(output_path, index=False, engine='openpyxl')
print(f'Exported {len(df)} rows to {output_path}')
