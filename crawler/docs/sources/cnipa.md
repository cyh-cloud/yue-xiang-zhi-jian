# 国家知识产权局地理标志

来源 ID: `cnipa`

状态: `approved-with-gaps`

验证时间: `2026-10-19 01:09 Asia/Shanghai`

## 来源概况

- 名称: 国家知识产权局地理标志
- 域名: `www.cnipa.gov.cn`、`ggfw.cnipa.gov.cn`
- 主管机构: 国家知识产权局
- 内容域: 地理标志产品，农业、食品、饮料、酒类、中药材和水产
- 优先级: P0
- 访问等级: `public`
- `license_or_usage`: 政府公开信息，页面未发现可复用的明确开放许可声明。采集库可保存来源事实、原文快照和文件哈希；对外展示优先使用短摘要、结构化字段和原文链接，不发布第三方文章全文。
- `confidence`: 高。公告列表、产品级检索列表、详情接口和 PDF 下载均已实测；产品级完整目录仍受 PDF 表格解析影响。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 栏目首页 | `https://www.cnipa.gov.cn/col/col1388/index.html` | GET | 地理标志专题，链接检索系统、公告与文件 |
| 产品认定公告列表 | `https://www.cnipa.gov.cn/col/col1400/index.html` | GET | 41 条，分页参数 `uid=4536&pageNum=1..3`，每页 15 条 |
| 产品初步认定公告列表 | `https://www.cnipa.gov.cn/col/col1399/index.html` | GET | 栏目首页提供入口，本次未作为主采集入口 |
| 公告详情模式 | `https://www.cnipa.gov.cn/art/{yyyy}/{m}/{d}/art_1400_{article_id}.html` | GET | 正文、发布时间、公告号、落款日期和附件链接 |
| 附件下载 | `https://www.cnipa.gov.cn/module/download/downfile.jsp?classid=0&showname={name}.pdf&filename={hash}.pdf` | GET | 通常不需要临时签名，适合作为长期来源页 |
| 检索页 | `https://ggfw.cnipa.gov.cn/dlbzsq/dbQuery` | GET | Vue 单页应用，首屏请求 `search/init` |
| 检索详情页 | `https://ggfw.cnipa.gov.cn/dlbzsq/detail?id={id}&name={urlencoded_name}` | GET | 页面只展示一个 PDF 文件链接，实际文件地址由详情接口返回 |

## 公开 JSON 接口与分页

### 公告首页接口

- 请求方式: `GET https://ggfw.cnipa.gov.cn/dlbzsq/landmark/product/search/init`
- 查询参数: 无。实测附加 `type`、`page`、`pageNum`、`pageSize` 均不改变结果。
- 返回结构: `data` 是对象，键 `"1"` 和 `"2"` 分别对应两类公告，每类先返回 5 条。
- 公告类型:
  - `type=1`: 原质监总局地理标志保护产品批准公告。
  - `type=2`: 国家知识产权局地理标志保护产品批准或认定公告。
- 页面行为: 两个“更多 >”按钮分别打开对应列表，页面使用 Element UI 分页器，默认每页 10 条。

### 产品级公告列表接口

- 请求方式: `GET https://ggfw.cnipa.gov.cn/dlbzsq/landmark/product/search/list`
- 查询参数:
  - `name`: 标题关键词，空字符串表示不过滤。
  - `type`: `1` 或 `2`，必填。
  - `limit`: 每页数量。实测 `100` 可用。
  - `page`: 从 `1` 开始的页码。
- 返回结构:

```json
{
  "success": true,
  "errorCode": 200,
  "errorMsg": "成功",
  "data": {
    "count": 42,
    "data": [
      {
        "id": 541,
        "name": "国家知识产权局关于对临晋江石榴等58个产品予以地理标志产品认定的公告（第687号）",
        "announcement": null,
        "coding": "2026-08-03",
        "type": 2,
        "isDeleted": 0
      }
    ]
  },
  "happenTime": "2026-10-19 01:03:36.678"
}
```

- 分页字段: `data.count` 为总数，`data.data` 为当前页数组。
- 每页数量: `limit` 控制；页面默认 10 条，本次实测 100 条成功。
- 实测数量: `type=1` 共 495 条，`type=2` 共 42 条，合计 537 条公告。
- 筛选字段: 仅验证标题关键词 `name`。产品名称本身不在该接口返回，需解析 PDF。

### 详情接口

