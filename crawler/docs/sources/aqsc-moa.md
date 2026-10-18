# 农业农村部农产品质量安全中心及监管司

来源 ID: `aqsc-moa`

状态: `approved-with-gaps`

验证时间: `2026-10-19 01:08 Asia/Shanghai`

## 来源概况

- 名称: 农业农村部农产品质量安全中心及农产品质量安全监管司
- 域名: `www.aqsc.agri.cn`、`mtyx.aqsc.org`、`jgs.moa.gov.cn`
- 主管机构: 农业农村部农产品质量安全中心；农业农村部农产品质量安全监管司
- 内容域: 全国名特优新农产品、全国特质农品、认证登记公告、名单附件
- 优先级: P0
- 访问等级: `public`
- `license_or_usage`: 官方公开公告，未发现开放许可。页面声明保留权利，使用范围限内部结构化提取、事实字段采集和来源跳转；整篇转载、镜像或再分发原文及附件需取得授权。
- `confidence`: `high`，首页、栏目、公告详情、查询系统和两份 XLSX 均已实际访问并解析；历史批次和全量水产覆盖为 `medium`。

来源按官方公告优先处理。`www.aqsc.agri.cn` 是名单和附件的主来源，`mtyx.aqsc.org` 用于查询当前有效记录和证书编号，`jgs.moa.gov.cn/rzde/` 用于公告交叉核对和发现链接。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| aqsc 首页 | `http://www.aqsc.agri.cn/` | GET | 2026-10-19 返回 200。页面编码按 GB18030 解码。 |
| 总通知公告 | `http://www.aqsc.agri.cn/tzgg/` | GET | 名特优新、特质农品、注销、追溯等公告混合列表。 |
| 名特优新栏目 | `http://www.aqsc.agri.cn/mtyx/` | GET | 名特优新制度、通知、产品名录入口。 |
| 名特优新通知公告 | `http://www.aqsc.agri.cn/mtyx/tzgg/` | GET | 名特优新专项公告。 |
| 名特优新产品名录 | `http://www.aqsc.agri.cn/mtyx/cpml/` | GET | 按批次发布的产品名录页，部分页面直接内嵌表格。 |
| 特质农品栏目 | `http://www.aqsc.agri.cn/tznp/` | GET | 特质农品制度、通知、产品名录入口。 |
| 特质农品通知公告 | `http://www.aqsc.agri.cn/tznp/tzgg_10469/` | GET | 特质农品专项公告。 |
| 特质农品产品名录 | `http://www.aqsc.agri.cn/tznp/cpml_10472/` | GET | 按批次发布的产品名录页。 |
| 认证登记栏目 | `https://jgs.moa.gov.cn/rzde/` | GET | 监管司认证登记栏目，15 条一页，部分条目外链到 aqsc。 |
| 名特优新动态查询 | `http://mtyx.aqsc.org/Home/Minglu/index.html` | GET | 表格查询，当前显示 9038 条记录。 |
| 特质农品动态查询 | `http://mtyx.aqsc.org/Tznp/Tezhi/index` | GET | 表格查询，当前显示 1265 条记录。 |

### 详情 URL 模式

- 总公告: `http://www.aqsc.agri.cn/tzgg/YYYYMM/tYYYYMMDD_<id>.htm`
- 名特优新专项公告: `http://www.aqsc.agri.cn/mtyx/tzgg/YYYYMM/tYYYYMMDD_<id>.htm`
- 特质农品专项公告: `http://www.aqsc.agri.cn/tznp/tzgg_10469/YYYYMM/tYYYYMMDD_<id>.htm`
- 名特优新产品名录: `http://www.aqsc.agri.cn/mtyx/cpml/YYYYMM/tYYYYMMDD_<id>.htm`
- 特质农品产品名录: `http://www.aqsc.agri.cn/tznp/cpml_10472/YYYYMM/tYYYYMMDD_<id>.htm`
- 监管司认证登记详情: `https://jgs.moa.gov.cn/rzde/YYYYMM/tYYYYMMDD_<id>.htm`
- 附件: 与详情页同目录的 `P020<数字>.xlsx`、`P020<数字>.pdf`、`P020<数字>.docx` 等。

