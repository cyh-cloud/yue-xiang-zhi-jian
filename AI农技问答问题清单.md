# AI 农技问答 —— 用户视角问题清单

> 审计日期：2026-10-02
> 审计性质：**只读**。未修改任何产品代码（`app.py` / `script.js` / `index.html` / `styles.css` / `sw.js` 均未改动）。
> 审计方法：逐行读代码 + 一次只读上游探测（`AI_API_KEY` 为空时上游真实返回码）。
> 视角设定：**把自己当作第一次使用这个功能的农户**，从打开页面到看到答案，逐步走一遍。

---

## 0. 一句话结论

**这个功能目前对用户是「不可用但看不出来」的状态。** 每问一次，用户都会收到同一句固定兜底话术，
而界面上它被渲染成一条正常的 AI 回答（带动画、复制、重新生成按钮），**用户无法分辨这是失败**。

---

## 1. 阻断级（已实测，当前 100% 触发）

### B1. `AI_API_KEY` 为空 → 上游直接拒绝

> **状态：✅ 已解决（2026-10-05）** —— `.env` 已填入 64 位密钥并实测生效（上游三模型 200，问答 / 流式 / 建议栏 / 图片诊断全部返回真实结果）。
> 本节以下内容保留为**当时的审计记录**（含旧的 `siliconflow.cn` 上游，现已换为阶跃星辰 StepFun）。

- 位置：`.env:8`（`AI_API_KEY=`）→ `app.py:38`
- 实测：向 `https://api.siliconflow.cn/v1/chat/completions` 发 `Authorization: Bearer `（空）请求，
  返回 **HTTP 401 · `{"code":30014,"data":null,"message":"Token is invalid."}`**
- 影响：流式与非流式**两条路径都必然失败**。

### B2. 失败被伪装成成功

`app.py:852-862`（非流式）：

```
except Exception as e:
    try:                      # 降级：再调一次 AI，同样 401
        fallback = call_ai_service(...)
        return jsonify({"success": True, "answer": fallback, ...})
    except Exception:
        return jsonify({"success": True, "answer": "抱歉，AI服务暂时不可用。建议咨询当地农技站或拨打12316三农服务热线获取帮助。", ...})
```

- **HTTP 200 + `success: True`** → 前端 `script.js:1519` `if (data.success)` 判定为正常回答。
- 用户看到的是：打字机效果、`复制` / `重新生成` 按钮、追问建议按钮 —— **全套"成功"的视觉语言**。
- **没有任何"AI 不可用"的错误态。**

### B3. 用户每问一次的实际观感（4 步）

1. 自己的问题出现在气泡里（正常）
2. **一个只有机器人头像、正文完全空白的空气泡**（`script.js:1576` 先建气泡，`:1600` 遇 `event: error` 直接 `return false`，不回滚）
3. 「思考中…」加载指示闪现（`script.js:1508`）
4. 出现上面那句固定兜底话术

---

## 2. 高危

| # | 问题 | 位置 | 用户可见表现 |
|---|---|---|---|
| H1 | 两个问答接口**无鉴权装饰器、无频率限制、无输入长度校验**（全项目仅 `MAX_CONTENT_LENGTH=16MB` 兜底） | `app.py:809`、`:865`、`:32` | 任何人可无限调用；粘贴超长文本直接送入模型 |
| H2 | 流式失败**残留空 bot 气泡**，从不清理 | `script.js:1576` ↔ `:1600` | 对话里凭空多出空白气泡，且随提问累加 |
| H3 | **切换作物不清空对话历史** | `script.js:1303-1310`、`:1337` | 旧作物的问答被当作上下文发给新作物的专家提示词 → **回答串味**；界面同时保留旧作物的整段对话 |
| H4 | `formatAnswer()` **三处 `innerHTML` 注入、完全不转义** | `script.js:1631-1638`，流式在 `:1597` **每个 chunk 都调一次** | 模型输出中的 `<`、`&` 等被当 HTML 解析；极端情况下可注入标记 |

**H3 补充说明（为什么它比看起来更严重）：**
生产者是**唯一**会清空历史的机制，而它写成了 `const observer = new MutationObserver(...)` 后**从未调用 `.observe()`**
→ 该观察器永不触发，`clearChatFlow()` 因此也成了**死代码**（全项目仅在此处被引用）。
产品卡切换走的是另一条独立监听（`script.js:1312-1319`），只刷新标签与建议、**不碰历史**。

---

## 3. 中危

