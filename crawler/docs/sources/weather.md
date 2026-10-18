# 中国天气网

来源 ID: `weather`

状态: `approved-with-gaps`

验证时间: `2026-10-19 01:04 Asia/Shanghai`

## 来源概况

- 名称: 中国天气网
- 域名: `www.weather.com.cn`，实时数据候选接口使用 `d1.weather.com.cn`，城市编码资源使用 `j.i8tq.com`
- 主管机构: 中国气象局公共气象服务中心体系内站点，页面主办信息以站内公告为准
- 内容域: `weather`
- 优先级: P1
- 访问等级: `public`
- `license_or_usage`: 未发现 API 复用许可或 SLA。当前接口属于网页运行时辅助接口，不是公开文档化 API；正式上线前应向运营方确认授权、配额和署名要求。
- `confidence`: 中。城市编码、页面和实时返回已实测，接口稳定性与授权待确认。
- 用途边界: 只登记实时天气 API 候选和城市编码入口，供后续农时天气提示调用。不建立历史天气表，不保存长期天气快照。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `https://www.weather.com.cn/` | GET | 返回 200，页面内提供城市搜索和天气入口 |
| 城市编码资源 | `https://j.i8tq.com/weather2020/search/city.js` | GET | JavaScript 对象，按省、市、区县组织，每个末端节点含 `AREAID` |
| 当前天气页面模式 | `https://www.weather.com.cn/weather1d/{AREAID}.shtml` | GET | 例如北京 `101010100`，广州 `101280101`，返回 200 |
| 实时天气 API 候选 | `https://d1.weather.com.cn/sk_2d/{AREAID}.html` | GET | 返回 `var dataSK={...};`，浏览器端接口，需带网页 Referer 实测 |
| 7 天预报页面 | `https://www.weather.com.cn/weather/{AREAID}.shtml` | GET | 仅作提示补充，不纳入本次实时 API 契约 |

城市编码资源是城市名称到 `AREAID` 的权威入口示例。`area` 编码按行政区层级组织，当前文件可解析出 3221 个 `AREAID` 节点。业务侧只需维护实际服务区域所需的编码，不必全量加载。

## 请求与分页

- 请求方式: GET
- 查询参数: 实时接口无查询字符串，`AREAID` 写在路径中
- 必要请求头: `User-Agent` 为常规浏览器；实测建议带 `Referer: https://www.weather.com.cn/weather1d/{AREAID}.shtml`
- 响应类型: `text/html; charset=UTF-8`，正文实际是 JavaScript 变量赋值
- 分页字段: 不适用
- 每页数量: 不适用
- 总数字段: 不适用
- 筛选字段: 不适用
- 城市筛选: 先用城市编码资源选 `AREAID`，再请求实时接口

返回正文示例结构:

```text
var dataSK={"city":"101010100","cityname":"北京",...};
```

解析时应去除 `var dataSK=` 前缀和末尾分号，再把对象部分作为 JSON 读取。响应不是严格 JSON API，错误处理和字段变更检测必须允许正文格式变化。

## 字段定位

### JSON API

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| `nameen` | 城市英文标识 | `beijing` |
| `cityname` | 城市中文名 | `北京` |
| `city` | `AREAID` 城市编码 | `101010100` |
| `temp` | 当前气温，摄氏度 | `6.1` |
| `tempf` | 当前气温，华氏度 | `43` |
| `WD` | 风向中文 | `西风` |
| `wde` | 风向英文缩写 | `W` |
| `WS` | 风力等级 | `1级` |
| `wse` | 风速 | `2km/h` |
| `SD` | 相对湿度 | `89%` |
| `sd` | 相对湿度重复字段 | `89%` |
| `qy` | 气压 | `1017` |
| `njd` | 能见度 | `18km` |
| `time` | 观测时间，返回时只有时分 | `00:45` |
| `rain` | 当前降雨量 | `0` |
| `rain24h` | 24 小时降雨量 | `0` |
| `aqi` | 空气质量指数 | `23` |
| `aqi_pm25` | PM2.5 分指数 | `23` |
| `weather` | 天气现象中文 | `晴` |
| `weathere` | 天气现象英文 | `Sunny` |
| `weathercode` | 天气现象代码 | `d00` |
| `limitnumber` | 车辆限行提示 | `不限行` |
| `date` | 日期描述 | `10月19日(星期一)` |

