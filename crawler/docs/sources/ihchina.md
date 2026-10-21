# 中国非物质文化遗产网

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `ihchina`

状态: `approved-with-gaps`

权利状态: `attribution-required`

验证时间: `2026-10-19 01:09 Asia/Shanghai`

## 来源概况

- 名称: 中国非物质文化遗产网·中国非物质文化遗产数字博物馆
- 域名: `www.ihchina.cn`
- 主管机构: 中华人民共和国文化和旅游部
- 主办机构: 中国艺术研究院 · 中国非物质文化遗产保护中心
- 内容域: 国家级非物质文化遗产代表性项目名录、代表性传承人、文化生态保护区、生产性保护示范基地、资讯、学术和影音资源
- 优先级: P0。官方名录，优先于商业聚合站和二次整理来源
- 访问等级: `public`
- `license_or_usage`: 站内注明“中国非物质文化遗产网”来源或带有网站 LOGO、水印的文字、图片、音视频，著作权归网站所有。转载、引用、摘编、下载或其他方式复制使用时须注明作者，并标明来源为“中国非物质文化遗产网”或 `www.ihchina.cn`；未经书面授权不得用于商业用途，也不得修改内容。采集库可保存公开内容和原始响应用于回溯，业务库只发布已审核的基础字段和必要短摘要，并保留来源链接。不得把第三方文章全文作为自有内容发布
- `confidence`: `high`。列表接口、详情页、传承人页、资讯页和学术页均已实际返回 `200`，选择器在 Playwright 中定位非空

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `https://www.ihchina.cn/` | GET | 站点门户 |
| 国家级非遗列表页 | `https://www.ihchina.cn/project` | GET | 页面标题“国家级非物质文化遗产代表性项目名录”，运行后由脚本调用 JSON 接口 |
| 列表 JSON 接口 | `https://www.ihchina.cn/getProject.html?province=&rx_time=&type=&cate=&keywords=&category_id=16&limit=10&p=1` | GET | 返回 `application/json; charset=utf-8`，匿名可访问 |
| 项目详情页模式 | `https://www.ihchina.cn/project_details/{id}.html` | GET | `id` 来自列表 JSON 的 `list[].id` |
| 代表性传承人列表 | `https://www.ihchina.cn/representative` | GET | 传承人独立名录，当前页面显示 3995 条 |
| 传承人详情页模式 | `https://www.ihchina.cn/ccr_detail/{id}.html` | GET | 传承人链接来自传承人表和项目详情页 |
| 相关资讯 / 学术详情模式 | `https://www.ihchina.cn/project_details/{id}.html`、`https://www.ihchina.cn/Article/Index/detail?id={id}` | GET | 项目详情的“相关资讯”与“相关学术”分别使用这两类链接 |
| 版权声明 | `https://www.ihchina.cn/about/206.html` | GET | 版权与免责声明 |
| robots.txt | `https://www.ihchina.cn/robots.txt` | GET | 实际返回 `404`，站点未提供可读取的 robots 规则 |

## 请求与分页

- 请求方式: `GET`
- 查询参数:

| 参数 | 类型 | 已验证取值 | 含义 |
| --- | --- | --- | --- |
| `province` | string | 空串、`440000` | 申报地区行政区划代码。`440000` 为广东省，返回 165 条 |
| `rx_time` | string | 空串、`1`、`2`、`3`、`4`、`10` | 公布批次。依次对应 2006 第一批、2008 第二批、2011 第三批、2014 第四批、2021 第五批 |
| `type` | string | 空串、`1` 至 `10` | 类别。依次对应民间文学、传统音乐、传统舞蹈、传统戏剧、曲艺、传统体育游艺与杂技、传统美术、传统技艺、传统医药、民俗 |
| `cate` | string | 空串、`1`、`2` | 项目类型。`1` 为新增项目，`2` 为扩展项目 |
| `keywords` | string | 空串、`粤剧` | 项目名称关键词。`粤剧` 返回 7 条 |
| `category_id` | string | `16` | 国家级非遗项目名录的分类 ID。省略该参数时接口返回 4234 条，与 3610 子项口径不同 |
| `limit` | integer | `10`，另验证 `1`、`50`、`100` | 每页条数。默认 `10` |
| `p` | integer | `1` 至 `361` | 页码，从 1 开始 |

