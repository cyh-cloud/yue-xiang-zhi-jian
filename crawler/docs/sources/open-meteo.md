# Open-Meteo 免费天气接口

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `open-meteo`

状态: `draft`

权利状态: `attribution-required`

访问等级: `public`

验证时间: `2026-10-20 Asia/Shanghai`

## 来源概况

- 名称: Open-Meteo
- 域名: `open-meteo.com`、`api.open-meteo.com`
- 内容域: `weather`
- 优先级: P1
- `license_or_usage`: 官方许可证页提供非商业免费层，要求保留来源署名。正式使用前仍需按当前许可证页复核字段范围、配额和署名文本。
- `rights_status`: `attribution-required`
- `attribution_text`: `Weather data by Open-Meteo.com`
- 用途边界: 只做运行时天气 DTO 和短期缓存，不建立历史天气表，不接付费套餐。

## 入口与请求

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 官网 | `https://open-meteo.com/` | GET | 产品与免费层入口 |
| 许可证 | `https://open-meteo.com/en/license` | GET | 非商业使用和署名要求 |
| 当前天气候选 | `https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m` | GET | 免费层候选端点，具体字段和配额以官方文档为准 |

接口使用经纬度定位，不依赖本站城市编码。请求必须设置明确的 User-Agent，按城市或业务区域批量请求，并在进程内缓存短期结果。

## 字段映射

| 来源字段 | 运行时 DTO 字段 | 说明 |
| --- | --- | --- |
| `latitude` | `latitude` | 请求位置 |
| `longitude` | `longitude` | 请求位置 |
| `current.time` | `observed_at` | 保留原始时间并标注时区 |
| `current.temperature_2m` | `temperature_c` | 摄氏度 |
| `current.weather_code` | `condition_code` | 官方 WMO 代码，翻译表另行冻结 |
| 响应正文 | `content_hash` | 只对正文计算，headers 哈希不作为版本 |
| 请求 URL | `source_url` | 运行时追溯地址 |

## 风险与限制

- 免费额度、字段可用性和限流尚未通过真实请求核验。
- 不保存长期天气历史，不把天气结果当作地块级气象事实。
- 必须保留 Open-Meteo 署名，不接入付费 API。
- 具体端点、参数和许可证文本在实现前必须再次核对官方页面。

## 审核要求

- 入口可打开: 待真实请求核验
- 样本可复现: 待真实请求核验
- 字段映射完整: 待端点核验
- 详情 URL 可直达: 待真实请求核验
- 合规结论: `draft`，仅登记免费候选，不进入首批业务发布