### HTML DOM

当前天气页面可作为 API 不可用时的诊断和备用定位，不建议作为主采集方式。

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 页面摘要 | `#hidden_title` | 样本值为 `10月18日20时 周日  晴  5/19°C` |
| 页面更新时间 | `#fc_24h_internal_update_time` | 样本值为 `2026-10-18 18:00` |
| 3 小时预报更新时间 | `#fc_3h_internal_update_time` | 样本值为 `2026-10-18 18:00` |
| 7 天更新时间 | `#zs_7d_update_time` | 样本值为 `2026-10-18 20:00:00.0` |
| 夜间天气 | `#today li:nth-child(1) p.wea` | 样本值为 `晴` |
| 夜间最低温 | `#today li:nth-child(1) p.tem span` | 样本值为 `5` |
| 白天天气 | `#today li:nth-child(2) p.wea` | 样本值为 `晴` |
| 白天最高温 | `#today li:nth-child(2) p.tem span` | 样本值为 `19` |
| 风向风力 | `#today li p.win span[title]` | `title` 例如 `南风`，文本例如 `<3级` |
| 3 小时序列 | 页面脚本 `var hour3data={...}` | 字符串数组，字段顺序为时间、天气代码、天气、温度、风向、风力、昼夜标记 |

### 文件附件

本来源未发现需要登记的公告附件。

## 真实样本

### 样本 1

- 详情 URL: `https://d1.weather.com.cn/sk_2d/101010100.html`
- 页面 URL: `https://www.weather.com.cn/weather1d/101010100.shtml`
- 抓取时间: `2026-10-19 01:04 Asia/Shanghai`
- 关键字段: `cityname=北京`，`city=101010100`，`temp=6.1`，`weather=晴`，`WD=西风`，`WS=1级`，`SD=89%`，`rain=0`，`rain24h=0`，`aqi=23`，`time=00:45`，`date=10月19日(星期一)`
- 目标映射: `std_weather_candidate` 的北京实时观测候选，不落历史表

### 样本 2

- 详情 URL: `https://d1.weather.com.cn/sk_2d/101280101.html`
- 页面 URL: `https://www.weather.com.cn/weather1d/101280101.shtml`
- 抓取时间: `2026-10-19 01:04 Asia/Shanghai`
- 关键字段: `cityname=广州`，`city=101280101`，`temp=23.5`，`weather=晴`，`WD=北风`，`WS=2级`，`SD=94%`，`rain=0`，`rain24h=0`，`aqi=26`，`time=00:45`，`date=10月19日(星期一)`
- 目标映射: `std_weather_candidate` 的广州实时观测候选，不落历史表

## 字段映射

### crawler std 层

