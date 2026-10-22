# 和风天气免费开发版

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `qweather`

状态: `draft`

权利状态: `attribution-required`

访问等级: `public`

验证时间: `2026-10-20 Asia/Shanghai`

## 来源概况

- 名称: 和风天气
- 域名: `www.qweather.com`、`devapi.qweather.com`
- 内容域: `weather`
- 优先级: P1
- `license_or_usage`: 只使用免费开发版和免费数据，不接商业或付费套餐。免费额度、字段权限和署名要求以开发者控制台及官方文档为准。
- `rights_status`: `attribution-required`
- `attribution_text`: `和风天气 QWeather`
- 用途边界: 只做运行时天气 DTO 和短期缓存，不建立历史天气表。

## 入口与请求

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 官网 | `https://www.qweather.com/` | GET | 产品入口 |
| 开发者文档 | `https://dev.qweather.com/docs/configuration/` | GET | 配置、认证和免费版说明 |
| 当前天气候选 | `https://devapi.qweather.com/v7/weather/now?location={location}&key={api_key}` | GET | 免费开发版候选端点，具体权限以控制台为准 |

API Key 只从本机环境变量或本地未跟踪会话配置读取，不进入仓库、日志、样本或提交。请求按城市批量缓存，不在循环中重试。

## 字段映射

| 来源字段 | 运行时 DTO 字段 | 说明 |
| --- | --- | --- |
| `location` | `location` | 请求位置 |
| `now.obsTime` | `observed_at` | 保留原始时间并标注时区 |
| `now.temp` | `temperature_c` | 摄氏度 |
| `now.text` | `condition_text` | 天气现象 |
| `now.icon` | `condition_code` | 图标代码 |
| 响应正文 | `content_hash` | 只对正文计算，headers 哈希不作为版本 |
| 请求 URL | `source_url` | 运行时追溯地址，不包含 API Key |

## 风险与限制

- 免费开发版的日调用量、字段权限和限流尚未在控制台核实。
- 不接入付费套餐，不保存历史天气，不把 Key 写入任何跟踪文件。
- 署名和商业使用边界必须在真实接入前复核。
- 具体端点、参数和错误码以当前官方文档为准。

## 审核要求

- 入口可打开: 待真实请求核验
- 样本可复现: 待真实请求核验
- 字段映射完整: 待端点核验
- 详情 URL 可直达: 待真实请求核验
- 合规结论: `draft`，仅登记免费候选，不进入首批业务发布