- 分页字段:
  - 顶层 `total`: 当前筛选条件下的记录总数
  - 顶层 `count`: 当前筛选条件下的记录总数，与 `total` 相同
  - 顶层 `p`: 当前页码
  - 顶层 `more`: 是否还有更多页
  - `links.total`: 总记录数
  - `links.total_pages`: 总页数，等于 `ceil(total / limit)`
  - `links.current`: 当前页码
  - `links.down.url`: 下一页 URL
  - `links.end.url`: 末页 URL
  - `links.pages`: 当前附近页的 URL 映射
  - `links.url`: 带 `_PAGENUM_` 占位符的分页模板
  - 顶层 `pa`: 页面分页器 HTML 片段
- 每页数量: 默认 `10`。`limit=10` 时 `total=3610`，`total_pages=361`
- 总数字段: `total` 和 `count`，默认查询均为 `3610`
- 筛选字段: `province`、`rx_time`、`type`、`cate`、`keywords`，固定名录分类为 `category_id=16`
- 3610 口径: 页面统计块显示“5 批、10 类别、1557 项目、3610 子项”。因此 `3610` 是国家级非遗代表性项目名录的子项数，不是唯一项目名数。同一项目名可因申报地区、扩展批次或保护单位不同而出现多条，例如“苗族古歌”在默认查询前 10 条中出现 5 次
- 详情 ID 稳定性: 列表 JSON 的 `id` 是详情页数字 ID；`auto_id` 是页面上的项目序号；`num` 是项目编号；`project_num` 是含批次和行政区划的内部编号。不要把四者混用
- HTML 回退: `/project` 是前端壳页，首次加载后由脚本请求 `/getProject.html`。采集器应优先直接请求 JSON，HTML DOM 只作为接口变更时的备用定位

## 字段定位

### JSON API

顶层字段:

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| `total` | 总记录数 | `3610` |
| `count` | 总记录数 | `3610` |
| `p` | 当前页 | `1` |
| `links` | 分页对象 | `total_pages=361` |
| `show` | 页面展示控制字段 | 空串 |
| `list` | 当前页记录数组 | 10 条 |
| `more` | 是否还有更多页 | `1` |
| `pa` | 分页器 HTML | `<ul class="page-box ...">` |

`list[]` 字段:

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| `id` | 详情页 ID | `12178` |
| `title` | 项目名称 | `苗族古歌` |
| `title2` | 副标题或别名 | 空串 |
| `auto_id` | 项目序号 | `1` |
| `num` | 项目编号 | `Ⅰ-1` |
| `num_first` | 编号主段 | `1` |
| `num_sec` | 编号次段 | `1` |
| `project_num` | 含申报批次和地区的内部编号 | `Ⅰ-001_01_522630` |
| `type` | 类别名称 | `民间文学` |
| `cate` | 项目类型 | `新增项目` |
| `rx_time` | 公布时间与批次，含 HTML `<br>` | `2006</br>(第一批)` |
| `province` | 申报地区或单位的展示名 | `贵州省台江县` |
| `city` | 地级行政区划代码 | `522600` |
| `area` | 县级行政区划代码 | `522630` |
| `address` | 省级行政区划代码 | `520000` |
| `unit` | 申报地区或单位 | `贵州省台江县` |
| `protect_unit` | 保护单位 | `台江县非物质文化遗产保护中心` |
| `content` | 正文 HTML 片段，实体编码 | `申报地区或单位：贵州省台江县 &lt;br /&gt;...` |
| `modified` | Unix 秒级修改时间 | `1544782620` |
| `status_id` / `status` | 发布状态 | `1` / `1` |
| `is_top` / `top_start` / `top_end` / `sortrank` | 置顶和排序字段 | `0` / 空串 / 空串 / `0` |
| `order` | 同组内排序 | `1` |
| `source` | 来源字段 | 空串 |
| `reg_type` | 注册或记录类型 | `0` |
| `project_level` | 项目级别 | 空串 |
| `playtype` | 媒体播放类型 | `local` |
| `upvideo` | 上传视频 | `null` |
| `img_group` / `video` / `img_video` | 图片组、视频、图片视频标记 | `N;` / `N;` / `N;` |

