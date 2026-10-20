# 采集域词汇

采集生命周期和跨库术语的权威定义统一见
[ADR 0003：Scrapy 采集执行边界](adr/0003-scrapy-collection-boundary.md)。

ADR 0003 定义 `raw`、`stage`、采集库 std 候选标准实体、业务实体和发布实体，
并固定 `raw -> stage -> 采集库 std -> 转换器 -> 业务实体 -> 审核 -> published`
的数据流程。来源建模、字段契约和转换规则的词汇以对应 ADR、schema 和来源契约为准。

本文件只做导航，不重复定义术语，避免形成第二个真相源。