不要仅根据 `<id>` 拼接详情 URL。同一篇公告可能只存在于专项栏目，例如 `t20260901_474171.htm` 在 `/tzgg/` 下为 404，在 `/mtyx/tzgg/` 下为 200。应始终从列表页解析 `href` 后用 `urljoin` 得到规范地址。

## 请求与分页

- 请求方式: 普通 HTTP GET，无登录，无验证码。
- aqsc 编码: HTML 声明 GB2312，部分页面实际按 `gb18030` 才能完整解码。响应头可能误报 `ISO-8859-1`，不要依赖响应头编码。
- 监管司编码: 页面为 UTF-8，但响应头可能误报 `ISO-8859-1`，应按 HTML `meta charset` 或显式 UTF-8 解码。
- 查询系统编码: `mtyx.aqsc.org` 为 UTF-8。

### 静态列表分页

| 列表 | 第一页 | 后续页 | 每页条数 | 观察 |
| --- | --- | --- | --- | --- |
| 总通知公告 | `/tzgg/index.htm` | `/tzgg/index_1.htm`、`index_2.htm` 递增 | 15 | 当前脚本页数变量不可完全信任；实测 `index_44.htm` 仍返回 1 条，`index_45.htm` 为 404。 |
| 名特优新公告 | `/mtyx/tzgg/index.htm` | `/mtyx/tzgg/index_1.htm` 至 `index_4.htm` | 15 | 共 5 页。 |
| 特质农品公告 | `/tznp/tzgg_10469/index.htm` | `/tznp/tzgg_10469/index_1.htm`、`index_2.htm` | 15 | 共 3 页。 |
| 监管司认证登记 | `/rzde/index.htm` | `/rzde/index_1.htm`、`index_2.htm` | 15 | 页面还有 `more_1.htm`、`more_2.htm`、`more_3.htm` 静态片段，供“查看更多”调用。 |

列表页应有停止条件：连续页无新详情 URL、页内条目为空、HTTP 404，或已覆盖到历史起点。不要用单一 `countPage` 变量决定是否结束。

### 动态查询分页

| 查询系统 | 总数 | 每页 | 页码模式 | 末页 |
| --- | --- | --- | --- | --- |
| 名特优新 | 9038 | 20 | `/Home/Minglu/index/p/{page}.html` | `/Home/Minglu/index/p/452.html` |
| 特质农品 | 1265 | 20 | `/Tznp/Tezhi/index/p/{page}.html` | `/Tznp/Tezhi/index/p/64.html` |

查询表单字段:

- `search_post_action=search`
- `search_rows_limit=20`
- `eq_dq_province`: 省份，`-999` 表示全部
- `eq_bu_hz_id`: 获证批次，`-999` 表示全部
- `li_productname1`: 产品名称
- `bt_yx_dt[]`: 有效期起止

查询结果直接返回在当前响应中。查询系统表格行没有单条详情链接，单条证书记录的可追溯详情应以公告详情页和附件行号为准。

## 字段定位

### HTML DOM

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 列表条目 | `.News_center_con li` | 每条含日期 `span` 和详情 `a[href]`。 |
| 列表标题 | `.News_center_con li a[href]` | 去掉前缀点号和空白。 |
| 列表日期 | `.News_center_con li span` | 格式通常为 `YYYY-MM-DD`。 |
| 分页变量 | `.News_center_flip script` | 可读 `currentPage`、`countPage`，只作辅助。 |
| 详情标题 | `.Details_con h3` | 公告标题，可能含 `<br>`。 |
| 详情元信息 | `.Details_con h4` | 同时包含日期、作者、来源。 |
| 详情正文 | `.Details_con #nr`、`.Details_con .TRS_Editor` | 正文，可能省略部分字段。 |
| 内嵌名单表 | `.Details_con table` | 第一行常为跨列标题，第二行为表头，第三行起为数据。 |
| 附件链接 | `.Details_con a[href]`、`#nr a[href]` | 链接文字通常是文件名，`href` 为同目录相对路径。 |
| 页脚声明 | `.foot_con_text` | aqsc 页面声明保留所有权利。 |