| # | 问题 | 位置 |
|---|---|---|
| M1 | `refreshSuggestions()` 的 `data-question="${q}"` **未转义**（同一文件 `appendSuggestions:1437` 却用了 `escapeHtml`，属遗漏） | `script.js:1369` |
| M2 | 首屏欢迎语与 4 个示例问题**硬编码为「荔枝」**；`updateProductLabel()` **初始化时从未被调用** → localStorage 存了水稻等其他作物时，首屏仍显示"专注于荔枝" | `index.html:238,241-246`；`script.js:1261` |
| M3 | **流式期间点「清空对话」** → 流继续写入已从 DOM 移除的 `contentEl`（答案不可见），但 `history.push` 照常执行 → 界面留下"欢迎语 + 孤立按钮"的残局 | `script.js:1284` ↔ `:1607-1613` |
| M4 | **流式路径不渲染 `data.suggestions`**（仅非流式渲染）→ `_generate_suggestions()` 那次额外 API 调用在流式下完全白费 | `script.js:1612-1616` |
| M5 | HTTP 400（`{"success":false,"message":"请输入问题"}`）也被 `if (!response.ok) return false` 捕获 → 触发「流式 + 非流式」整条双链路 | `script.js:1574` |
| M6 | 历史按**条数**截断（`history[-5:]`）而非长度 → 长回答可撑爆上下文；且与 `max_tokens: 800` 无关联控制 | `app.py:827`、`:884` |
| M7 | **全链路无留痕**：问答不入库、无日志、无引文、无知识库依据。`AGRICULTURE_KNOWLEDGE` 实际只用于取 `product_name` 与回退文案 | 全链路 |

---

## 4. 低危 / 体验

| # | 问题 | 位置 |
|---|---|---|
| L1 | `retry` 用 `messages[messages.length-1]` 假设最后一个 `.qa-message` 是刚生成的 bot 气泡；且 `history.pop()` 清的是最后一条而非对应那条 | `script.js:1475-1488` |
| L2 | 示例按钮点击后 `input.value=''` 再提问 → 输入框**不回显**用户选的问题 | `script.js:1355-1358` |
| L3 | `data['choices'][0]` / `chunk['choices'][0]` **无 schema 校验** | `app.py:846`、`:918`；`app.py:3698` |
| L4 | 后端 `iter_lines()` 无读超时、客户端断开不感知；前端 `reader.read()` 也无超时 | `app.py:904,907`；`script.js:1585` |
| L5 | 发送按钮在 `isTyping` 期间不 `disabled`（仅靠函数入口 `return` 兜住） | `index.html:249` |
| L6 | 移动端 `Enter` 直接发送（靠 `!e.shiftKey` 区分换行）；中文输入法候选未上屏即回车会误发 | `script.js:1274` |
| L7 | 流式完成时 `formatAnswer(fullAnswer)` 被**重复渲染一次**；`fullAnswer` 为空串时仍 `return true` 并把空答案 push 进 history | `script.js:1610`、`:1607-1608` |
| L8 | `event: done` / `data: [DONE]` 无显式处理（靠 `JSON.parse` 抛错被吞），依赖实现巧合 | `script.js:1592-1603` |

---

## 5. 复核后**排除**的误判（避免修错方向）

| 曾经的判断 | 复核结论 |
|---|---|
| 「诊断面板 `.crop-btn` 未与 AI 问答同步」 | **不成立**。`syncPestCropFromProduct()` 已在 `initPestDiagnosis()` 尾部每次打开面板都调用（`script.js:2201`），Q1 已修；**且它属病虫害诊断模块，不属 AI 问答**。 |
| 「SSE 会阻塞 Flask dev server，导致全站卡死」 | **不成立**。Flask `app.run()` 默认 `threaded=True`，SSE 不会阻塞其他请求。 |
| 「`event: error` 会让前端渲染出 `undefined` 字样」 | **不成立**。服务端先 `yield 'event: error'` 再 `yield 'data: {...}'`，前端按行顺序先命中 `event: error` 即返回，不会解析到其后那行 JSON。 |

> 附带一项**全站**（非本模块）安全提示：`app.py:4541` 为 `app.run(host='0.0.0.0', port=5000, debug=True)`，
> 在 `0.0.0.0` 上暴露 Werkzeug 调试器，风险级别高于本清单任一条，建议单独处理。

---

## 6. 建议修复批次（**尚未动手，等指示**）

1. **止血**：填入可用 `AI_API_KEY`；或把"未配置/调用失败"改为显式的可见状态，**停止伪装成功**。
2. **正确性**：清理失败残留的空气泡；切作物清空历史并复用 `clearChatFlow()`；流式补渲染 `suggestions`；400 不再走双链路。
3. **安全**：`formatAnswer` 改为「先转义再套格式」；`refreshSuggestions` 补 `escapeHtml`；两个 ask 接口补输入长度上限（可选加限流）。
4. **体验**：首屏调用 `updateProductLabel()` / `refreshSuggestions()`；发送中禁用按钮；示例按钮回显问题；删除死代码（`observer` 与 `clearChatFlow`）。

---

## 7. 复现路径

