# CSS 测试选择器契约

状态：T9 已收口。行为 e2e 不绑定已退役的旧前缀，也不把测试身份写成缩写。

## 优先级

1. `data-testid`
2. ARIA 角色、标签和可见文本
3. 稳定语义类名，例如 `employment-job-card`、`crafts-card`

旧前缀 `emp-`、`craft-`、`cs-`、`copy-`、`msg-`、`bo-`、`qa-`、`fdn-`、
`guide-` 已从活动模板、`id`、`data-testid` 和 e2e 定位器中删除。测试身份使用
完整语义名，例如 `backoffice-shell`、`message-center-panel`、
`copywriting-records`、`customer-service-status`、`crafts-card`。

`tests/test_css_semantic_aliases.py` 机械拒绝这些旧前缀重新进入模板或 e2e，
并检查活动 SFC 中的字面锚点都指向本组件已声明的 `id`。

## 例外

`resume-block` 是领域内仍被多处消费的稳定语义类名。农业任务、技艺步骤、
技艺采购项、方言卡片、方言短语和快捷问题的活动 e2e 已改用 `data-testid`。
公开资源页的方言、案例和政策重复项已改用 `data-testid` 加业务标识属性，
不再把卡片内部布局类名当作测试契约。

## 共享层选择器夹具

`tests/test_frontend_styles.py` 通过检查器 CLI 在临时仓库中注入
`[data-theme="dark"] .startup-overview-card`，要求检查器以
`shared-page-selector` 拒绝，并报告 `components.css`、命中行号、命中选择器和
`frontend/src/views/home/home.css` 归属建议。真实仓库测试同时断言
`components.css` 不再包含任何 `startup` 规则或注释。