### 文件附件

链接选择:

```css
.Details_con a[href$=".xlsx"],
.Details_con a[href$=".xls"],
.Details_con a[href$=".pdf"],
.Details_con a[href$=".doc"],
.Details_con a[href$=".docx"],
.Details_con a[href$=".zip"]
```

实践上应先取 `.Details_con a[href]`，去掉 query 和 fragment 后按扩展名判断，再用 `urljoin(detail_url, href)` 解析相对地址。

附件 URL 规律:

- 附件通常与详情页同目录，例如详情 `/tzgg/202511/t20251128_468194.htm` 的附件为 `/tzgg/202511/P020251225613822033339.xlsx`。
- 文件名前的 `P020<数字>` 是发布系统内部编号，不对应产品编号。
- 同一公告可同时提供 `.pdf` 正文和 `.xlsx` 名单，应优先解析 XLSX；PDF 只作正文和版式核验。
- 2024 至 2026 年不少公告把名单直接嵌入 HTML 表格，没有附件。解析器必须同时支持附件和 `.Details_con table`。

### 附件表头

名特优新公示表:

```text
序号 | 省份 | 县域 | 证书编号 | 产品名称 | 获证单位 |
联系人 | 生产规模（公顷、万头、万只、万羽等） | 主要生产经营单位
```

特质农品公示表:

```text
序号 | 省份 | 县域 | 产品全称 | 申请单位全称 |
联系人 | 生产规模（公顷、万头、万只、万羽等）
```

最终公告可能使用 `获证单位`，公示阶段可能使用 `申请单位全称`。两者进入同一 `applicant_name`，同时保留来源字段名，不能把申请单位误写成已核准获证单位。

## 已下载文件

下载目录: `crawler/download/www.aqsc.agri.cn/`

| 文件 | 公告详情 URL | 附件 URL | 大小 | SHA-256 | 结构 |
| --- | --- | --- | ---: | --- | --- |
| `2025年第三批名特优新公示表.xlsx` | `http://www.aqsc.agri.cn/tzgg/202511/t20251128_468194.htm` | `http://www.aqsc.agri.cn/tzgg/202511/P020251225613822033339.xlsx` | 113937 bytes | `cd0e40aa19d47a474c1242502064c40a19a0d64c73887227b61537230b88cc63` | 1 个工作表；792 行；标题 1 行、表头 1 行、数据 790 行；9 列。 |
| `2025年第三批特质农品公示表.xlsx` | `http://www.aqsc.agri.cn/tzgg/202511/t20251128_468195.htm` | `http://www.aqsc.agri.cn/tzgg/202511/P020251128359343750170.xlsx` | 24022 bytes | `e7d927fbff2122aa22f3ac67384d4be6a58befc2a5389fe42545488bd745249a` | 3 个工作表；Sheet1 有 154 行，标题 1 行、表头 1 行、数据 152 行；7 列；Sheet2、Sheet3 为空。 |

两份文件均小于 100MB，均通过 ZIP 文件头 `PK\x03\x04` 和 `openpyxl` 解析验证，没有损坏。名特优新表的 790 条数据中，`县域` 有 15 条为空，其他关键字段完整；特质农品表的 152 条数据字段完整。

解析时应先定位表头行，不要假设所有文件第 2 行一定是表头。可靠条件是某行同时包含 `序号`、`省份`，其后为数据行。

## 真实样本

### 样本 1: 普通农产品，名特优新

- 认证类型: `mingteyouxin`
- 产品名称: 平谷蟠桃
- 证书编号: `CAQS-MTYX-20250914`
- 批次: 2025 年第三批
- 公告标题: 2025 年第三批全国名特优新农产品公示
- 发布日期: 2025-11-28
- 省份: 北京市
- 县域: 平谷区
- 公告详情 URL: `http://www.aqsc.agri.cn/tzgg/202511/t20251128_468194.htm`
- 附件 URL: `http://www.aqsc.agri.cn/tzgg/202511/P020251225613822033339.xlsx`
- 附件行: Sheet1 第 3 行，序号 1
- 获证单位: 北京市平谷区果品产业服务中心
- 联系人: 喻永强
- 生产规模: 5933.33 公顷
- 主要生产经营单位: 北京丽城嘉苑农业发展有限公司；北京绿农兴云智慧农业专业合作社
- 水产标记: `aquatic=false`
- 目标映射: `agri_certified_products` 一条名特优新记录；`agri_product_sources` 一条附件行来源记录。

