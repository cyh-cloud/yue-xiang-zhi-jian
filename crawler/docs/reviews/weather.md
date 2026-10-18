# 中国天气网 审核记录

来源 ID: `weather`

审核时间: `2026-10-19 01:29 Asia/Shanghai`

审核结论: `approved-with-gaps`

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
| HTML DOM 选择器 | 有缺口 | `#hidden_title`、`#fc_24h_internal_update_time`、`#fc_3h_internal_update_time`、`#zs_7d_update_time` 都能定位，但前两个是 `<input type="hidden">`，值在 `value` 属性；后两个同样是隐藏 input，`get_text()` 为空。文档把它们的“样本值”写成可见文本，未说明应读取 `value`，实现者按文本选择器会得到空值 |
| 字段映射 | 有缺口 | `city`、`cityname`、`nameen`、`temp`、`weather`、`weathercode`、`WD`、`WS`、`wse`、`SD`、`qy`、`njd`、`rain`、`rain24h`、`aqi`、`aqi_pm25`、`limitnumber`、`time`、`date` 的映射成立；`observed_at` 需要把 `date`、`time` 与抓取日期组合，跨午夜风险文档已提示。但 `std_weather_candidate` 在冻结 schema 中没有定义，文档也没有说明它是否只是运行时 DTO、是否落 raw/stage |
| 访问限制 | 通过（有 robots 缺口） | `www.weather.com.cn/robots.txt` 返回 200，内容为 `User-agent: * / Allow: /`；`d1.weather.com.cn/robots.txt` 返回 403 正文，不能据此推断接口允许或禁止。首页和天气页无登录要求，实时接口需页面 Referer |
| 版权与用途 | 通过 | 首页和天气页页脚均写“中国天气网版权所有，未经书面授权禁止使用”，并标识中国气象局公共气象服务中心及 `京ICP证010385-2号`。文档明确未发现 API 复用许可、上线前需确认授权，边界正确 |
| “只登记 API 候选、不建历史表” | 通过 | 来源文档、`crawler/docs/mapping/weather.md` 和冻结 schema 都没有天气历史表；文档明确 std 只保留最近候选，业务库不保存天气快照。该结论与本轮 API/页面事实一致 |
| 下载记录 | 通过 | 目录 `crawler/download/www.weather.com.cn/` 共 14 个文件，最大 382564 bytes，均低于 100MB，无需 `OVERSIZE.md`；文档列出的 `home.html`、`robots.txt`、`city-list.js`、`weather1d-101010100.html`、两个 `sk-*.json` 及 headers 的大小和 SHA-256 均可复算。实时响应会变化，不能要求下载哈希永久等于新请求 |

## 发现的问题

- HTML DOM 章节把隐藏 input 的 `value` 写成“样本值”，没有写明读取属性。`#hidden_title` 的 `value` 是 `10月18日20时 周日  晴  5/19°C`，`#fc_24h_internal_update_time` 的 `value` 是 `2026-10-18 18:00`，`#fc_3h_internal_update_time` 的 `value` 是 `2026-10-18 18:00`，`#zs_7d_update_time` 的 `value` 是 `2026-10-18 20:00:00.0`；按 `get_text()` 读取后两个会得到空字符串。
- `std_weather_candidate` 在 `crawler/docs/schema/crawler-db.md` 中不存在。文档把它描述为“临时标准实体”，同时又说可以写入 raw 响应索引；raw、stage、std 的落点没有可执行的表名或结构，后续实现无法按冻结 schema 建表。
- 接口必须带正确 Referer 才能返回 200；文档写了“建议带”，但未把错误 Referer/无 Referer 的 403 结果写成硬性前置条件。把 Referer 当作可选会让实现直接拿到 403 错误页。
- 文档的字段表示例把 `temp` 写成 `6.1`、`WD` 写成 `西风`，是较早抓取值；本轮返回 `5.9`、`北风`，属于实时变化，不构成事实错误，但审核记录和样本应明确“值仅作字段格式示例”。
- 文档的 `date` 字段是中文日期，未给出跨年、跨午夜和星期解析的确定性规则；`time` 只有时分，不能单独形成观测时间。
- `limitnumber` 在部分城市为空字符串，文档用北京“不限行”作为字段存在性证据，但没有说明空值是合法值，不能把它当成缺失错误。
- `d1.weather.com.cn/robots.txt` 返回 403。文档已经写了这一点，但没有说明该 403 是 HTML 错误页而非 robots 规则；调度器不能把响应体当作 robots 文本解析。
- 下载记录中的 headers 哈希依赖响应头（Date、缓存、Set-Cookie 会变化），可复算本次文件，但不能作为跨次请求的稳定契约；文档应明确只有页面/接口正文哈希用于内容版本核对，headers 哈希只作本次样本证据。
- 来源文档没有明确 `std_weather_candidate` 是“运行时 DTO”还是“采集库表”。`crawler/docs/mapping/weather.md` 使用了同样的临时实体名，若 schema 不冻结，两个文档会各自演化。

## 必须补齐

- 把 HTML DOM 的四个隐藏 input 写成“读取 `value` 属性”，并在样本值前标注“本次样本，实时变化”；不要用 `get_text()` 作为解析方式。
- 在来源文档中把 Referer 从“建议”改为必需请求头，记录无 Referer/错误 Referer 返回 403，正确 Referer 返回 200。
- 明确 `std_weather_candidate` 的身份：要么在冻结 schema 中定义该临时实体及其 TTL/清理策略，要么改为只写运行时 DTO 和 raw 索引，不声称存在 std 表。
- 给 `observed_at` 写出确定性组合规则：优先使用 `date` 和 `time`，以 `fetched_at` 的日期消歧，跨午夜或跨日时标记陈旧/待复核。
- 说明 `limitnumber` 可以为空字符串，空值不等同于字段缺失；同时说明 `time` 不是分钟级完整时间。
- 明确 `d1.weather.com.cn` 的 403 是 HTML 错误页，不能解析成 robots 允许规则；若后续要正式上线，需另行确认接口授权和配额。

## 可后续处理

- 7 天预报页面已返回 200，字段结构可后续扩展；本轮不把它纳入实时 API 契约。
- 预警、空气质量分项、分钟级观测和农业气象专用指标未验证，继续作为后续候选。
- API 正式授权、并发配额、长期稳定性和跨网络可用性仍需运营方确认。
- 实时接口的值会变化，下载哈希只能证明本次样本；后续实现应保存 `fetched_at` 和内容哈希，而不是要求跨请求固定哈希。