| 目标 | 操作 |
|---|---|
| 复现 B1 上游返回码 | 运行 `.workbuddy/_qa_probe.py`，读 `.workbuddy/_qa_probe.txt` |
| 复现 B3 空气泡 | 打开页面 → 农技问答区 → 问任意问题 → 观察问题气泡后是否紧跟一个空白机器人气泡 |
| 复现 H3 上下文串味 | 在「荔枝」下问一题 → 切到「水稻」→ 再问一题 → 观察标签已变但旧对话仍在、回答参照荔枝 |
| 复现 M2 首屏不一致 | 先切到「水稻」（写入 localStorage）→ 刷新页面 → 看欢迎语是否仍写「荔枝」 |

---

# 第二部分 · 修复记录

> 修复日期：2026-10-02
> 用户指令：「**APIkey后续再添加，先把其他问题按照轻重级解决**」
> 因此 **B1（配密钥）不做**，其余问题按严重度分批修复。本轮共修改 5 个产品文件。

## 8. 修复总览

| 问题 | 处理方式 | 状态 |
|---|---|---|
| B2 失败伪装成成功 | 失败改为返回 `503 + success:false + code`，前端渲染错误态 | 已修 |
| B3 失败残留空气泡 | 流式失败先移除本轮输出再回退；空内容也判失败 | 已修 |
| H1 无校验/无限流 | 输入长度上限 500（前后端一致）+ 按 IP 滑动窗口限流 | 已修（**未加鉴权，见 §11**） |
| H2 空气泡不清理 | 同上（B3） | 已修 |
| H3 切作物上下文串味 | 切换作物即重置对话与界面 | 已修 |
| H4 `formatAnswer` 注入 | 改为「先整体转义再套格式」 | 已修 |
| M1 `refreshSuggestions` 未转义 | 改用 DOM API 构建按钮（`dataset` 赋值） | 已修 |
| M2 首屏标签/示例写死 | 初始化即调用 `updateProductLabel()` + `refreshSuggestions()` | 已修 |
| M3 流式期间清空对话 | `AbortController` + 代次号（generation），作废在途响应 | 已修 |
| M4 流式不渲染追问建议 | 新增 SSE `suggestions` 事件，正文收尾后再补发 | 已修 |
| M5 400 触发双链路 | 非 2xx 且带 `message` 时直接呈现，不再重复请求 | 已修 |
| M6 历史按条数截断 | 改为「轮数 5 + 字符数 4000」双上限拼装 | 已修 |
| **M7 无留痕/无引文** | **未做**：属功能新增（需 DB 或知识库），待产品决策 | 待定 |
| L1 retry 定位脆弱 | 引入轮次标识（`data-qa-round`），精确移除该轮 | 已修 |
| L2 示例按钮不回显 | 统一走 `submitAgricultureQuestion`；**保持「点击即发送」语义** | 已修（语义未变） |
| L3 无 schema 校验 | `_chat_completion` 统一校验，全站 AI 调用受益 | 已修 |
| L4 无超时 | 后端 `(10,60)` 读超时；前端 60s/90s + 流式看门狗 | 已修 |
| L5 发送按钮不置灰 | `setQaBusy()` 控制 `disabled` + `aria-busy` | 已修 |
| L6 输入法回车误发 | `e.isComposing \|\| e.keyCode === 229` 直接返回 | 已修 |
| L7 重复渲染/空答案入库 | 回退路径去掉打字机，直接渲染；空内容判失败 | 已修 |
| L8 隐式处理 `[DONE]` | SSE 按空行分块解析，显式区分 `done`/`error`/`suggestions` | 已修 |
| 附：全站 debug 暴露 | `debug` 改为由 `FLASK_DEBUG` 控制，默认关闭 | 已修 |

## 9. 改动文件

| 文件 | 要点 |
|---|---|
| `app.py` | 新增 `_ai_configured` / `_rate_limited` / `_client_key` / `_agri_system_prompt` / `_parse_agri_request` / `_build_agri_messages` / `_chat_completion`；重写两个 ask 端点；`call_ai_service` 改为委托 `_chat_completion`；建议端点加静态兜底与限流；`app.run` 不再硬编码 `debug=True` |
| `script.js` | `QAState` 增 `product/generation/abort`；新增 `submitAgricultureQuestion` / `syncQaProduct` / `resetQaConversation` / `setQaBusy` / `removeQaRound` / `removeQaBotOutput` / `renderQaError` / `qaPostJson` / `finishQaRound` / `parseSseBlock` / `sseMessage`；重写 `askAgricultureQuestion` / `askAgricultureStreaming` / `formatAnswer` / `appendActions` / `appendSuggestions` / `refreshSuggestions` / `clearChatFlow`；删除永不触发的 `MutationObserver` 死代码 |
| `index.html` | 提问框加 `maxlength="500"` 与 `aria-label` |
| `styles.css` | 新增 `.qa-message-error` / `.qa-inline-note` / `#ask-agriculture-btn:disabled` |
| `sw.js` | 缓存版本 v7 → **v8** |

## 10. 验证

**行为回归 40/40 通过**（`.workbuddy/_qa_verify.py` → `_qa_verify.txt`，隔离临时库）
覆盖：输入校验 6 项、诚实失败 3 项、限流 3 项、建议兜底 3 项、上下文拼装 3 项、
通用调用入口 2 项、前端静态检查 18 项、启动安全 2 项。