### 样本 2: 水产品，名特优新

- 认证类型: `mingteyouxin`
- 产品名称: 秦皇岛刺参
- 证书编号: `CAQS-MTYX-20250923`
- 批次: 2025 年第三批
- 公告标题: 2025 年第三批全国名特优新农产品公示
- 发布日期: 2025-11-28
- 省份: 河北省
- 县域: 源文件为空，保留 `null`
- 公告详情 URL: `http://www.aqsc.agri.cn/tzgg/202511/t20251128_468194.htm`
- 附件 URL: `http://www.aqsc.agri.cn/tzgg/202511/P020251225613822033339.xlsx`
- 附件行: Sheet1 第 12 行，序号 10
- 获证单位: 秦皇岛市海洋和渔业局
- 联系人: 石云海
- 生产规模: 2036 公顷
- 主要生产经营单位: 昌黎县振利水产养殖有限公司；昌黎县旺海水产养殖专业合作社；昌黎县川岛湾水产养殖有限公司；秦皇岛七里渔田水产养殖有限公司；秦皇岛鸿兆水产养殖有限公司
- 水产证据: 产品名称为刺参；申请单位为海洋和渔业局；主要生产经营单位含“水产养殖”
- 水产标记: `aquatic=true`，`category=aquatic_shellfish`
- 目标映射: `agri_certified_products` 一条名特优新记录；来源行保留空县域，不虚构行政区。

### 样本 3: 水产品，特质农品

- 认证类型: `tezhi_nongpin`
- 产品名称: 长芦海晶汪子虾
- 证书编号: `null`，公示表未提供证书编号
- 批次: 2025 年第三批
- 公告标题: 2025 年第三批特质农品公示
- 发布日期: 2025-11-28
- 省份: 天津市
- 县域: 滨海新区
- 公告详情 URL: `http://www.aqsc.agri.cn/tzgg/202511/t20251128_468195.htm`
- 附件 URL: `http://www.aqsc.agri.cn/tzgg/202511/P020251128359343750170.xlsx`
- 附件行: Sheet1 第 10 行，序号 8
- 申请单位: 天津海晶博睿科技有限公司
- 联系人: 吴昊
- 生产规模: 2410.007 公顷
- 水产证据: 产品名称为汪子虾，申请单位为水产相关企业
- 水产标记: `aquatic=true`，`category=aquatic_crustacean`
- 目标映射: `agri_certified_products` 一条特质农品记录；公共公示阶段先使用自然键占位，取得最终公告证书编号后升级为证书自然键。

## 水产识别与映射

数据中明确存在水产。已下载的 790 条名特优新数据中，产品名称形态学筛查得到 68 条候选，包含刺参、对虾、青蟹、鳜鱼、鲟鱼、紫菜、文蛤、竹蛏等；152 条特质农品数据中筛查得到 10 条候选，包含汪子虾、大闸蟹、罗氏沼虾、鲟鱼子酱、石蛙等。该数字只是候选量，不是最终水产真值。

水产字段建议:

- `category`: 受控枚举，至少包括 `aquatic_fish`、`aquatic_crustacean`、`aquatic_shellfish`、`aquatic_algae`、`aquatic_other`、`non_aquatic`、`unknown`。
- `aquatic`: 三态布尔值，取 `true`、`false`、`null`。无法确认时写 `null`，不要默认 false。
- `aquatic_evidence`: 保存做出判断的证据来源，例如 `product_name`、`applicant_name`、`operator_name`、`manual_review`。

判定顺序:

1. 有官方品类或产品分类字段时，以官方字段为准。
2. 产品名称命中受控水产词表，且申请单位或主要生产经营单位出现“水产、渔业、海洋、渔场、养殖场”等生产证据时，可直接标记。
3. 产品名称命中但单位无水产证据时，进入人工复核，不直接入库为 true。
4. 产品名称未命中但单位含水产证据时，进入人工复核，防止地方名、商品名或加工品漏判。
5. 人工复核覆盖优先于关键词结果，保留复核人和时间。