列表页 DOM 回退:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 总子项数 | `.num-box .b[data-rn]` | 第 4 个统计块为 `data-rn="3610"` |
| 统计文案 | `.num-box` | 显示批次、类别、项目、子项数量 |
| 表头 | `#table th` | 9 列：序号、项目序号、编号、名称、类别、公布时间、类型、申报地区或单位、保护单位 |
| 数据行 | `#table tr` | 第 1 行为表头，之后为数据行 |
| 名称链接 | `#table tr:nth-child(2) a[href^="/project_details/"]` | 指向详情页 |
| 结果数 | `.tit .col` | 当前筛选结果条数 |
| 筛选地区 | `.select-opts.province .select-item[data-id]` | 37 个选项，含“全部” |
| 筛选批次 | `.select-opts.rx_time .select-item[data-id]` | `1`、`2`、`3`、`4`、`10` |
| 筛选类别 | `.select-opts.type .select-item[data-id]` | `1` 至 `10` |
| 筛选类型 | `.select-opts.cate .select-item[data-id]` | `1`、`2` |
| 关键词输入 | `#keywords` | 项目名称关键词 |
| 分页器 | `.page-box` | 页码按钮和跳转输入 |
| 总页数 | `input[name="total_pages"]` | `361` |

### HTML DOM

项目详情页 `https://www.ihchina.cn/project_details/{id}.html`:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 项目名称 | `.article-mod2 .t_head .h30` | 详情页主标题 |
| 基本信息键值 | `.article-mod2 .table .p` | 每项文本形如“项目序号：1”，按冒号拆分 |
| 项目序号 | `.article-mod2 .table .p:nth-child(1)` | 样本值 `项目序号：1` |
| 项目编号 | `.article-mod2 .table .p:nth-child(2)` | 样本值 `项目编号：Ⅰ-1` |
| 公布时间 | 文本匹配 `^公布时间：` 的 `.article-mod2 .table .p` | 样本值 `公布时间：2006(第一批)` |
| 类别 | 文本匹配 `^类别：` 的 `.article-mod2 .table .p` | 样本值 `类别：民间文学` |
| 所属地区 | 文本匹配 `^所属地区：` 的 `.article-mod2 .table .p` | 样本值 `所属地区：贵州省` |
| 类型 | 文本匹配 `^类型：` 的 `.article-mod2 .table .p` | 样本值 `类型：新增项目` |
| 申报地区或单位 | 文本匹配 `^申报地区或单位：` 的 `.article-mod2 .table .p` | 样本值 `贵州省台江县` |
| 保护单位 | 文本匹配 `^保护单位：` 的 `.article-mod2 .table .p` | 样本值 `台江县非物质文化遗产保护中心` |
| 正文 | `.article-mod2 .text .p` | HTML 或纯文本正文；可能包含图片和段落 |
| 相关传承人区块 | `.inherit_xx2 .x-tables table:first-of-type` | 表格第 1 行为表头，后续为传承人 |
| 传承人编号 | 传承人表 `tr td:nth-child(1)` | 可能为空 |
| 传承人姓名与链接 | 传承人表 `tr td:nth-child(2) a[href^="/ccr_detail/"]` | 链接到传承人详情 |
| 传承人性别 | 传承人表 `tr td:nth-child(3)` | |
| 传承人出生日期 | 传承人表 `tr td:nth-child(4)` | 可能为空 |
| 传承人民族 | 传承人表 `tr td:nth-child(5)` | |
| 传承人类别 | 传承人表 `tr td:nth-child(6)` | |
| 传承人项目编号 | 传承人表 `tr td:nth-child(7)` | |
| 传承人项目名称 | 传承人表 `tr td:nth-child(8)` | |
| 传承人申报地区或单位 | 传承人表 `tr td:nth-child(9)` | |
| 相关项目 | `.inherit_xx2 .x-tables` 第 2 个容器内的 `table` | 表头：编号、项目名称、类型、申报地区或单位。不要使用 `table:nth-of-type(2)`，真实 DOM 是多个同级容器 |
| 相关项目链接 | 相关项目表 `tr td:nth-child(2) a[href^="/project_details/"]` | 可直接打开 |
| 相关资讯 | `.inherit_xx2 .list:nth-of-type(n)` 中标题为“相关资讯”的区块 | 实际上按 `.inherit_xx2 .list` 顺序取第 1 个 |
| 资讯日期 | 相关资讯 `.list-link .date` | `2023.06.25` |
| 资讯标题 | 相关资讯 `.list-link .p` | |
| 资讯链接 | 相关资讯 `a.list-link[href]` | 通常为 `/project_details/{id}.html` |
| 相关学术 | `.inherit_xx2 .list` 顺序第 2 个，标题为“相关学术” | |
| 学术日期 | 相关学术 `.list-link .date` | |
| 学术标题 | 相关学术 `.list-link .p` | |
| 学术链接 | 相关学术 `a.list-link[href]` | 形如 `/Article/Index/detail?id={id}` |