**可视验证（无头 Chrome + CDP，控制台异常 0、console.error 0）**
`cdp-qa/` 四张截图，逐项实测结果：

| 项 | 实测值 |
|---|---|
| 首屏（T1） | 标签「荔枝」；4 个示例按钮**均带 `title` 与 `type="button"`** → 证明初始化确实调用了 `refreshSuggestions()`（静态 HTML 里这两属性都不存在）；`maxlength=500` |
| 提问失败（T2） | 用户气泡 1、机器人气泡 1、**空气泡 0**、错误态 1 且带「重试」、**复制/重新生成按钮 0**、历史 0、无残留「思考中」 |
| 转义与 SSE（T3） | 输入 `**加粗**<img src=x onerror=alert(1)>` → 输出 `<strong>加粗</strong>&lt;img …&gt;`，**`<img>` 未生成**；`3.5公斤` `10.5公斤` **未被误断行**；`event: error` 块正确解析出 `message="boom"` |
| 忙碌态（T4） | `disabled=true` + `aria-busy="true"`，结束后复位 |
| 切作物（T5） | 标签→「水稻」、对话归零、欢迎语重建、示例换成水稻 4 问 |
| 点击示例（T6） | 用户气泡 1（文本=示例问题）、错误态 1、**空气泡 0**、输入框已清空 |
| 清空对话（T7） | 欢迎语恢复、**`#qa-product-label` 仍存在且为「水稻」**、消息归零 |

> 顺带修掉一个此前未列出的隐性缺陷：原 `clearChatFlow()` 重建欢迎语时**丢掉了 `id="qa-product-label"`**，
> 导致清空一次后产品标签就再也无法更新。现已统一保留该 id。

## 11. 两项有意未做（需产品决策）

1. **不给 ask 接口加鉴权**。该功能位于公开的农业技能页，加登录校验会把匿名访客挡在外面、
   改变产品形态。本轮以「输入长度上限 + 按 IP 限流（默认 5 分钟 60 次，可用环境变量调整）」
   抑制滥用。如需强制登录，请明确指示。
2. **M7 问答留痕 / 引文依据**未做。它需要新增数据表或接入知识库，属功能新增而非缺陷修复。
   当前状况：问答不落库、无日志、无参考文献。若需要，建议单独排期。

## 12. 仍需注意

- 限流是**进程内内存态**，多进程/重启即重置，定位是「抑制滥用」而非安全边界。
- 视觉验证跑在 5059 端口，用的是真实库；本轮 AI 端点不写库，**无数据残留**。
- 修复后 `AI_API_KEY` 仍为空，用户看到的是**明确的「尚未启用」提示 + 重试按钮**（见 `qa_b_error_state.png`），
  不再是一句伪装成回答的兜底话术。填入密钥并重启服务后即恢复真实问答。

---

# 第三部分 · 第二轮排查（用户指令：「再次排查…查看还有什么逻辑矛盾和漏洞」）

> 排查日期：2026-10-02（第二轮）
> 本轮为**只读排查，未改动任何产品代码**。
> 除继续找旧问题外，**重点复查了上一轮我自己的改动**（修复本身会引入新风险），
> 并用 AST / 实测脚本代替目测：`.workbuddy/_qa_ast_audit.py`、`.workbuddy/_qa_probe2.py`。

## 13. 结论

上一轮修掉的是「失败被伪装」这条主干。本轮找到 **16 项**，其中 4 项高危——
**但性质完全不同**：它们不是「失败被伪装」，而是**「同一个平台对不同内容出口采用了互相矛盾的诚实度与合规口径」**。
另外有 5 项是**我上一轮改动引入或未做完**的。

## 14. 高危（4 项）

### N1 ★ 半数作物拿不到对应的 AI 专家身份（功能级，影响面 3/6）

`AGRICULTURE_KNOWLEDGE` 只定义了 **3 个**作物：

```
后端 AGRICULTURE_KNOWLEDGE : ['aquatic', 'longan', 'lychee']      ← 只有 3 个
前端 index.html 产品卡      : 6 个（+ rice, tea, vegetable）
数据库 farming_products     : 6 个（+ rice, tea, vegetable）
前端 getProductName         : 6 个
```

而 `system_prompt` 正是靠它拼专家身份：

```python
product_name = AGRICULTURE_KNOWLEDGE.get(product, {}).get('name', '广东特色农产品')
```

**后果**：用户选「水稻 / 茶叶 / 蔬菜」时，界面欢迎语写着「专注于**水稻**种植指导」，
但发给模型的提示词实际是「专注于**广东特色农产品**领域」——
**一半作物的 AI 专家身份静默退化成通用身份**，用户完全看不出来。

补充事实（决定了修复成本）：`AGRICULTURE_KNOWLEDGE` 全项目只有 4 处用法，
**全部是取 `name`**，它内部的 `seasons` / `diseases` 是死数据。
所以修复**只需要补 3 个名字**，不需要补内容。