建议使用临时标准实体 `std_weather_candidate` 承接一次请求，不建立 `weather_history` 表。该实体可以写入 raw 响应索引，但标准层只保留最近一次候选供调试和转换使用。

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| `city` | `std_weather_candidate.city_code` | 运行时提示 DTO `city_code` | 城市自然键，保留字符串 |
| `cityname` | `std_weather_candidate.city_name` | 运行时提示 DTO `city_name` | 直接映射 |
| `nameen` | `std_weather_candidate.city_slug` | 运行时提示 DTO `city_slug` | 可用于日志，不用于展示 |
| `temp` | `std_weather_candidate.temperature_c` | 运行时提示 DTO `temperature_c` | 转数值，保留一位小数 |
| `tempf` | `std_weather_candidate.temperature_f` | 不展示 | 保留原始值用于核对 |
| `weather` | `std_weather_candidate.condition_text` | 运行时提示 DTO `condition_text` | 直接映射 |
| `weathercode` | `std_weather_candidate.condition_code` | 运行时提示 DTO `condition_code` | 直接映射 |
| `WD` | `std_weather_candidate.wind_direction` | 运行时提示 DTO `wind_direction` | 直接映射 |
| `WS` | `std_weather_candidate.wind_level` | 运行时提示 DTO `wind_level` | 直接映射 |
| `wse` | `std_weather_candidate.wind_speed` | 运行时提示 DTO `wind_speed` | 保留原字符串 |
| `SD` | `std_weather_candidate.humidity` | 运行时提示 DTO `humidity` | 去掉百分号存入，另保留原文 |
| `qy` | `std_weather_candidate.pressure_hpa` | 运行时提示 DTO `pressure_hpa` | 转数值 |
| `njd` | `std_weather_candidate.visibility` | 运行时提示 DTO `visibility` | 保留原字符串 |
| `rain` | `std_weather_candidate.rain_current` | 运行时提示 DTO `rain_current` | 转数值 |
| `rain24h` | `std_weather_candidate.rain_24h` | 运行时提示 DTO `rain_24h` | 转数值 |
| `aqi` | `std_weather_candidate.aqi` | 运行时提示 DTO `aqi` | 转整数 |
| `aqi_pm25` | `std_weather_candidate.aqi_pm25` | 不展示 | 保留供诊断 |
| `limitnumber` | `std_weather_candidate.traffic_limit` | 不展示 | 与农时提示无关，可丢弃 |
| `time` | `std_weather_candidate.observed_time_raw` | 运行时提示 DTO `observed_at` | 与 `date`、抓取日期组合为完整时间 |
| `date` | `std_weather_candidate.observed_date_raw` | 运行时提示 DTO `observed_at` | 解析中文日期和星期 |
| 响应正文 | `std_weather_candidate.content_hash` | 运行时提示 DTO `content_hash` | 对规范化正文计算 SHA-256 |
| 请求 URL | `std_weather_candidate.source_url` | 运行时提示 DTO `source_url` | 原始接口 URL |
| 抓取时间 | `std_weather_candidate.fetched_at` | 运行时提示 DTO `fetched_at` | 必须随响应保存 |

### 粤乡智匠建议表

不建天气表。后续农时提示接口可按请求实时读取候选，在内存中组装以下字段并标注来源与取得时间:

- `city_code`
- `city_name`
- `temperature_c`
- `condition_text`
- `wind_direction`
- `wind_level`
- `humidity`
- `rain_current`
- `rain_24h`
- `aqi`
- `observed_at`
- `fetched_at`
- `source_url`

农时提示只使用与作业相关的字段，例如温度、降雨、风力、湿度和更新时间。页面必须提示天气为实时参考值，不能替代当地气象预警。

## 数据量与更新

- 当前数量估算: 城市编码资源含 3221 个 `AREAID`
- 更新频率: 实时接口通常每 10 至 30 分钟更新一次，页面各模块更新时间不一致
- 变更检测: 以 `city + observed_at + content_hash` 判断；`time` 未变化或明显落后于抓取时间时标记为陈旧
- 建议采集频率: 只对平台服务区域按需轮询，建议 15 至 30 分钟一次；同一轮请求设置间隔和缓存
- 历史数据保留: 不保留历史天气表。raw 响应只用于短期排错，不作为业务历史事实源

## 风险与限制

- 登录: 不需要
- robots: `https://www.weather.com.cn/robots.txt` 返回 `User-agent: * / Allow: /`；`https://d1.weather.com.cn/robots.txt` 返回 403，不能据此推断接口授权
- 版权: 站点内容版权归中国天气网及相应权利人。接口未提供明确复用许可，业务上线前需确认授权
- 结构稳定性: API 返回 `text/html` 包裹 JavaScript，字段可能无公告变更
- 缺失字段: 没有分钟级观测时间、预警等级、土壤墒情和农业气象专用指标
- 时效风险: `time` 只有时分，必须用 `date` 和抓取日期补齐；跨午夜时需防止日期错位
- 接口风险: 直接依赖网页内部接口可能被限流、加签或下线
- 农时提示边界: 不将城市级天气解释为地块级气象条件，不输出灌溉、施药等强结论