区块存在性必须按标题判断，不要固定认为每个项目都有四块。样本 `23632` 只有“相关传承人”和“相关项目”，没有“相关资讯”和“相关学术”区块。

传承人详情页 `https://www.ihchina.cn/ccr_detail/{id}.html`:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 姓名 | `.article-mod2 .t_head .h30` | |
| 基本信息 | `.article-mod2 .table .p` | 序号、性别、出生日期、民族、类别、项目编号、项目名称、申报地区或单位 |
| 小传 | `.article-mod2 .text .p` | 传承人生平与技艺说明 |
| 关联区块 | `.inherit_xx2` | 结构与项目详情页相同 |

资讯详情页 `https://www.ihchina.cn/project_details/{id}.html`:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 标题 | `.newsdetails1 .article-title .h24` | |
| 来源 | `.newsdetails1 .article-title .sub-item` 中文本以“来源：”开头项 | |
| 创建时间 | `.newsdetails1 .article-title .sub-item .en` | 形如 `2023-06-25 18:43:00` |
| 正文 | `.newsdetails1 .article-cont` | 长文正文 |
| 编辑 | `.article-nav` | 形如 `编辑：李振茹`。实测该节点不在 `.newsdetails2` 内 |

学术详情页 `https://www.ihchina.cn/Article/Index/detail?id={id}`:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 标题 | `.newsdetails1 .article-title .h24` | |
| 来源、作者 | `.newsdetails1 .article-title .sub-item` | 文本分别以“来源：”“作者：”开头 |
| 创建时间 | `.newsdetails1 .article-title .sub-item .en` | 形如 ` 2023.09.11 18:05:00` |
| 正文 | `.newsdetails1 .article-cont` | 长文正文 |
| 编辑 | `.article-nav` | |

### 文件附件

无。当前范围未发现列表或详情页必须依赖的公开附件。若后续采集到 PDF、DOC、XLSX、图片或音视频文件，按 100MB 上限处理并记录 URL、大小和 SHA-256。

## 真实样本

### 样本 1：来自列表 JSON 接口

- 详情 URL: `https://www.ihchina.cn/project_details/12178.html`
- 列表接口 URL: `https://www.ihchina.cn/getProject.html?province=&rx_time=&type=&cate=&keywords=&category_id=16&limit=10&p=1`
- 抓取时间: `2026-10-19 01:09 Asia/Shanghai`
- 原始响应证据: HTTP `200`，`Content-Type: application/json; charset=utf-8`，响应长度约 45531 字节。顶层 `total=3610`、`count=3610`、`p=1`、`list.length=10`、`links.total_pages=361`
- 关键字段:

| 字段 | 值 |
| --- | --- |
| `id` | `12178` |
| `title` | `苗族古歌` |
| `auto_id` | `1` |
| `num` | `Ⅰ-1` |
| `project_num` | `Ⅰ-001_01_522630` |
| `type` | `民间文学` |
| `cate` | `新增项目` |
| `rx_time` | `2006</br>(第一批)` |
| `address` | `520000` |
| `province` | `贵州省台江县` |
| `city` | `522600` |
| `area` | `522630` |
| `unit` | `贵州省台江县` |
| `protect_unit` | `台江县非物质文化遗产保护中心` |
| `content` | 以“申报地区或单位：贵州省台江县”开头，含 HTML 实体编码的正文 |
- 页面证据: 详情页 HTTP `200`，标题为“苗族古歌 - 中国非物质文化遗产网·中国非物质文化遗产数字博物馆”；`.article-mod2 .t_head .h30` 返回“苗族古歌”，`.article-mod2 .table .p` 返回 8 个键值，`.article-mod2 .text .p` 纯文本长度 541
- 目标映射: `std_ich_projects` 主记录；`std_ich_inheritors` 5 条；`std_ich_related_items` 3 条；`std_ich_media_links` 仅在有图片或视频时写入

### 样本 2：来自详情页

- 详情 URL: `https://www.ihchina.cn/project_details/23632.html`
- 发现路径: 在样本 1 详情页的“相关项目”表中发现，链接文本“苗族古歌（簪汪传）”
- 抓取时间: `2026-10-19 01:09 Asia/Shanghai`
- 原始页面证据: HTTP `200`，标题为“苗族古歌（簪汪传） - 中国非物质文化遗产网·中国非物质文化遗产数字博物馆”
- 关键字段:

| 字段 | 值 |
| --- | --- |
| 项目名称 | `苗族古歌（簪汪传）` |
| 项目序号 | `1` |
| 项目编号 | `Ⅰ-1` |
| 公布时间 | `2021(第五批)` |
| 类别 | `民间文学` |
| 所属地区 | `贵州省` |
| 类型 | `扩展项目` |
| 申报地区或单位 | `贵州省贵阳市清镇市` |
| 保护单位 | `清镇市文化馆` |
| 正文 | 851 个纯文本字符，含 4 个段落 |
| 相关传承人 | 1 条：王启光，链接 `https://www.ihchina.cn/ccr_detail/29840.html` |
| 相关项目 | 3 条：`12179`、`12178`、`12177` |
| 相关资讯 | 无区块 |
| 相关学术 | 无区块 |
- 辅助样本: 传承人 `王安江`，`https://www.ihchina.cn/ccr_detail/716.html`，HTTP `200`，序号 `01-0001`，性别男，出生日期 `1935.11`，民族苗族，类别民间文学，项目编号 `Ⅰ-1`，项目名称苗族古歌，申报地区或单位贵州省台江县
- 目标映射: `std_ich_projects` 主记录；`std_ich_inheritors` 1 条；`std_ich_related_items` 3 条；`std_ich_media_links` 仅在正文或页头存在图片、视频时写入

## 字段映射

### crawler std 层建议实体

`std_ich_projects`