位置：`app.py:196`（定义）、`app.py:102 / 1112 / 1172`（3 处取 name）

### N2 ★ 同一平台，「AI 是否可用」的表达互相矛盾

本轮把问答改成**诚实报错**（AI 不可用则不出答案），但**同一平台的病虫害诊断仍是「伪装成 AI」**：

| | AI 不可用时 | 接口返回 | 界面说法 |
|---|---|---|---|
| AI 农技问答 | 报错，不出答案 | `503 + code` | 「AI 尚未启用」+ 重试 |
| **病虫害诊断** | **静默改用关键词匹配知识库** | **`success:True`，形状与 AI 结果完全相同** | **「AI正在分析症状…」→「诊断完成！」** |

`diagnose_pest`（`app.py:2343-2388`）AI 分支与知识库分支**返回同一个结构、同一个 `success:True`，
没有任何来源标记**（全项目 `source` 字段只存在于农时日历）。
前端 `script.js:2495 / 2504` 照常显示「AI正在分析症状…」与「诊断完成！」。

**矛盾点**：一个出口说「AI 没启用」，另一个出口用「AI 诊断完成」的语气给出关键词匹配结果。
**且后者更危险**——农户会把一个关键词命中的结论当成 AI 诊断。

### N3 ★ 合规口径不一致：日历有整套免责机制，问答一个都没有

农时日历子系统有一整套合规设计：`is_verified`、日期「约」前缀、当日弹窗说明、
「查看数据依据」来源清单、《待核清单》交付物。

而 **AI 问答的回答界面上：没有免责声明、没有来源、没有「仅供参考/待核实」**——
在 `script.js` 中检索 `免责 / 仅供参考 / 不构成` **命中 0 处**。

同时提示词明确要求：

> 3) **涉及农药时注明安全用量**

农药用量恰恰是**幻觉代价最高**的内容，而这条要求把「输出用量」写成了硬性指标，
却没有要求给出依据、也没有要求加不确定性表述。

**矛盾点**：同一条农事建议，走日历出口要标「约」+ 列来源 + 声明待复核；
走问答出口则以「专家」口吻直接给出、什么都不标。

### N4 ★ 限流可被一行 header 绕过；密钥填上后本服务就是开放代理

- `CORS(app)`（`app.py:29`）**未限制来源** → 任意网站都可调用本项目接口。
- 限流键 `_client_key()` **优先取客户端可自由伪造的 `X-Forwarded-For`**：

```python
forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
return forwarded or request.remote_addr or 'unknown'
```

→ 攻击者每次请求换一个 `X-Forwarded-For` 值即可**完全绕过限流**；
配合无限流的 CORS，**一旦填入 API_KEY，本服务会变成任意网站的免费 LLM 代理**，
账单算在你的密钥上。这是上一轮我为了「抑制滥用」加的措施，**没有达到目的**。

## 15. 中危（5 项，均为上一轮改动引入或未做完）

| # | 问题 | 说明 | 位置 |
|---|---|---|---|
| N5 | **流式与非流式的元素顺序不一致** | `suggestions` 事件在**读取循环内**就调用 `appendSuggestions`，而 `finishQaRound`（挂「复制/重新生成」）要等流真正关闭才执行 → 流式是「回答 → 追问建议 → 操作按钮」，非流式是「回答 → 操作按钮 → 追问建议」 | `script.js:1815` vs `:1849` |
| N6 | **发送按钮多禁用数秒** | 因为 `event: done` 只被 `continue` 掉、没用来收尾，用户要等「追问建议」那次**额外 AI 调用**结束才解除禁用。上一轮我改了协议顺序，但**前端没利用它**，等于没解决延迟 | `script.js:1748` 附近 + `askAgricultureQuestion` 的 finally |
| N7 | **中途失败会重复一次完整超时** | 流式中途失败且无内容时 `return 'fallback'` → 再走一遍非流式（同一上游故障必然再失败）→ 最坏 **60s + 60s**。这与我自己写的注释「同一原因必然再次失败」自相矛盾 | `script.js:1856` |
| N8 | **用中文文案正则判断错误类型** | `if (/未配置\|未启用\|尚未启用/.test(streamError))` ——服务端明明下发了 `code: ai_not_configured`。**文案改一个字，行为就静默变化**（前端全项目从未读取过 `code` 字段） | `script.js:1852` |
| N9 | **早期返回路径缺代次号校验** | `!response.ok`、`catch → fallback`、`!response.body` 三条路径**都没校验 `generation`** → 「清空对话/切作物」与早期返回竞争时，错误气泡可能落进刚清空的对话；且 `askAgricultureOnce` 在代次号校验**之前**就 `appendTypingIndicator()`，校验失败时**不移除** → 可能残留「思考中…」 | `script.js:1757-1778`、`:1625`+`:1633` |

