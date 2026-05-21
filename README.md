# 量科网历史数据抓取

量科网 (qtc.com.cn) 历史新闻全量抓取项目，用于行业趋势分析。

## 目录结构

```
liangke_historical/
├── scrape_list.py          # 列表页抓取（news/flash/reference）
├── scrape_detail.py        # 详情页抓取（内容、参考链接）
├── db.py                   # SQLite ORM 模型
├── export_historical.py    # Excel 导出
├── historical.db           # SQLite 数据库
└── requirements.txt
```

## 数据规模

- Flash: ~8,670 篇
- News: ~166 篇
- Reference: ~117 篇
- 时间跨度: 2021-11 ~ 2026-05

## 关键字段

- `published_at`: 量科网精确发布时间（从 `liangke_id` 解析，精确到分钟）
- `content`: 正文内容
- `reference_url`: 参考链接
- `source_domain`: 来源域名

## 更新日志

- 2026-05-21: 新增 `published_at` 字段，移除失效的 `original_date` 和 `liangke_date`
- 2026-05-21: 完成全部 8,953 篇文章的详情抓取
