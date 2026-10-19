# Git 历史卫生

状态: active

日期: 2026-10-20

## 发布制品

公开仓库使用一个从已审核工作树生成的单分支发布制品。发布分支只包含代码、文档、标准化数据和合成 fixture，不继承整合工作树中的旧 raw 证据、会话头或个人数据提交。

`history-hygiene-baseline.json` 是发布制品的空基线。它只保留说明字段，`findings` 必须为空。任何可达历史命中都必须修复，不能用基线豁免。

当前整合 worktree 可能仍能访问旧整合历史中的对象，这是清理前工作树的属性，不是公开分支的发布证据。最终判定以公开分支的 clean-clone 扫描为准，由独立 public-branch 步骤执行，不在本分支改写历史。

## 扫描范围

`check_history_hygiene.py` 扫描可达 Git 对象中的:

- `crawler/download/`、`.headers` 和私有 session、cookie、credential、secret 路径。
- 文本证据中的 `Set-Cookie`、`Authorization`、Bearer token、签名参数、API key 和私钥块。
- HTML 中的隐藏表单状态、原始 form/script/iframe 结构，以及 `__VIEWSTATE`、`__EVENTVALIDATION`、CSRF 类 token。
- XLSX 的联系人列、非合成作者或最后修改者、嵌入对象和完整源表尺寸。
- PDF 的作者、创建者、嵌入附件、页数上限、中文原始正文和个人数据。
- HTML、JSON、TXT、XLSX、PDF 中的手机号、邮箱、身份证号和联系方式标签。
- 公开 evidence fixture 的合成标记、体积上限和格式合法性。

检查器不依赖单一字段名 denylist。公开的 XLSX、PDF、HTML fixture 必须带合成标记，并通过结构、元数据和内容三层检查。

## 命令

在公开分支的 clean clone 根目录运行:

```powershell
python crawler/tools/check_history_hygiene.py
```

预期输出:

```text
history hygiene passed: 0 documented finding(s), no new leaks
```

`check_contracts.py` 默认检查空基线形状，不在整合 worktree 扫描旧历史。需要同时扫描可达历史时运行:

```powershell
python crawler/tools/check_contracts.py --scan-history
```

## 清理边界

- 本分支不重写历史、不创建公开分支、不 force-push。
- 公开分支必须从干净工作树生成，并保持空基线。
- 清理后重新运行 `check_history_hygiene.py`，命中数必须为 0。
- fixture 生成命令: `python -m crawler.tools.generate_public_fixtures`。