## 16. 低危 / 一致性（7 项）

| # | 问题 | 位置 |
|---|---|---|
| N10 | 「重新生成」在历史被挤出 10 条窗口后 `findIndex` 返回 -1 → **按钮还在但点了毫无反应，也无提示** | `script.js:1577-1578` |
| N11 | 提问进行中：发送按钮置灰，但**示例按钮与追问建议按钮仍是可点外观**，点了被 `isTyping` 静默吞掉 → 交互暗示不一致 | `script.js:1350`、`appendSuggestions` |
| N12 | `QAState.lastAnswer` 写入 3 处、**全项目 0 处读取**（死状态）；`maxHistory = 10` 但前端只送 `slice(-5)` → 后 5 条永远不参与上下文（**一半是死配置**） | `script.js:1256-1258` |
| N13 | `refreshSuggestions` 取不到建议时**保留旧按钮** → 切作物后若该请求失败，底部仍是**上一个作物**的 4 个问题，与刚切换的标签互相矛盾（这是我上一轮为「失败不清空」引入的降级，代价即此） | `script.js:1395` 附近 |
| N14 | 中途中断保留下来的**半截回答被当作完整回答**写进 `QAState.history`（无任何标记），后续会作为上下文继续使用 | `script.js:1849` |
| N15 | `AGRICULTURE_KNOWLEDGE` 的 `seasons`/`diseases` 是**死数据**（4 处用法全是取 name），占数百行；且 `PEST_KNOWLEDGE` 有 **8** 个作物（含 banana/citrus）与日历的 **6** 个不一致 | `app.py:196+` |
| N16 | 错误信息把内部配置细节（`AI_API_KEY`、`.env` 路径、需重启）**暴露给匿名访客**。上一轮我为了让你一眼看到原因而故意这么写，但它同时是信息泄露；建议拆成「用户看通用提示 / 服务端日志写具体原因」 | `app.py:AI_NOT_CONFIGURED_MSG` |

## 17. 一项已确认**不是**问题（避免误修）

`call_ai_service` 上一轮改成「未配置即抛 `RuntimeError`」——`AST` 审计确认它的
**10 个调用点全部位于 `try/except` 内（无保护 0 个）**，因此该改动不会让其他 AI 功能从
「优雅降级」变成「500 错误页」。证据：`.workbuddy/_qa_ast_audit.txt`。

## 18. 建议修复批次（尚未动手，等你确认）

1. **N1 补 3 个作物名**（改动极小、收益立竿见影）+ **N8 改用 `code` 字段** + **N9 补齐代次号校验** + **N10/N11 补用户反馈**。
2. **N4 限流与 CORS**：限流键改用 `remote_addr`（或仅在显式配置可信代理时才信任 XFF）；
   `CORS(app)` 收敛为允许的来源白名单。**会改变部署行为，需你确认正式域名。**
3. **N5/N6/N7 流式收尾**：真正用 `event: done` 收尾（挂操作按钮并解除禁用），
   建议改为最后再发 `suggestions`，并把「中途失败」的回退改成可选而非无条件。
4. **N2/N3 口径统一**（**需要你定调，属产品决策**）：
   - 诊断功能是否也标注「本次结论来自知识库/来自 AI」？还是与问答统一为「AI 不可用则明确告知」？
   - 问答回答是否加免责与来源说明？若加，走日历同一套措辞（「参考值 · 待复核 · 以当地农技站为准」）还是单独一套？
5. **N12/N13/N14/N15/N16 清理**：删死状态与死数据、建议栏失败时给出明确占位而不是留旧内容、
   中断回答在历史里打标记、错误信息分级。

---

# 第四部分 · 第二轮修复记录

> 依据你的定调：**① 诊断功能采用「标注」方案；② 问答免责声明采用「单独一套」；③ CORS/限流加固暂缓。**
> 除 N4 与 N15 的清理外，第三部分列出的 16 项已全部处理。

## 19. 修复总览（16 项）

