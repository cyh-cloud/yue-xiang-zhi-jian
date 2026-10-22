# 中国天气网 审核记录

来源 ID: `weather`

审核时间: `2026-10-19 01:29 Asia/Shanghai`

审核结论: `approved-with-gaps`

权利状态: `attribution-required`

## 审核范围

- 待审文档: `crawler/docs/sources/weather.md`
- 审核者: 来源审核 agent
- 复核方式: 独立使用 `curl` 与 Python `urllib`/`BeautifulSoup` 重开首页、城市编码、北京/广州当前天气页、北京 7 天页、两个实时接口和 robots；逐项解析 `dataSK`、页面隐藏 input 和 DOM 选择器，并复算下载目录哈希

本轮实际验证 8 个 URL 返回 200；`d1.weather.com.cn/robots.txt` 返回 403，属于边界探测失败，不当作接口授权。两个实时接口均要求正确页面 Referer：无 Referer 或错误 Referer 返回 403，正确 Referer 返回 200。

## 逐项结论

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 入口 URL | 通过 | `https://www.weather.com.cn/` 返回 200；页面标题“天气网”，未发现密码输入或登录表单。城市编码资源 `https://j.i8tq.com/weather2020/search/city.js` 返回 200、382564 bytes、`application/javascript` |
| 城市编码 | 通过 | 城市资源是 `var city_data = {...}` 的嵌套 JavaScript 对象，按省、市、区县组织；`"AREAID"` 共 3221 个。北京 `101010100`、广州 `101280101` 各出现一次，中文名和英文标识与接口返回一致 |
| 当前天气页面 | 通过 | `https://www.weather.com.cn/weather1d/101010100.shtml` 与广州对应页面均返回 200；`#today li:nth-child(1) p.wea`、`#today li:nth-child(2) p.wea`、夜间/白天温度、`p.win span[title]` 和 `var hour3data` 均有非空结果 |
| 7 天页面 | 通过（非主契约） | `https://www.weather.com.cn/weather/101010100.shtml` 返回 200，`[id="7d"]` 和 `.t.clearfix` 可定位 7 条日期卡片；文档已明确不把 7 天页纳入实时 API 契约，边界合理 |
| 实时接口与请求参数 | 通过 | 接口为 `GET https://d1.weather.com.cn/sk_2d/{AREAID}.html`，无查询字符串；`AREAID` 在路径中。实测必须带 `Referer: https://www.weather.com.cn/weather1d/{AREAID}.shtml`，普通浏览器 User-Agent 可用；返回 Content-Type 为 `text/html`，正文是 `var dataSK={...};` |
| 返回字段 | 通过 | 北京与广州响应均为 23 个字段：`nameen`、`cityname`、`city`、`temp`、`tempf`、`WD`、`wde`、`WS`、`wse`、`SD`、`sd`、`qy`、`njd`、`time`、`rain`、`rain24h`、`aqi`、`aqi_pm25`、`weather`、`weathere`、`weathercode`、`limitnumber`、`date`。对象可在去掉 `var dataSK=` 前缀和末尾分号后用 JSON 解析 |
| 样本 1 | 通过 | 北京接口返回 200，`cityname=北京`、`city=101010100`、`temp=5.9`、`weather=晴`、`WD=北风`、`WS=0级`、`SD=88%`、`rain=0`、`rain24h=0`、`aqi=23`、`time=01:05`、`date=10月19日(星期一)`；实时值随时间变化，但 URL 和字段结构可复现 |
| 样本 2 | 通过 | 广州接口返回 200，`cityname=广州`、`city=101280101`、`temp=23.4`、`weather=晴`、`WD=北风`、`WS=1级`、`SD=94%`、`rain=0`、`rain24h=0`、`aqi=26`、`time=01:00`、`date=10月19日(星期一)`；城市编码和字段结构稳定 |
| HTML DOM 选择器 | 通过 | 四个隐藏 input 已明确读取 `value` 属性，文档标明样本值随实时数据变化 |
| 字段映射 | 通过 | 字段映射成立；`weather_dto` 明确为运行时 DTO，只保存 raw 响应索引，不建立 std 或历史天气表 |
| 访问限制 | 通过（有 robots 缺口） | `www.weather.com.cn/robots.txt` 返回 200，内容为 `User-agent: * / Allow: /`；`d1.weather.com.cn/robots.txt` 返回 403 正文，不能据此推断接口允许或禁止。首页和天气页无登录要求，实时接口需页面 Referer |
| 版权与用途 | 通过 | 首页和天气页页脚均写“中国天气网版权所有，未经书面授权禁止使用”，并标识中国气象局公共气象服务中心及 `京ICP证010385-2号`。文档明确未发现 API 复用许可、上线前需确认授权，边界正确 |
| “只登记 API 候选、不建历史表” | 通过 | 来源文档、`crawler/docs/mapping/weather.md` 和冻结 schema 都没有天气历史表；文档明确 std 只保留最近候选，业务库不保存天气快照。该结论与本轮 API/页面事实一致 |
| 下载记录 | 通过 | 目录 `crawler/download/www.weather.com.cn/` 共 14 个文件，最大 382564 bytes，均低于 100MB，无需 `OVERSIZE.md`；文档列出的 `home.html`、`robots.txt`、`city-list.js`、`weather1d-101010100.html`、两个 `sk-*.json` 及 headers 的大小和 SHA-256 均可复算。实时响应会变化，不能要求下载哈希永久等于新请求 |