- 请求方式: `GET https://ggfw.cnipa.gov.cn/dlbzsq/landmark/product/search/detail?id={id}`
- 参数: `id` 为公告 ID，来自列表接口。
- 返回结构: `data` 为 PDF 临时签名 URL 字符串。
- 签名参数: `X-Amz-Algorithm=AWS4-HMAC-SHA256`、`X-Amz-Date`、`X-Amz-SignedHeaders=host`、`X-Amz-Expires=18000`、`X-Amz-Credential`、`X-Amz-Signature`。
- 签名有效期: 实测 `X-Amz-Expires=18000`，即约 5 小时。
- 不能长期复用: PDF URL 带临时签名，必须每次先调详情接口获取新 URL。去掉签名得到 `403 AccessDenied`，把有效期改为 1 秒得到 `403 ExpiredSignature`。

## 字段定位

### JSON API

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| `data.1[].id` | 旧公告 ID | `58` |
| `data.1[].name` | 公告标题 | `关于批准对南湖菱、东海（老）淮猪肉、乐平雪梨瓜、白蕉海鲈、乡城松茸实施地理标志产品保护的公告(2009年第89号)` |
| `data.1[].coding` | 旧公告文号 | `2009年第89号` |
| `data.1[].type` | 公告类型 | `1` |
| `data.2[].id` | 新公告 ID | `541` |
| `data.2[].name` | 公告标题 | `国家知识产权局关于对临晋江石榴等58个产品予以地理标志产品认定的公告（第687号）` |
| `data.2[].coding` | 新公告日期 | `2026-08-03` |
| `data.2[].type` | 公告类型 | `2` |
| `data.count` | 当前类型公告总数 | `42` |
| `data.data[].isDeleted` | 删除标记 | `0` |

### HTML DOM

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 公告列表项 | `.ulist li` | 国家知识产权局栏目列表 |
| 公告标题 | `.ulist li a` | 标题文本 |
| 公告日期 | `.ulist li span` | `YYYY-MM-DD` |
| 分页总数 | `.lucidity_pgToolbar span` | 第一处是总条数 |
| 公告详情标题 | `.index_title` | 详情页标题 |
| 公告发布时间 | `.index_time` | 国家知识产权局站点的发布日期 |
| 公告正文 | `.index_art_con` | 正文和附件链接 |
| 检索页关键词框 | `input[placeholder="关键词搜索"]` | 检索页输入框 |
| 检索页结果 | `.policyAnswersItem` | 每条含标题和日期 |
| 检索页分页 | `.el-pagination` | 总数和页码按钮 |

### 文件附件

| 文件名 | URL | 类型 | 大小 | 结构 |
| --- | --- | --- | --- | --- |
| `国家知识产权局关于对临晋江石榴等58个产品予以地理标志产品认定的公告（第687号）.pdf` | 通过 `detail?id=541` 获取签名 URL，路径为 `/qlrtp/objfile/bhxxpt/dbsbhz/UpLoadFile/approval/20260803/...pdf` | PDF | 1,174,529 bytes | 199 页；第 1 页公告正文，第 2-28 页左右为附件 1 产品表，第 29 页起为附件 2 保护要求 |
| `2009年第89号.pdf` | 通过 `detail?id=58` 获取签名 URL，路径为 `/qlrtp/objfile/bhxxpt/dbsbhz/UpLoadFile/approval/old/2009年第89号.pdf` | PDF | 250,603 bytes | 7 页；第 1-2 页公告正文与产品清单，第 2-7 页为 5 个产品质量技术要求 |
| `www-cnipa-539.pdf` | `https://www.cnipa.gov.cn/module/download/down.jsp?i_ID=186731&colID=1400` | PDF | 484,164 bytes | 6 页；第 1 页公告，第 2-3 页黄骅梭子蟹保护要求 |

## PDF 解析

- PDF URL 规律:
  - 2025 年后新公告常见 `/approval/{YYYYMMDD}/{URL编码标题}.pdf`。
  - 旧公告常见 `/approval/old/{文号}.pdf`。
  - 两类都追加 S3 签名查询参数。
- 解析方式: `pypdf.PdfReader(path).pages[i].extract_text()` 可提取文字和表格内容。新公告表格列被逐单元格换行，需按页重建行列；旧公告正文按“一、二、三”产品段落切分更稳定。
- 产品名称:
  - 新公告附件 1 表头为“序号 产品名称 省份 申请人 产地范围 备注”，每页重复表头。
  - 附件 2 以“N. 产品名称地理标志产品保护要求”分段，可从“一、地理标志产品名称”后提取名称。
