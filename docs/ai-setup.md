# AI 服务配置指南

后端 AI 功能（农技问答、病虫害诊断、带货话术、商品文案、客服对练、方言语音等）依赖一个 OpenAI 兼容的聊天补全端点。应用启动时自动读取项目根目录的 `.env`（见 `app.py` 的 `load_dotenv()`），**改完必须重启服务**才生效。

## 最快路径（SiliconFlow，代码默认值就是它）

1. 复制样例：`.env.example` → `.env`
2. 只需填密钥：

   ```env
   AI_API_KEY=sk-你的真实密钥
   ```

   其余用默认即可：
   - `AI_API_URL` = `https://api.siliconflow.cn/v1/chat/completions`
   - `AI_MODEL` = `Qwen/Qwen3-32B`（文本，也是诊断/对话兜底）
   - `AI_VL_MODEL` = `Qwen/Qwen3-VL-32B-Instruct`（图片诊断）

3. 重启服务（`python run.py`）。

## 换其它 OpenAI 兼容服务商

按 `.env.example` 里的 StepFun 示例，改这三个即可：

```env
AI_API_URL=https://你的服务商/v1/chat/completions
AI_API_KEY=你的密钥
AI_MODEL=文本模型名
AI_VL_MODEL=支持图片的模型名   # 留空 = 关闭图片诊断（不会静默降级）
```

可选：`AI_CHAT_MODEL`（留空跟随 `AI_MODEL`）、`AI_REASONING_EFFORT`、`AI_REASONING_TOKEN_RESERVE`。

## 怎么算“配好了”

`app.py` 的 `_ai_configured()` 只认一件事：`AI_API_KEY` 非空。未配置时 AI 接口明确返回 503 + 错误码（不返回假结果）；配置并重启后应返回 200。

自测：重启后 `GET /api/agriculture/suggestions` 或 `POST /api/agriculture/ask`，或看启动日志有无 “AI_API_KEY 未配置” 的告警。

## 注意

- `.env` 已在 `.gitignore` 忽略，密钥不会进仓库；`.env.example` 是唯一允许提交的样例。
- 密钥按调用计费，真实冒烟省着打。
