# CSS 测试选择器契约

状态：T12 已完成，T13 已删除旧前缀。行为 e2e 不绑定已退役的旧类名前缀。

## 优先级

1. `data-testid`
2. ARIA 角色、标签和可见文本
3. 稳定语义类名，例如 `employment-job-card`、`crafts-card`

旧前缀 `emp-`、`craft-`、`cs-`、`copy-`、`msg-`、`bo-`、`qa-`、`fdn-`、
`guide-` 等旧前缀已从活动模板删除，测试继续使用语义名或行为选择器。

## 例外

`task-item`、`step`、`resume-block`、`dialect-card`、`phrase-item`、
`voice-quick-btn`、`case-card`、`policy-card` 是当前仍被多个测试使用的稳定语义名。
它们没有缩写前缀，保留到出现更稳定的 `data-testid`。