- 地区:
  - 附件 1 直接给“省份”，市县或具体产区从“产地范围”提取。
  - 旧公告从“保护范围为...”提取。
- 公告号:
  - 新公告标题含“第 N 号”，PDF 第 1 页也有“第 N 号”。
  - 旧公告标题和 PDF 第 1 页含“YYYY年第N号”。
- 认定日期:
  - 新公告以落款日期为准，例如第 687 号 PDF 落款为 `2026 年 8 月 3 日`；栏目发布日期 `2026-08-12` 不是认定日期。
  - 旧公告落款为中文日期，例如 `二〇〇九年九月二十一日`，需转成 ISO 日期。
- 样本页结果:
  - 第 687 号第 29 页提取到“临晋江石榴”“临猗县临晋江石榴种植专业合作社”“山西省临猗县...”。
  - 第 687 号第 32 页提取到“莫力达瓦大豆”“莫力达瓦达斡尔族自治旗农畜产品质量安全中心”。
  - 第 539 号第 2 页提取到“黄骅梭子蟹”“河北省沧州市黄骅市人民政府”“河北省沧州市黄骅市南排河镇”。

## 真实样本

### 样本 1: 白蕉海鲈（水产）

- 详情 URL: `https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=58&name=%E5%85%B3%E4%BA%8E%E6%89%B9%E5%87%86%E5%AF%B9%E5%8D%97%E6%B9%96%E8%8F%B1%E3%80%81%E4%B8%9C%E6%B5%B7%EF%BC%88%E8%80%81%EF%BC%89%E6%B7%AE%E7%8C%AA%E8%82%89%E3%80%81%E4%B9%90%E5%B9%B3%E9%9B%AA%E6%A2%A8%E7%93%9C%E3%80%81%E7%99%BD%E8%95%89%E6%B5%B7%E9%B2%88%E3%80%81%E4%B9%A1%E5%9F%8E%E6%9D%BE%E8%8C%B8%E5%AE%9E%E6%96%BD%E5%9C%B0%E7%90%86%E6%A0%87%E5%BF%97%E4%BA%A7%E5%93%81%E4%BF%9D%E6%8A%A4%E7%9A%84%E5%85%AC%E5%91%8A%282009%E5%B9%B4%E7%AC%AC89%E5%8F%B7%29`
- 公告详情 URL: 国家知识产权局栏目未检索到对应文章，使用检索系统详情页和 PDF 作为直达来源。
- 抓取时间: `2026-10-19 01:04 Asia/Shanghai`
- 关键字段:
  - 产品名称: 白蕉海鲈
  - 公告号: 2009年第89号
  - 公告日期: 2009-09-21
  - 地区: 广东省珠海市斗门区
  - 产地范围: 广东省珠海市斗门区现辖行政区域内，东经 113°05′ 至 113°25′，北纬 21°59′ 至 22°25′
  - 类别: 水产
- 目标映射: `agri_certified_products`，`cert_type=地理标志`；来源记录指向 `agri_product_sources`。

### 样本 2: 黄骅梭子蟹（水产）

- 详情 URL: `https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=513&name=%E5%9B%BD%E5%AE%B6%E7%9F%A5%E8%AF%86%E4%BA%A7%E6%9D%83%E5%B1%80%E5%85%B3%E4%BA%8E%E6%89%B9%E5%87%86%E5%AF%B9%E9%BB%84%E9%AA%85%E6%A2%AD%E5%AD%90%E8%9F%B9%E7%AD%89%E4%BA%A7%E5%93%81%E5%AE%9E%E6%96%BD%E5%9C%B0%E7%90%86%E6%A0%87%E5%BF%97%E4%BA%A7%E5%93%81%E4%BF%9D%E6%8A%A4%E7%9A%84%E5%85%AC%E5%91%8A%EF%BC%88%E7%AC%AC539%E5%8F%B7%EF%BC%89`。仅传 `id=513` 时页面文件名显示为 `.pdf`，带上 `name` 可稳定显示文件名。
- 公告详情 URL: `https://www.cnipa.gov.cn/module/download/down.jsp?i_ID=186731&colID=1400`。该列表项直接链接 PDF，没有独立 HTML 详情页。
- 抓取时间: `2026-10-19 01:06 Asia/Shanghai`
- 关键字段:
  - 产品名称: 黄骅梭子蟹
  - 公告号: 第539号
  - 公告日期: 2023-08-01（PDF 落款）；栏目日期 2023-08-03
  - 地区: 河北省沧州市黄骅市
  - 申请机构: 河北省沧州市黄骅市人民政府
  - 产地范围: 河北省沧州市黄骅市南排河镇的沿海滩涂及近海海域
  - 类别: 水产