| # | 原问题 | 处理方式 | 状态 |
|---|---|---|---|
| N1 ★ | `AGRICULTURE_KNOWLEDGE` 只覆盖 3/6 作物，水稻/茶叶/蔬菜的专家身份静默退化 | 新增 `_agriculture_product_name()`：**farming_products 目录 → 知识库 → 内置兜底表** 三级取值，覆盖全部 6 作物；替换全部 3 处旧写法 | ✅ |
| N2 ★ | 诊断降级用知识库时返回同样的 `success:True`，无来源标记 | 两条产出路径都打上 `source` / `source_label` / `source_note`；前端加来源角标 + 标题切换 + 降级时黄色告警通知 | ✅ |
| N3 ★ | 问答界面零免责零来源 | 问答区新增**常驻**免责声明（独立文案，不复用日历措辞），覆盖农药/兽药用量与重大决策 | ✅ |
| N4 ★ | `CORS(app)` 无限来源 + `X-Forwarded-For` 可伪造绕过限流 | **按你的指示暂缓**（密钥最后一个再加），列入上线前必做清单 | ⏸ |
| N5 | 流式/非流式元素顺序不一致 | 收尾统一为 `finishQaRound(roundId, question, answer, suggestions)`，顺序固定「操作按钮 → 追问建议」 | ✅ |
| N6 | `event: done` 未被利用，发送按钮多禁用数秒 | 收到 `done` 即调用 `finalize()` 收尾并释放忙碌态，之后继续读取只为接住 `suggestions` | ✅ |
| N7 | 中途失败重复一次完整超时（最坏 60s+60s） | 回退到非流式**仅限**「流式端点不存在（404/405）」或「一个 SSE 事件都没收到」；其余一律直接呈现错误态 | ✅ |
| N8 | 用中文文案正则判断错误类型 | 删除该正则；新增 `ssePayload()` 解析 `data`，改用服务端下发的 `code` / 结构判断 | ✅ |
| N9 | 三条早期返回路径缺代次号校验；`askAgricultureOnce` 在校验前插入「思考中…」 | 三条路径均补 `generation` 校验；`appendTypingIndicator` 移到校验之后，且无条件 `removeTypingIndicator()` | ✅ |
| N10 | 「重新生成」在轮次滑出历史后点了无反应 | 取不到历史条目时**从用户气泡的 DOM 取回原问题**；确实取不到才提示 | ✅ |
| N11 | 提问中示例/追问按钮外观可点却被静默吞掉 | `setQaBusy` 同步置灰 `.example-btn` 与 `.qa-action-btn.suggest-btn`；输入框加 `aria-busy`；仍被触发时给出提示 | ✅ |
| N12 | `lastAnswer` 死状态；`maxHistory=10` 但只送 5 条 | 删除 `lastAnswer`；新增常量 `QA_HISTORY_CONTEXT_TURNS = 5`，与后端 `AGRI_HISTORY_MAX_TURNS` 对齐并注释说明「内存 10 条服务于重新生成」 | ✅ |
| N13 | 建议栏失败时保留旧按钮，与刚切换的作物标签矛盾 | 用 `container.dataset.product` 记录按钮所属作物；不属于当前作物时改用**通用问题模板**（「{作物}当前季节该做哪些管理？」等），既不清空也不矛盾 | ✅ |
| N14 | 中断的半截回答被当完整回答写进历史 | `finishQaRound(..., { interrupted: true })` 打标；`qaHistoryPayload()` 把中断轮次的 `answer` 置空，后端 `_build_agri_messages` 会整体跳过该轮 | ✅ |
| N15 | `AGRICULTURE_KNOWLEDGE` 的 `seasons`/`diseases` 是死数据；~~`PEST_KNOWLEDGE` 8 作物 vs 日历 6 作物~~ **（2026-10-05：作物口径已统一为 8，见终检 A3）** | N1 修好后「取名字」不再依赖它，**清理死数据属可选项**，未动（见 §23） | ⏸ |
| N16 | 错误信息向匿名访客暴露 `.env` / `AI_API_KEY` / 「需重启」 | 拆成两份：对外文案改为「尚未启用，请联系平台管理员 + 12316」；`.env` 排查指引移入 `AI_NOT_CONFIGURED_LOG`，**仅写服务端日志** | ✅ |

**顺带修掉的相邻缺陷（排查中发现，非原列表）**

- `renderDiagnosis` 三处 `innerHTML` 未转义（`d.symptoms.map(s => \`<li>${s}</li>\`)`）→ 统一为 `diagnosisList()` 归一化 + `escapeHtml()`；顺带解决了「模型把数组写成一段字符串导致 `.map is not a function` 整块渲染中断」。
- `diagnose_pest` 的 AI 分支只判 `JSONDecodeError`，`{"foo":1}` 这类**结构合法但缺 `disease`** 的响应会被当成有效诊断返回 → 补 `ValueError` 校验与 warning 日志。
- 「开始AI诊断」按钮与「AI正在分析症状…」加载文案在降级路径上名不副实 → 改为「开始诊断」「正在分析症状，请稍候...」。

## 20. 改动文件

| 文件 | 改动 |
|---|---|
| `app.py` | 新增 `_AGRI_PRODUCT_NAME_FALLBACK` / `_agriculture_product_name()` / `DIAG_SOURCE_*` / `_tag_diagnosis_source()` / `AI_NOT_CONFIGURED_LOG`；替换 3 处作物取名；`diagnose_pest` 两条路径加来源标注 + 补校验；两条未配置日志改为只记内部细节 |
| `script.js` | `QAState` 增 `activeRound`、删 `lastAnswer`；新增 `QA_HISTORY_CONTEXT_TURNS` / `qaHistoryPayload()` / `ssePayload()` / `diagnosisList()` / `renderGenericSuggestions()` / `QA_GENERIC_QUESTIONS`；重写 `askAgricultureStreaming`（`sawEvent` / `pendingSuggestions` / `finalized` / `releaseBusy` / `finalize`）；重写 `finishQaRound` / `askAgricultureOnce` / `setQaBusy` / `refreshSuggestions` / `renderDiagnosis` / `runDiagnosis`；`appendActions` 的重新生成改为可从 DOM 取回；`sseMessage` → `ssePayload` |
| `index.html` | 问答区新增 `#qa-disclaimer`；诊断结果区新增 `#diagnosis-title` 与 `#diagnosis-source`；按钮/标签文案去 AI 预设 |
| `styles.css` | 新增 `.diag-source` / `.diag-source[data-source="knowledge_base"]` / `.qa-disclaimer`；`.example-btn:disabled`、`.qa-action-btn.suggest-btn:disabled` |
| `sw.js` | `CACHE_NAME` `yuexiang-v8` → **`yuexiang-v9`** |