## 验证记录

- 验证方式: 实际 HTTP GET，使用浏览器 User-Agent 和页面 Referer；解析返回对象并对 DOM 选择器做静态定位核对
- 验证结果: 首页、城市编码资源、北京和广州实时接口、北京当前天气页均返回 200
- 未验证项: API 正式授权、长期稳定性、并发配额、跨网络可用性、分钟级刷新间隔

## 下载记录

所有文件均小于 100MB，无需 `OVERSIZE.md`。

| 文件 | URL | 大小 | SHA-256 |
| --- | --- | ---: | --- |
| `home.html` | `https://www.weather.com.cn/` | 139824 | `604D2297F9EB4A7AC105A923DF8C8561380A283E4843A35E5F903DA265C270A8` |
| `home.headers` | `https://www.weather.com.cn/` | 760 | `815B42CEB4FF0A27689D3C50C2A984A45A1A850BE9DAB41BF7A079DE0C0FF230` |
| `robots.txt` | `https://www.weather.com.cn/robots.txt` | 23 | `16CEB5EE3E0DC13AA9ADF31A3EBBE45A1D965B8C2B9F72EAF84E5911E140ED95` |
| `robots.headers` | `https://www.weather.com.cn/robots.txt` | 884 | `928F5FA7CDA1D4B3AC3E130FE70F114D235CEFA541A21D56CEDCF77860555216` |
| `city-list.js` | `https://j.i8tq.com/weather2020/search/city.js` | 382564 | `9F0E940707C99EA192B709D176A40FDC3CE647027715757840DA42AB64162B8A` |
| `city-list.headers` | `https://j.i8tq.com/weather2020/search/city.js` | 654 | `92DD9FA0F0D4A407CECCC64A0FA9E5CFC56D4817B6964D426A31390897B4E843` |
| `weather1d-101010100.html` | `https://www.weather.com.cn/weather1d/101010100.shtml` | 75505 | `4BCFAC3E13D136F00EA3F446877BB906434190300EB35C150AA2263D033AEBF6` |
| `weather1d-101010100.headers` | `https://www.weather.com.cn/weather1d/101010100.shtml` | 775 | `23FD1711D1AA75FFC6E70009C9FBF73E68881DD86090161288C02AAD53D523D4` |
| `sk-beijing.json` | `https://d1.weather.com.cn/sk_2d/101010100.html` | 373 | `0C788A9EA6056EA0D2BBE6BD3DD657D4948E2C38C238FB83870FCDE93A0448B3` |
| `sk-beijing.headers` | `https://d1.weather.com.cn/sk_2d/101010100.html` | 246 | `18A3CC31FA3FF79DBC378F56351E1044F7682DE8C57D0EE7C5353EB80F7986EA` |
| `sk-guangzhou.json` | `https://d1.weather.com.cn/sk_2d/101280101.html` | 369 | `D8096FEB852F0E83E60C969A55103E0598DE18FA5CE54B94FFC9E95C8317A605` |
| `sk-guangzhou.headers` | `https://d1.weather.com.cn/sk_2d/101280101.html` | 246 | `EC978A97007B04B230C854B8FE9E42C7F460DF8FCF6647A8F89CD1A3C34F8F11` |
| `business-robots.txt` | `https://d1.weather.com.cn/robots.txt` | 348 | `56429DF9E952BC12EE88A4FF682E852F8FADA281E6FB416A7E6483A5E9AFEC89` |
| `business-robots.headers` | `https://d1.weather.com.cn/robots.txt` | 212 | `75B70A27832980DE7225956C0A54D98301CE03D2B265F4CFD2D4047730AA1495` |

## 审核要求

- 入口可打开: 是
- 样本可复现: 是，实时值会变化，但 URL 和字段结构可复现
- 字段映射完整: 是，覆盖实时天气提示所需字段
- 详情 URL 可直达: 是