关键词不能作为唯一依据。已观察到明显误报和歧义:

- `鲅鱼圈鸡蛋` 的“鲅鱼”是地名，不是水产品。
- `安溪毛蟹` 是茶叶品类，不应仅凭“蟹”判为水产。
- `仪征紫菜薹` 是蔬菜，不是紫菜。
- `蒙阴丹参`、`禄劝党参` 的“参”不是海参。
- `贝贝南瓜`、`贝母`、`鱼腥草`、`螺丝椒` 等词形会触发贝、鱼、螺等误报。
- 部分水产加工品名称不含鱼虾蟹字样，例如 `瑶柱`，需要结合产品或单位信息复核。

样本 2 和样本 3 的证据链均不止关键词: 申请单位或主要生产经营单位直接含海洋、渔业或水产信息，因此可高置信标记为水产。

## 历史批次采集策略

名特优新和特质农品必须分两条采集流水线处理，不能只按页面目录混在一起。

### 公告发现

1. 遍历 `/tzgg/`、`/mtyx/tzgg/`、`/tznp/tzgg_10469/` 的静态分页。
2. 用标题和目录双重判定认证类型。
3. 名特优新识别: 标题含 `全国名特优新`，或详情路径在 `/mtyx/`，或证书编号以 `CAQS-MTYX-` 开头。
4. 特质农品识别: 标题含 `特质农品`，或详情路径在 `/tznp/`，或证书编号以 `CAQS-TZNP-` 开头。
5. 公告状态识别: 标题含 `公示` 为 `proposed`，含 `公告` 为 `certified`，含 `注销` 为 `revoked`，其他为 `notice`。

### 公告和名单解析

每条公告保留:

- `announcement_id`
- `announcement_no`
- `announcement_title`
- `publish_date`
- `certification_type`
- `announcement_status`
- `detail_url`
- `body_text`
- `attachment_urls`
- `content_sha256`

每条名单行保留:

- `batch`
- `announcement_no`
- `publish_date`
- `province`
- `county`
- `product_name`
- `certificate_no`
- `applicant_name`
- `contact_name`
- `production_scale_raw`
- `main_operators_raw`
- `row_no`
- `source_field_names`

批次从公告标题、文件标题或文件名提取，例如 `2025年第三批`。公告号从标题提取，例如 `农业农村部农产品质量安全中心公告（第44号）`。没有明确公告号时写 `null`。

### 公示、正式公告和注销

- 公示表没有证书编号时，以 `certification_type + batch + 规范化产品名称 + 省份 + 县域 + 申请单位` 生成临时自然键。
- 最终公告取得 `CAQS-MTYX-` 或 `CAQS-TZNP-` 证书编号后，用批次和产品主体信息回填，并切换到证书自然键。
- 注销公告不删除原产品。写入 `status=revoked`、注销公告 URL、注销日期和注销批次，保留原认定记录。
- 同一产品可能跨批次再次出现。证书编号优先作为最终自然键；没有证书编号时，批次必须参与自然键。

### 历史回填

- 优先解析 2019 年以后的 XLSX 和 HTML 表格。
- 旧 PDF 只做正文和缺失表头核验，必要时人工抽样，不把 OCR 结果直接当结构化真值。
- 每批保存附件哈希和行级哈希，重复运行按自然键升级写入。

## 认证类型区分

| 中文口径 | 标准枚举 | 证书前缀 | 主要列表 | 证书编号 |
| --- | --- | --- | --- | --- |
| 全国名特优新农产品 | `mingteyouxin` | `CAQS-MTYX-` | `/mtyx/tzgg/`、`/mtyx/cpml/` | 通常有 |
| 全国特质农品 | `tezhi_nongpin` | `CAQS-TZNP-` | `/tznp/tzgg_10469/`、`/tznp/cpml_10472/` | 正式公告有，公示表可能没有 |