## 21. 验证

三套验证全部通过，均针对**隔离临时库**（不动 `data/yuexiang.db`）：

| 验证 | 范围 | 结果 |
|---|---|---|
| 语法 | `app.py` / `database.py` / `farming_data.py` / `script.js` / `sw.js` | **6/6 通过** |
| 行为回归 | 扩展为 A–P 共 **81 项**（含本轮新增 41 项） | **81/81 通过、0 失败** |
| 可视验证（无头 Chrome + CDP） | 10 项断言 + 7 张截图 | **全部通过，控制台异常 0、console.error 0** |

关键实测数据（`_qa2_run.txt`）：

- 未配置密钥提问 → `503 {"code":"ai_not_configured"}`，且文案 **不含 `.env`、不含 `AI_API_KEY`**。
- 诊断（AI 不可用）→ `disease=水稻稻瘟病, source=knowledge_base, label=本地知识库匹配`，UI 标题显示「**知识库匹配结果**」、来源条为琥珀色。
- 合成 AI 来源渲染 → 标题切回「诊断结果」、来源条转为绿色、`data-source="ai"`。
- 转义验证：注入 `<img src=x onerror=alert(1)>` 后 `#symptoms-list img` 数量为 **0**，渲染为纯文本。
- 收尾顺序：DOM 子元素为 `["qa-message bot","qa-msg-actions","qa-msg-suggestions"]` → **按钮在前、建议在后**。
- 忙碌锁定：`setQaBusy(true)` 后发送按钮 + **4/4** 示例按钮同时置灰，释放后回到 0。

产出文件：`.workbuddy/_qa2_verify.txt`、`.workbuddy/_qa2_run.txt`、`.workbuddy/_qa2_serve_info.txt`、`.workbuddy/cdp-qa2/`（7 张截图 + `cdp-report.txt`）。

## 22. 与你决策不一致的地方

**没有偏离。** 三点均按你的定调执行：N2 用「标注」而非「AI 不可用则整体拒绝」；
N3 的免责文案是独立一套，未复用日历的「尚未经农技人员逐条复核」；
N4 完全没动，仅在文档与记忆中登记为上线前必做。

唯一一处**程序化取舍**需要你知晓：N7 把「流式失败后自动改走非流式」收得很紧
（仅 404/405 或零事件时回退）。代价是：若正式环境前置代理会缓冲 SSE、导致前端始终收不到事件，
此时仍会回退；但若代理返回 200 却把流截断，前端会直接显示错误态而不再自动重试一次。
该取舍的目的是**避免用户白等一个完整超时**，重试入口由错误气泡上的「重试」按钮提供。

## 23. 仍未做 / 上线前必做清单

按优先级：

1. **~~N4 CORS 白名单 + 限流键加固~~** ✅ **已完成（2026-10-05 复核）**：
   限流键已改用 `remote_addr`（`_client_key()`，`TRUST_PROXY=0` 时不采信 XFF）；
   `CORS(app)` 已收敛为 localhost/127.0.0.1 + `CORS_ORIGINS` 白名单；四条 AI 路由均有 `_rate_limited`。
2. **~~B1 填入 `AI_API_KEY`~~** ✅ **已完成（2026-10-05 实测生效）**：`.env` 已填 64 位密钥，
   上游三模型 HTTP 200，问答 / 流式 / 建议栏 / 图片诊断全部返回真实结果，**无一处降级**。（**不要再按「AI 分支均走降级」理解本清单的旧结论**）
3. **N15 清理**：`AGRICULTURE_KNOWLEDGE` 的 `seasons`/`diseases`（数百行死数据）、
   ~~`PEST_KNOWLEDGE` 8 作物与日历 6 作物的口径不一致~~（**2026-10-05 已统一为 8，见终检 A3**）—— 属卫生问题，不影响正确性。
4. **~~欢迎语文案~~** ✅ **已可销账**：B1 完成后，首屏「我是AI农技专家，专注于 X 种植指导」由「能力声明」变为**可用性声明**。
5. 业务侧：把《农时日历待核清单.md》交农技人员逐条复核，回填 `is_verified=1`（**现有 123 条全为 0**）。