- 目标映射: `agri_certified_products`，`cert_type=地理标志`；来源记录指向 `agri_product_sources`。

### 样本 3: 临晋江石榴（普通农产品，表格解析样本）

- 详情 URL: `https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541&name=%E5%9B%BD%E5%AE%B6%E7%9F%A5%E8%AF%86%E4%BA%A7%E6%9D%83%E5%B1%80%E5%85%B3%E4%BA%8E%E5%AF%B9%E4%B8%B4%E6%99%8B%E6%B1%9F%E7%9F%B3%E6%A6%B4%E7%AD%8958%E4%B8%AA%E4%BA%A7%E5%93%81%E4%BA%88%E4%BB%A5%E5%9C%B0%E7%90%86%E6%A0%87%E5%BF%97%E4%BA%A7%E5%93%81%E8%AE%A4%E5%AE%9A%E7%9A%84%E5%85%AC%E5%91%8A%EF%BC%88%E7%AC%AC687%E5%8F%B7%EF%BC%89`
- 国家知识产权局详情 URL: `https://www.cnipa.gov.cn/art/2026/8/12/art_1400_207705.html`
- 抓取时间: `2026-10-19 01:04 Asia/Shanghai`
- 关键字段:
  - 产品名称: 临晋江石榴
  - 公告号: 第687号
  - 认定日期: 2026-08-03
  - 省份: 山西省
  - 申请人: 临猗县临晋江石榴种植专业合作社
  - 产地范围: 山西省临猗县东张镇、耽子乡、临晋镇、嵋阳镇、北景乡、猗氏镇 6 个乡镇
  - 类别: 水果
- 目标映射: `agri_certified_products`，`cert_type=地理标志`；来源记录指向 `agri_product_sources`。

## 范围分类

- 纳入:
  - 农业: 水果、蔬菜、粮油、茶叶、食用菌、畜禽等。
  - 食品: 调味品、酱腌菜、豆制品、糕点、食用油脂等。
  - 饮料: 茶、咖啡、果汁及非酒精饮料。
  - 酒类: 白酒、黄酒、葡萄酒、啤酒及其他酒类。
  - 中药材: 药材、饮片原料和药食同源产品。
  - 水产: 鱼、虾、蟹、贝、藻、海参、鲍鱼等。
- 排除:
  - 纯工艺品: 刺绣、木雕、砚台、陶瓷、花炮等。
  - 非食品工业品: 玉石、建材、化工品、机械产品等。
  - 排除原因保存到 `agri_product_sources.exclusion_reason` 或等价字段，保留原文名称、公告 ID 和 PDF 页码，便于复核。
- 分类方法:
  - 先按产品名称和申请人所在地建立候选。
  - 再按 PDF 中的“质量要求”“种源”“品种”“栽培管理”“养殖管理”“加工工艺”等段落判定类别。
  - 名称有歧义时保留 `category=unknown` 并进入人工复核，不猜测。
  - `cert_type` 固定为 `地理标志`，与名特优新、特质农品分开。

## 字段映射

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| 公告 ID | `agri_product_sources.source_record_id` | `agri_product_sources.source_record_id` | 保留检索系统 ID，去掉签名参数 |
| 公告标题 | `agri_product_sources.title` | `agri_product_sources.title` | 原样保存 |
| 公告文号或日期 | `agri_product_sources.announcement_no` | `agri_product_sources.announcement_no` | 旧公告用 `2009年第89号`，新公告用 `第687号` |
| 栏目发布日期 | `agri_product_sources.published_at` | `agri_product_sources.published_at` | 与认定日期分开 |
| PDF 落款日期 | `agri_certified_products.certified_at` | `agri_certified_products.certified_at` | 归一为 `YYYY-MM-DD` |
| 产品名称 | `agri_certified_products.product_name` | `agri_certified_products.product_name` | 去掉换行和多余空格 |
| 省份 | `agri_certified_products.province` | `agri_certified_products.province` | 附件 1 表格 |
| 市县或产区 | `agri_certified_products.region` | `agri_certified_products.region` | 从产地范围提取，无法确定时保留全文到 `origin_scope` |
| 产地范围 | `agri_certified_products.origin_scope` | `agri_certified_products.origin_scope` | 保留原文 |
| 申请人或申请机构 | `agri_certified_products.applicant` | `agri_certified_products.applicant` | 附件 1 与保护要求可能不同，冲突时保留两值 |
| 产品类别 | `agri_certified_products.category` | `agri_certified_products.category` | 按范围分类规则枚举 |
| 认证类型 | `agri_certified_products.cert_type` | `agri_certified_products.cert_type` | 固定 `地理标志` |
| PDF URL | `agri_product_sources.source_url` | `agri_product_sources.source_url` | 长期链接优先用国家知识产权局附件页；签名 URL 只进 raw 层 |
| 详情页 URL | `agri_product_sources.detail_url` | `agri_product_sources.detail_url` | 检索系统详情页或国家知识产权局文章页 |
| PDF 哈希 | `raw.files.sha256` | 不直接入库 | 用于变更检测和重跑校验 |