认证类型必须独立成列。不得只靠产品名称、省份或通用 `agri_certified_products` 表推断，也不得把特质农品写入名特优新枚举。

## 字段映射

### crawler std 层 `agri_certified_products`

| 来源字段 | std 字段 | 类型 | 转换说明 |
| --- | --- | --- | --- |
| 来源 ID | `source_id` | text | 固定 `aqsc-moa`。 |
| 公告认证类型 | `certification_type` | enum | `mingteyouxin` 或 `tezhi_nongpin`。 |
| 标题/文件名 | `batch` | text | 提取 `YYYY年第N批`。 |
| 公告标题 | `announcement_no` | text | 提取公告号，没有则 `null`。 |
| `日期` | `publish_date` | date | 解析为 ISO 日期。 |
| `证书编号` | `certificate_no` | text | 去除空格，统一大写；公示缺省为 `null`。 |
| `产品名称` / `产品全称` | `product_name` | text | 去首尾空白，保留原始名称。 |
| `省份` | `province` | text | 保留官方行政区名称。 |
| `县域` | `county` | text | 空值保留 `null`，不改写为省名。 |
| `获证单位` / `申请单位全称` | `applicant_name` | text | 统一为申请主体，另存原字段名。 |
| `联系人` | `contact_name` | text | 保存公开公告中的联系人。 |
| `生产规模（...）` | `production_scale_raw` | text | 保留原文，如 `2036公顷`、`520万尾`。 |
| `主要生产经营单位` | `main_operators_raw` | text | 保留换行分隔的原始文本。 |
| 标题状态 | `status` | enum | `proposed`、`certified`、`revoked`、`notice`。 |
| 产品名称/单位证据 | `category` | enum | 水产受控类别或 `non_aquatic`、`unknown`。 |
| 产品名称/单位证据 | `aquatic` | bool/null | 三态，证据不足为 `null`。 |
| 详情 URL | `source_detail_url` | text | 公告详情页。 |
| 附件行 | `source_row_no` | integer | XLSX 或 HTML 表格的物理行号。 |
| 来源内容 | `content_sha256` | text | 公告、附件或行级规范化内容哈希。 |

### crawler std 层 `agri_product_sources`

| 来源字段 | std 字段 | 类型 | 转换说明 |
| --- | --- | --- | --- |
| 来源 ID | `source_id` | text | 固定 `aqsc-moa`。 |
| 公告 ID | `announcement_id` | text | 由详情 URL 或 `YYYYMMDD_id` 生成。 |
| 公告标题 | `source_title` | text | 原文标题。 |
| `日期` | `source_date` | date | 公告发布日期。 |
| 详情 URL | `source_detail_url` | text | 可直接打开的公告页。 |
| 附件链接文字 | `attachment_name` | text | 原文件名。 |
| 附件 URL | `attachment_url` | text | 绝对 URL。 |
| 附件字节 | `attachment_sha256` | text | 下载后计算 SHA-256。 |
| 附件大小 | `attachment_size` | integer | 字节数。 |
| 本地路径 | `raw_file_path` | text | `crawler/download/www.aqsc.agri.cn/<file>`。 |
| 附件行 | `source_row_no` | integer | 名单行号。 |
| 证书编号 | `certificate_no` | text | 与主表相同。 |
| 公告状态 | `source_event` | enum | `proposed`、`certified`、`revoked`、`notice`。 |
| 取得时间 | `fetched_at` | datetime | Asia/Shanghai。 |
| 公告和附件 | `content_sha256` | text | 用于变更检测。 |
| 页面声明 | `license_status` | text | `official-public-notice-rights-reserved`。 |

### 粤乡智匠建议表 `agri_certified_products`

