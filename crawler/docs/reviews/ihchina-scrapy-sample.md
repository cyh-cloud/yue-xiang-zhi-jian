# ihchina Scrapy 小样本验证

日期: 2026-10-21

结果: succeeded

## 列表

- URL: `https://www.ihchina.cn/getProject.html?province=&rx_time=&type=&cate=&keywords=&category_id=16&limit=5&p=1`
- 取得时间: `2026-10-21T03:36:52+08:00`
- HTTP: `200`
- Content-Type: `application/json; charset=utf-8`
- 响应字节: 23732
- SHA-256: `ccc154890691354db8e8a7eafecddbae9faa642e30e04ef717a837358eae5853`
- total: 3610
- count: 3610
- list 条数: 5
- 样本 ID: `12178`、`12177`、`12179`、`23632`、`12180`

## 详情

| source_item_id | HTTP | 字节 | 字段数 |
| --- | ---: | ---: | ---: |
| 12178 | 200 | 40312 | 8 |
| 12177 | 200 | 38985 | 8 |
| 12179 | 200 | 36167 | 8 |
| 23632 | 200 | 35605 | 8 |
| 12180 | 200 | 36462 | 8 |

5 个详情页均返回 `200`，主标题和 8 个基本信息键值均可定位。

## 边界

- fixture 回放与 live 结果分开记录。
- 本次没有保存全量详情或媒体文件。
- 证据只记录 URL、取得时间、状态码、字节数和哈希，不包含登录态或 Cookie。