| 来源字段 | std 字段 | 转换说明 |
| --- | --- | --- |
| `id` | `source_item_id` | 与 `source_id='ihchina'` 组成来源内自然键之一 |
| `title` | `name` | 去首尾空白，保留全角括号 |
| `auto_id` | `serial_no` | 项目序号 |
| `num` | `ich_code` | 项目编号，统一罗马数字与连字符样式 |
| `project_num` | `source_project_num` | 保留原始内部编号 |
| `type` | `category` | 类别名称 |
| `cate` | `project_type` | 新增项目 / 扩展项目 |
| `rx_time` | `announcement_batch` | 去 `<br>`，拆出年份和批次 |
| `address` | `province_code` | 省级行政区划代码 |
| `city` | `city_code` | 地级行政区划代码 |
| `area` | `county_code` | 县级行政区划代码 |
| `province` / `unit` | `declaration_region` | 申报地区或单位展示名 |
| `protect_unit` | `protection_unit` | 保护单位 |
| `content` | `description_html` / `description_text` | raw 保存原始 HTML，std 保存去标签纯文本 |
| `modified` | `source_modified_at` | Unix 秒转 ISO 8601 |
| `id` | `source_url` | 拼为 `https://www.ihchina.cn/project_details/{id}.html` |
| 详情页基本信息 | `region` | 从 `province`、`city`、`area` 和“所属地区”交叉校验 |

`ich_inheritors`

| 来源字段 | std 字段 | 转换说明 |
| --- | --- | --- |
| 姓名链接中的 `ccr_detail` ID | `source_item_id` | |
| 姓名 | `name` | |
| 性别 | `gender` | |
| 出生日期 | `birth_date` | 保留 `YYYY.MM` 精度，无法确定完整日期时写 null |
| 民族 | `ethnicity` | |
| 类别 | `category` | |
| 项目编号 | `ich_code` | |
| 项目名称 | `project_name` | |
| 申报地区或单位 | `declaration_region` | |
| 姓名链接 | `source_url` | |

`ich_related_items`

| 来源字段 | std 字段 | 转换说明 |
| --- | --- | --- |
| 当前项目 `id` | `subject_source_item_id` | |
| 相关项目链接中的 ID | `related_source_item_id` | |
| 相关项目编号 | `ich_code` | |
| 相关项目名称 | `related_name` | |
| 相关项目类型 | `relation_type` | 页面表头写“类型”，实际值为类别名称，例如民间文学 |
| 申报地区或单位 | `declaration_region` | |
| 相关项目链接 | `related_url` | |

`ich_media_links`

| 来源字段 | std 字段 | 转换说明 |
| --- | --- | --- |
| 项目 `id` | `subject_source_item_id` | |
| 正文图片 `img[src]` | `media_url` | 相对路径补全为绝对 URL |
| 页头图片、视频、`pop-video` 的 `data-src` | `media_url` | 仅在字段非 `N;` 时写入 |
| 资源类型 | `media_type` | image / video / audio / iframe |
| 来源详情 URL | `source_page_url` | 用于回溯 |

`ich_related_articles` 建议新增，或复用通用 `related_links`

| 来源字段 | std 字段 | 转换说明 |
| --- | --- | --- |
| 当前项目 `id` | `subject_source_item_id` | |
| 资讯或学术链接中的 ID | `article_source_item_id` | |
| 区块标题 | `relation_type` | 相关资讯 / 相关学术 |
| 日期 | `published_date` | 统一为 `YYYY-MM-DD` |
| 标题 | `title` | |
| 链接 | `source_url` | |
| 正文 | `body_html` / `body_text` | 资讯和学术全文默认只进采集库，不默认发布 |

### 粤乡智匠 crafts 表补列方案

| 目标字段 | 类型建议 | 来源 | 转换说明 |
| --- | --- | --- | --- |
| `source_url` | TEXT | 项目详情页 URL | 必填，直接可由 `id` 生成 |
| `ich_code` | TEXT | `num` | 项目编号 |
| `ich_category` | TEXT | `type` | 非遗类别 |
| `ich_batch` | TEXT | `rx_time` | 去 HTML 后保存“第一批”等 |
| `ich_type` | TEXT | `cate` | 新增项目 / 扩展项目 |
| `protection_unit` | TEXT | `protect_unit` | 保护单位 |
| `province` | TEXT | `address` 或“所属地区” | 保存省级名称，不保存行政区划数字码 |
| `city` | TEXT | `city` 和 `province` 展示名 | 解析地级名称；无法解析时写 null |
| `county` | TEXT | `province` 展示名和 `area` | 解析县级名称；无法解析时写 null |
| `is_teachable` | INTEGER | 人工审核 | 默认 0。只有具备可审核教学步骤、视频或采购指南时才置 1 |
| `content_hash` | TEXT | 规范化后的标题、正文、批次、保护单位 | SHA-256，用于变更检测 |
| `imported_at` | TEXT | 导入时间 | ISO 8601，带时区 |