| std 字段 | 业务字段 | 说明 |
| --- | --- | --- |
| `certification_type` | `certification_type` | 必填，区分名特优新和特质农品。 |
| `certificate_no` | `certificate_no` | 正式记录的自然键组成；公示阶段可为空。 |
| `product_name` | `product_name` | 展示名称。 |
| `province` | `province` | 省份筛选。 |
| `county` | `county` | 县域筛选，可为空。 |
| `applicant_name` | `applicant_name` | 申请或获证主体。 |
| `contact_name` | `contact_name` | 公开展示前需走运营审核。 |
| `production_scale_raw` | `production_scale` | 保留原文，另建单位解析字段。 |
| `main_operators_raw` | `main_operators` | 原文保留；需要拆分时另建关联表。 |
| `batch` | `batch` | 批次。 |
| `announcement_no` | `announcement_no` | 公告号。 |
| `publish_date` | `publish_date` | 发布日期。 |
| `status` | `status` | 公示、获证、注销。 |
| `category` | `category` | 水产或普通品类。 |
| `aquatic` | `is_aquatic` | 前台水产筛选。 |
| `source_detail_url` | `source_url` | 跳转官方公告。 |

业务主表自然键建议: 有证书编号时使用 `certification_type + certificate_no`；公示阶段使用 `certification_type + batch + 规范化产品名称 + province + 可空 county + applicant_name`。运营人工修改字段不自动覆盖。

### 粤乡智匠建议表 `agri_product_sources`

| std 字段 | 业务字段 | 说明 |
| --- | --- | --- |
| 产品主键 | `product_id` | 关联 `agri_certified_products`。 |
| `source_id` | `source_id` | 固定 `aqsc-moa`。 |
| `source_title` | `source_title` | 公告标题。 |
| `source_date` | `source_date` | 发布日期。 |
| `source_detail_url` | `source_detail_url` | 官方详情页。 |
| `attachment_url` | `attachment_url` | 官方附件 URL。 |
| `attachment_sha256` | `attachment_sha256` | 附件校验和。 |
| `source_row_no` | `source_row_no` | 附件或 HTML 表格行号。 |
| `source_event` | `source_event` | 公示、获证、注销。 |
| `fetched_at` | `fetched_at` | 取得时间。 |
| `license_status` | `license_status` | 权利状态说明。 |

业务表只保留展示和审核需要的最小来源信息。原始 HTML、完整附件和解析日志留在采集库 raw/stage 层。

## 数据量与更新

- 当前数量估算: 动态查询系统显示名特优新 9038 条、特质农品 1265 条，合计 10303 条当前查询记录。
- 单批规模: 2025 年第三批名特优新 790 条；同批特质农品 152 条。2026 年第一批名特优新公告正文声明 636 条，特质农品 148 条。
- 更新频率: 以批次公告为主。2025 年观察到三批，2026 年截至验证时间观察到两批，实际节奏不固定。
- 变更检测: 列表 URL、标题、日期、详情页 SHA-256、附件 SHA-256、规范化行哈希。目标页面未返回可用的 `ETag` 或 `Last-Modified`，不能依赖条件请求。
- 建议采集频率: 列表每日一次；发现新公示或公告后立即抓取详情和附件；每月做一次全量对账；历史回填只跑一次并按内容哈希增量补采。
- 历史数据保留: 保留每次公告快照和附件哈希。证书注销通过事件更新状态，不物理删除历史记录。

## 风险与限制

- HTTPS: `www.aqsc.agri.cn` 在验证时出现证书主机名不匹配，HTTPS 返回 403 或 TLS 失败；已验证可用的主入口是 `http://www.aqsc.agri.cn/`。不要通过关闭证书校验来抓取 HTTPS。
- 编码: aqsc 页面响应头编码不可靠，必须按 `gb18030` 解码；监管司页面实际 UTF-8。
- robots: `www.aqsc.agri.cn/robots.txt` 返回 403，`jgs.moa.gov.cn/robots.txt` 返回 404，`mtyx.aqsc.org/robots.txt` 返回 404。没有取得明确允许规则，不能把 404 当作授权。
- 跨站链接: 监管司和 aqsc 页面会链接 `www.moa.gov.cn`。已验证 `www.moa.gov.cn/robots.txt` 为 `User-agent:* / Disallow:/`，不要自动跨站抓取该域。
- 登录: 三个目标入口均无需登录。查询系统会下发 `PHPSESSID`，只作匿名会话使用，不保存账号、密码、Cookie 或登录凭据。
- 版权: 页面声明保留所有权利。只采集结构化事实字段、公告元数据和附件哈希，保留来源链接；不把公告全文或附件原样发布到业务库。
- 结构稳定性: 总公告、专项公告、产品名录路径和分页形式不完全一致；详情 URL 不能凭 ID 猜。列表链接可能跨栏目，必须解析后再规范化。
- 缺失字段: 2025 年第三批名特优新表有 15 条县域为空；公示阶段可能没有证书编号；2026 年部分内嵌表格的联系方式显示为 `{{PHONE_xxx}}` 占位符，不能还原或猜测。
- 动态查询: 查询结果行没有单条详情 URL，证书记录与公告行需要靠证书编号和批次关联。筛选、分页和会话组合的长期稳定性未验证。
- 水产: 关键词筛查存在地名、茶名、蔬菜名和中药材误报，不能把关键词作为唯一依据。
- PDF: 旧批次可能只有 PDF。未对所有历史 PDF 做 OCR 和表格结构验证。