建议目标表约束:

- 自然键: `cert_type + product_name + province + region`，缺少 `region` 时使用 `origin_scope` 的稳定摘要参与去重。
- `cert_type=地理标志`。
- `source_id=cnipa`。
- 同一产品多次公告时保留最新有效记录，旧公告进入来源历史。
- 人工修改字段不自动覆盖。

## 数据量与更新

- 公告数量: `type=1` 495 条，`type=2` 42 条，共 537 条。
- 产品数量: 只能从 PDF 统计。标题中明确写出产品数的 39 条公告合计 3,288 个产品，另有 498 条旧公告标题不含数量。按标题粗估不能作为全量口径。
- 已知大公告: 第 640 号含 1,409 个产品；第 646 号含 870 个产品；第 687 号含 58 个产品。
- 更新频率: 不定期，国家知识产权局发布新认定或保护公告时更新。
- 变更检测: 每轮抓取 `search/list` 的 `id`、`count` 和标题；对已存在 ID 比较详情接口返回的 PDF 路径，对新增 ID 下载并解析。
- 建议采集频率: 每周检查一次列表，发现新公告后抓取 PDF；历史全量回填一次。
- 历史数据保留: 保留公告列表快照、PDF 哈希和解析结果；签名 URL 不长期保存。

## 风险与限制

- 登录: 未发现登录要求。检索页有免责声明弹窗，关闭或接受后可正常查询。
- robots: `https://www.cnipa.gov.cn/robots.txt` 返回 404；`https://ggfw.cnipa.gov.cn/robots.txt` 和 `/dlbzsq/robots.txt` 返回 HTML 单页应用，不是有效 robots 文件。按公开政府信息访问，仍应限速并避免高并发。
- 版权: 页面标注“版权所有：国家知识产权局”，未发现开放许可。采集库保存原文用于事实核验，业务库只发布结构化字段、短摘要和原文链接。
- 结构稳定性: 产品级列表接口未在页面源码中直接出现，来自前端网络请求，升级后可能改名。国家知识产权局栏目列表可作为备用发现入口。
- 签名过期: PDF URL 约 5 小时过期，不能写入长期字段或作为详情 URL。
- PDF 解析: 新公告表格按单元格换行，简单文本提取会产生列错位；需要按页表头、序号和“附件 2”分段重建。
- 缺失字段: 列表接口没有产品名称、地区、类别和认定日期，均需 PDF 或 HTML 详情补全。
- 公告日期差异: 栏目发布日期、PDF 落款日期和公告编号日期可能不同，必须分别保存。

## 未验证项

- 未验证产品级 JSON 接口是否直接返回产品数组；当前只确认公告级列表。
- 未穷举全部 537 个 PDF 的大小，未发现超过 100MB 的样本。
- 未验证 2026 年 8 月之后的新公告是否有新接口版本。
- 未验证国家知识产权局栏目列表是否覆盖检索系统中的全部旧公告。
- 未验证所有 PDF 的文字层质量；扫描版公告需要 OCR。

## 验证记录

- 验证方式: Playwright 打开栏目首页、产品认定公告列表、详情页和检索页；实际 HTTP 请求 `search/init`、`search/list`、`search/detail`；下载并解析 3 份 PDF。
- 验证结果: 接口可用，分页和详情签名行为可复现，样本可打开，PDF 可解析。
- 未验证项: 见上节。

## 审核要求

- 入口可打开: 是。
- 样本可复现: 是，3 条样本均有详情 URL。
- 字段映射完整: 主体字段已映射，产物级全量目录需完成 PDF 表格解析后确认。
- 详情 URL 可直达: 是。检索系统详情页可直达；签名 PDF URL 不写入长期详情字段。

