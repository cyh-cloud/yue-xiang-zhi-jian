# 天气 API 候选字段映射

状态: draft

日期: 2026-10-19

本文只记录中国天气网实时天气、预报和预警的候选字段，不建立历史天气表。天气不是采集库的长期事实源，只服务于后续农时提示。

## 已验证入口

| 用途 | URL | 状态 |
| --- | --- | --- |
| 城市编码资源 | `https://j.i8tq.com/weather2020/search/city.js` | 已验证，3221 个 `AREAID` 节点 |
| 当前天气页面 | `https://www.weather.com.cn/weather1d/{AREAID}.shtml` | 已验证 |
| 实时天气候选 | `https://d1.weather.com.cn/sk_2d/{AREAID}.html` | 已验证，返回 `var dataSK={...};` |
| 7 天预报页面 | `https://www.weather.com.cn/weather/{AREAID}.shtml` | 已验证页面，字段结构待验证 |
| 预警 | 来源文档未记录稳定公开 API | 待验证 |

## 候选字段

| 业务字段 | 来源字段或位置 | 运行时 DTO 字段 | 运行时 DTO | 说明 |
| --- | --- | --- | --- | --- |
| 城市编码 | `city` | `dto.city_code` | `city_code` | 字符串，保留前导零 |
| 城市名 | `cityname` | `city_name` | `city_name` | 直接映射 |
| 城市英文标识 | `nameen` | `city_slug` | 不展示 | 可作日志标识 |
| 当前天气 | `weather`、`weathercode` | `condition_text`、`condition_code` | 同名 | 天气现象和代码分开 |
| 当前温度 | `temp` | `temperature_c` | `temperature_c` | 摄氏度，保留一位小数 |
| 华氏温度 | `tempf` | `temperature_f` | 不展示 | 只作核对 |
| 体感温度 | 未验证 | `feels_like_c` | `feels_like_c` | 来源文档未记录，待验证 |
| 风向 | `WD`、`wde` | `wind_direction`、`wind_direction_code` | 同名 | 中文和英文代码分开 |
| 风力 | `WS` | `wind_level` | `wind_level` | 保留“1级”等原文 |
| 风速 | `wse` | `wind_speed` | `wind_speed` | 保留原字符串 |
| 湿度 | `SD` | `humidity` | `humidity` | 去掉百分号时另存原文 |
| 气压 | `qy` | `pressure_hpa` | `pressure_hpa` | 转数值 |
| 能见度 | `njd` | `visibility` | `visibility` | 保留原字符串 |
| 当前降雨 | `rain` | `rain_current` | `rain_current` | 转数值 |
| 24 小时降雨 | `rain24h` | `rain_24h` | `rain_24h` | 转数值 |
| 空气质量 | `aqi`、`aqi_pm25` | `aqi`、`aqi_pm25` | `aqi` | `aqi_pm25` 可只作诊断 |
| 观测时间 | `date` + `time` | `observed_at` | `observed_at` | 来源只有时分，必须结合日期和抓取日期 |
| 发布日期 | `date` | `observed_date_raw` | 不展示 | 中文日期，需解析 |
| 取回时间 | 响应取得时间 | `fetched_at` | `fetched_at` | ISO 8601 含时区 |
| 来源 URL | 请求 URL | `source_url` | `source_url` | 实时接口地址 |
| 内容哈希 | 规范化响应正文 | `content_hash` | `content_hash` | 变化检测 |
| 预报日期 | 7 天页面，待验证 | `forecast_date` | `forecast_date` | 只记录候选，不建历史表 |
| 预报天气 | 7 天页面，待验证 | `forecast_condition` | `forecast_condition` | 待验证选择器 |
| 预报最高温 | 7 天页面，待验证 | `forecast_temp_high` | `forecast_temp_high` | 待验证 |
| 预报最低温 | 7 天页面，待验证 | `forecast_temp_low` | `forecast_temp_low` | 待验证 |
| 预警类型 | 未验证 | `warning_type` | `warning_type` | 不推测来源结构 |
| 预警等级 | 未验证 | `warning_level` | `warning_level` | 待验证 |
| 预警标题 | 未验证 | `warning_title` | `warning_title` | 待验证 |
| 预警发布时间 | 未验证 | `warning_published_at` | `warning_published_at` | 待验证 |

## 不建历史天气表

- 不创建 `weather_history`、`weather_hourly` 或长期天气快照表。
- raw 层可以保存短期响应用于排错，必须记录 `fetched_at` 和 TTL。
- 不建立 std 天气表；每次请求只在内存组装运行时 DTO。
- 业务库不保存天气快照。

## 运行时实现

- 中国天气网、Open-Meteo 和和风天气使用独立来源 ID，免费层和配额写在各自来源元数据中。
- 中国天气网 DTO 由 `dataSK` 正文解析，保留 `city_code`、`observed_at`、`fetched_at` 和 `source_url`。
- 内容版本只使用正文 `content_hash`；headers 哈希只作为单次取回证据，不参与变更判断。

## 农时提示接入点

后续农时提示从 `farming_tasks`、`farming_phenophases` 和作物订阅获得任务，再按地区城市编码请求实时天气候选，在响应时组装提示:

- 输入: `product_id`、`task_id`、`city_code`、`observed_at`、天气字段。
- 输出: 任务标题、日期、天气摘要、来源链接、取回时间和时效提示。
- 只使用温度、降雨、风力、湿度和更新时间等与作业相关的字段。
- 城市级天气不能解释为地块级气象条件。
- 气象预警不能由模型自行生成，来源没有稳定预警字段时明确显示“待接入”。
- 天气只作参考，页面提示用户以当地气象部门预警为准。

## 授权与稳定性

- 实时接口是网页运行时辅助接口，不是公开文档化 API。
- 未发现 API 复用许可、配额和 SLA，正式上线前需确认授权、署名和调用频率。
- `d1.weather.com.cn/robots.txt` 返回 403，不能据此推断允许或无限制。
- 实时值会变化，文档中的样本只证明结构，不是稳定事实。

## 已知缺口

- 预警 API 和字段未验证。
- 7 天预报的稳定 DOM 或 API 字段未验证。
- `time` 只有时分，跨午夜时需要日期校正。
- 城市编码文件由第三方域名提供，长期稳定性待验证。

## 待验证

- 预警入口、预警等级枚举和更新时间。
- 预报字段是否值得进入运行时 DTO。
- 农时提示的具体接口形状和缓存 TTL。
- API 授权、配额和署名要求。