## 未验证项

- 未回填全部历史批次，只验证了 2025 年第三批的两份 XLSX 和若干公告页。
- 未对动态查询的筛选分页组合建立稳定契约。
- 未验证所有 PDF 的字段可提取性。
- 未取得 robots 的明确许可文本，也未发现站点的开放数据许可声明。
- 未建立完整人工水产复核集。

## 验证记录

验证方式: 使用实际 HTTP 请求访问页面和附件，使用 `BeautifulSoup` 核验 DOM，使用 `openpyxl` 解析 XLSX，使用 SHA-256 校验下载文件。

| URL | 结果 |
| --- | --- |
| `http://www.aqsc.agri.cn/` | 200，标题“农业农村部农产品质量安全中心” |
| `http://www.aqsc.agri.cn/tzgg/` | 200，15 条/页 |
| `http://www.aqsc.agri.cn/mtyx/tzgg/` | 200，5 页 |
| `http://www.aqsc.agri.cn/tznp/tzgg_10469/` | 200，3 页 |
| `http://www.aqsc.agri.cn/tzgg/202511/t20251128_468194.htm` | 200，含名特优新 XLSX 附件 |
| `http://www.aqsc.agri.cn/tzgg/202511/t20251128_468195.htm` | 200，含特质农品 XLSX 附件 |
| `http://www.aqsc.agri.cn/tzgg/202605/t20260527_472366.htm` | 200，HTML 内嵌名特优新表格 636 条数据 |
| `http://www.aqsc.agri.cn/tzgg/202605/t20260527_472367.htm` | 200，HTML 内嵌特质农品表格 148 条数据 |
| `http://www.aqsc.agri.cn/mtyx/tzgg/202609/t20260920_474564.htm` | 200，第 44 号公告，内嵌名特优新名单 |
| `http://www.aqsc.agri.cn/tznp/tzgg_10469/202609/t20260920_474561.htm` | 200，第 45 号公告，内嵌特质农品名单 |
| `https://jgs.moa.gov.cn/rzde/` | 200，标题“首页-认证登记” |
| `https://jgs.moa.gov.cn/rzde/202509/t20250908_6477077.htm` | 200，正文链接回 aqsc 公告 |
| `http://mtyx.aqsc.org/Home/Minglu/index.html` | 200，9038 条，452 页 |
| `http://mtyx.aqsc.org/Tznp/Tezhi/index` | 200，1265 条，64 页 |
| `http://www.aqsc.agri.cn/tzgg/202511/P020251225613822033339.xlsx` | 200，113937 bytes，XLSX 文件头有效 |
| `http://www.aqsc.agri.cn/tzgg/202511/P020251128359343750170.xlsx` | 200，24022 bytes，XLSX 文件头有效 |

## 审核要求

- 入口可打开: 通过。
- 样本可复现: 通过，3 条样本均能定位到公告页、附件和附件行。
- 字段映射完整: 通过，名特优新和特质农品分别映射，水产字段和来源字段均已定义。
- 详情 URL 可直达: 通过，样本使用公告详情页，不使用首页或列表页。
- 当前结论: `approved-with-gaps`。主要缺口是 robots 无明确规则、动态查询无单条详情、历史 PDF 和完整水产复核集尚未验证。