自然键建议: `source_id + source_item_id` 作为采集库唯一键；业务库用 `ich_code + 申报地区或单位 + 项目名称` 做 升级写入 校验。若保护单位或申报地区变化，保留冲突记录，不静默覆盖人工字段。

发布策略: 全量项目可入库、可浏览、可跳转来源。`is_teachable=0` 的项目只展示基础资料和来源链接，不渲染空步骤、空视频和空采购指南。

## 数据量与更新

- 当前数量估算:
  - 国家级非遗名录默认筛选 `category_id=16`：`3610` 子项
  - 省略 `category_id`：`4234` 条，口径更大，不作为本项目“3610 子项全量”入口
  - 页面统计：5 批、10 类别、1557 项目、3610 子项
  - 代表性传承人页面：3995 条
  - 详情页关联资源每块最多可见 5 条，不能据此推断全站关联资源总量
- 更新频率: 名录按批次公布，通常数年一次；传承人、相关资讯和相关学术会持续增补。`modified` 字段只反映来源记录修改时间，不等于国务院公布时间
- 变更检测:
  - 列表层每轮记录 `total`、`total_pages`、每页 `id` 集合和 `modified`
  - 详情层比较规范化正文、基本信息、关联传承人、相关项目、资讯和学术链接集合的 SHA-256
  - 对 `title`、`num`、`cate`、`protect_unit`、`province` 建立字段级差异
  - 关联资源以链接集合比较，新增或删除分别记录
- 建议采集频率:
  - 列表全量：每周一次
  - 详情全量：每月一次；发现新 `id`、`modified` 变化或 `total` 变化时立即增量
  - 关联资讯和学术：每周一次元数据；正文按需回填
  - 传承人：每月一次
- 历史数据保留: raw 层保留响应快照和哈希；std 层保留当前版本和变更记录；业务库只保留发布版本和导入批次。资讯和学术若只保存元数据，需在 raw 层明确标记 `body_saved=false`

## 采集策略

- 清单发现: 直接请求 `/getProject.html`，固定 `category_id=16`，以 `limit=10`、`p=1..361` 翻页。默认值 `10` 必须写入配置，不要依赖页面隐式默认
- 完整性校验: `total=3610`、`count=3610`、`total_pages=361`、按页累计 `sum(list.length)=3610`、`id` 去重后计数为 3610
- 边界处理: `p=362` 返回 `200` 但 `list` 缺失，采集器应视为越界空页并停止，不要把它写成正常详情页
- 详情全采: 对所有 `list[].id` 请求 `/project_details/{id}.html`，保存 HTML、正文、基本信息、传承人表、相关项目、相关资讯和相关学术
- 传承人: 先从项目详情表采集关联传承人，再按需访问 `/ccr_detail/{id}.html` 补全小传。独立传承人页可作为全量发现入口
- 相关项目: 保存双向关系时以“当前项目 -> 相关项目”为有向边，避免把页面表格中的“类型”误读成新增 / 扩展项目类型
- 资讯和学术: 默认采集标题、日期、URL 和所属关系等元数据；需要全文时单独抓取并保存 `body_html`、`body_text`、`content_hash` 和取得时间。若只存元数据，在 raw 记录写 `body_saved=false`，在 std 记录写 `body_available=true`
- 媒体: 只登记公开可访问的图片、视频、音频和 iframe URL；单文件超过 100MB 不下载，写入对应域名目录的 `OVERSIZE.md`
- 请求节奏: 串行或低并发，单域名建议 1 至 2 请求/秒，带明确 `User-Agent` 和失败退避；不使用登录态、Cookie 或绕过访问控制
- 结构化解析: JSON 优先，DOM 回退。DOM 选择器要按区块标题定位，不能假设所有详情页都有四个关联区块
- 清洗: `rx_time` 去掉 `<br>` 和多余空白；`content` 先反转义再解析 HTML；行政区划代码与展示名分开保存