## 发现的问题

- 历史发现（已处理）：隐藏 input 已明确读取 `value` 属性，不再用 `get_text()`；样本值已标注为实时变化。
- `weather_dto` 已改为运行时 DTO，不再声称存在 std 表。
- 接口已把正确 Referer 写成硬性请求前置条件。
- 文档的字段表示例把 `temp` 写成 `6.1`、`WD` 写成 `西风`，是较早抓取值；本轮返回 `5.9`、`北风`，属于实时变化，不构成事实错误，但审核记录和样本应明确“值仅作字段格式示例”。
- 文档的 `date` 字段是中文日期，未给出跨年、跨午夜和星期解析的确定性规则；`time` 只有时分，不能单独形成观测时间。
- `limitnumber` 在部分城市为空字符串，文档用北京“不限行”作为字段存在性证据，但没有说明空值是合法值，不能把它当成缺失错误。
- `d1.weather.com.cn/robots.txt` 返回 403。文档已经写了这一点，但没有说明该 403 是 HTML 错误页而非 robots 规则；调度器不能把响应体当作 robots 文本解析。
- 下载记录中的 headers 哈希依赖响应头（Date、缓存、Set-Cookie 会变化），可复算本次文件，但不能作为跨次请求的稳定契约；文档应明确只有页面/接口正文哈希用于内容版本核对，headers 哈希只作本次样本证据。
- 来源文档和 mapping 已统一说明 `weather_dto` 是运行时 DTO。

## 必须补齐

- 已完成：HTML DOM 的四个隐藏 input 明确读取 `value` 属性，样本值标注为实时变化。
- 已完成：来源文档把 Referer 写为必需请求头，并记录无 Referer/错误 Referer 返回 403、正确 Referer 返回 200。
- 已明确 `weather_dto` 只写运行时 DTO 和 raw 索引，不声称存在 std 表。
- 已完成：`observed_at` 使用 `date`、`time` 和 `fetched_at` 组合，处理跨年和跨午夜。
- 已完成：说明 `limitnumber` 可为空字符串，`time` 只有时分。
- 已完成：明确 `d1.weather.com.cn` 的 403 是 HTML 错误页，不能解析成 robots 允许规则。

## 可后续处理

- 7 天预报页面已返回 200，字段结构可后续扩展；本轮不把它纳入实时 API 契约。
- 预警、空气质量分项、分钟级观测和农业气象专用指标未验证，继续作为后续候选。
- API 正式授权、并发配额、长期稳定性和跨网络可用性仍需运营方确认。
- 实时接口的值会变化，下载哈希只能证明本次样本；后续实现应保存 `fetched_at` 和内容哈希，而不是要求跨请求固定哈希。
- 2026-10-20 契约修复: 删除重复的 `weather-com-cn` 来源 ID，中国天气网统一使用 `weather`；Open-Meteo 和 QWeather 使用各自独立的文档与审核记录。

## 2026-10-20 运行时缓存

- 已新增 `WeatherRuntimeCache`，默认 TTL 为 15 分钟，线程安全，可在测试中注入时钟。
- 缓存只保存运行时 DTO，不创建历史天气表；真实接口授权、配额和长期稳定性仍为 `deferred`。