## 风险与限制

- 登录: 未发现登录要求。列表接口、项目详情、传承人、资讯、学术和版权声明均匿名返回 `200`；本次未保存任何账号、密码或 Cookie
- robots: `https://www.ihchina.cn/robots.txt` 返回 `404`，记录为 `not-found`。允许采集并写 `deferred` 候选，404 不等于明确授权，采集仍需遵守版权声明、合理频率和不影响服务的原则
- 版权: 站内明确限制商业用途和未授权修改。业务库只发布基础资料和必要摘要，全文、图片和音视频保留在采集库并标注来源；对外展示必须显示“中国非物质文化遗产网”或 `www.ihchina.cn`
- 结构稳定性: `/project` 是前端壳页，列表依赖 AJAX；详情页关联区块按内容条件渲染，样本 `23632` 缺少资讯和学术区块；`rx_time` 和 `content` 含 HTML 片段；项目序号、编号、内部编号和详情 ID 语义不同
- 缺失字段: 列表接口没有独立的“公布年份”和“批次”字段，只能从 `rx_time` 拆分；没有完整省、市、县名称，只能从 `province` 展示名和行政区划代码推导；`modified` 不是公布日期
- 口径风险: 省略 `category_id` 返回 4234 条，不能直接当作 3610 子项；同一项目名的多条子项不能按标题去重
- 关联资源风险: 相关资讯和相关学术每块最多展示 5 条，页面未提供该区块的完整分页，不能保证覆盖全部关联资源。独立资讯和学术列表可作为后续补全入口
- 图片防盗链或跨域: 正文图片和视频可能存在相对路径、外链或播放限制，下载前需实际请求并记录状态
- 已验证项:
  - 2026-10-20 的历史全量发现记录为 3610 个子项、`std_ich_projects` 3610 行、唯一 ID 3610、0 失败。该记录使用已退役的旧在线入口，仅作历史证据，当前实时入口为 Scrapy 项目。
- 未验证项:
  - 未验证 3610 个详情页是否全部可打开，也未全量统计各详情页关联区块数量
  - 未验证传承人独立列表是否覆盖项目详情中出现的全部传承人
  - 未验证相关资讯、相关学术是否存在独立全量接口
  - 未验证所有媒体文件的大小、格式和可下载性
  - 未把任何网页或媒体保存到下载目录

## 验证记录

- 验证方式: Playwright 实际打开列表页、详情页、传承人页、资讯页和学术页；在浏览器上下文执行 DOM 选择器、`fetch` JSON 接口和版权页请求；另外用实际 HTTP HEAD/GET 复核入口状态
- 验证结果:
  - 首页、`/project`、`/project_details/12178.html`、`/project_details/23632.html`、`/representative`、`/ccr_detail/716.html`、`/about/206.html` 均返回 `200`
  - 列表接口返回 `200`、`application/json; charset=utf-8`、`total=3610`、`count=3610`、`total_pages=361`
  - 列表第 1 页返回 10 条，首条为 `12178` 苗族古歌
  - `p=361` 返回 10 条，`p=362` 返回 `200` 但无 `list`
  - 广东省筛选返回 165 条，17 页
  - 项目详情 `12178` 的 8 个基本信息键值、正文、5 条传承人、3 条相关项目、5 条资讯、5 条学术均定位成功
  - 项目详情 `23632` 的 8 个基本信息键值、851 字正文、1 条传承人、3 条相关项目定位成功，资讯和学术区块不存在
- 未验证项: 见“风险与限制”

## 下载记录

无。

## 审核要求

- 入口可打开: 已确认
- 样本可复现: 已确认 2 条项目样本和 1 条传承人辅助样本
- 字段映射完整: 已覆盖项目、传承人、相关项目、媒体和资讯学术建议实体
- 详情 URL 可直达: 已确认

