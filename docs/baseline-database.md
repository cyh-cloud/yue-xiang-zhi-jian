# 基线库

## 它是什么

`data/baseline.db` 是一份**灌完内容的 SQLite 库**：56 张表、5 个视图、14 张内容表
全部有行，外加演示账号。新环境拿到它就能直接启动，不需要再跑代码里的播种逻辑。

它由 `migrations/0001_content_to_db.py --make-baseline` 从现库复制而来，不是手产物。
脚本只清两处历史脏数据，不灌内容（T10 起内容不在代码里）。

## 为什么需要它

T17 把 `data/*.db` 加进 `.gitignore` 并从 git 移除跟踪后，仓库里没有任何机制产出
一份可用的基线库。现有测试与 e2e 都依赖种子数据：没有基线库时，依赖内容的用例会
直接报错。当前 `data/yuexiang.db` 作为受控业务快照随 `frontend/vue-rebuild` 分发，
用于新环境交付；`data/baseline.db` 仍是生成物，不进入版本库。

## 怎么生成

在仓库根跑：

    python migrations/0001_content_to_db.py --make-baseline

默认输出到 `data/baseline.db`。想换位置加 `--baseline-path <路径>`。

脚本做三件事：

1. 对目标库（默认 `data/yuexiang.db`，可用 `--db` 覆盖）跑一遍迁移：清两处历史脏数据
   （`points` 的 NULL 主键行、`messages` 的孤儿收件人行）；
2. 把处理完的库复制成基线库；
3. 清掉基线库里的 `schema_migrations` 记录，并把 journal_mode 从 WAL 切回 DELETE。

第三步是刻意的：基线库代表「迁移前的形状」，留着迁移记录会让后续任何迁移脚本
在它身上直接跳过。清掉之后，往基线库上跑新迁移与在现库上跑完全一样。

⚠️ 内容已经不在脚本里了（T10 把 `domain_data/` 与 `domains/` 的内容常量整体删除）。
所以本命令**不会**往内容表里灌任何东西，它只是「复制现库 + 清迁移记录」。想让基线库
跟上新的内容，直接改现库（或经运营后台改），再跑一次本命令；脚本本身没有内容副本。

## 新环境怎么用

    Copy-Item data\baseline.db $env:TEMP\yuexiang.db
    $env:YUEXIANG_DB = "$env:TEMP\yuexiang.db"
    python backend/run.py

e2e 用同一份库：`e2e/serve.py` 把 `YUEXIANG_DB` 指向临时路径，启动时从基线库复制
过去，再跑 `init_db()` 补演示账号。T10 之后 `init_db()` 不再写任何内容行
（ADR 0002），所以「从基线库复制」是 e2e 拿到内容的唯一途径。若没有
`data/baseline.db`，可以把 `YUEXIANG_BASELINE_DB` 指向受控快照 `data/yuexiang.db`，
启动器仍会复制到临时库，不会写快照。

## 与现库的关系

现库 `data/yuexiang.db` 是受控业务快照，不是运行中的可变用户库，不要直接写它。
迁移脚本对现库副本做两件写操作：

- 灌内容（对已有行按自然键就地更新，不动自增 id）；
- 清两处脏数据（`points` 的 NULL 主键行、`messages` 的孤儿收件人行）。

清理动作逐行记进 `schema_migrations.extra`，不静默丢弃。想在副本上先看效果：

    cp data/yuexiang.db /tmp/probe.db
    YUEXIANG_DB=/tmp/probe.db python migrations/0001_content_to_db.py
    YUEXIANG_DB=/tmp/probe.db python migrations/0001_content_to_db.py   # 第二次应提示已执行

## 为什么基线库不入版本库

`.gitignore` 忽略 `data/*.db`。`data/baseline.db` 是生成物，二进制文件进 git 会让
每次内容变更都产生一份全量 diff，且历史里的旧版本永远删不干净。生成命令进版本库，
基线产物不进：`--make-baseline` 是幂等的，任何人任何时候都能重建出一份一样的。
`data/yuexiang.db` 是用户明确要求的受控业务快照，是这条规则的单文件例外，不应在
日常开发中覆盖它。

## 什么情况下要重新生成

- 内容变了（运营在后台改过、或往现库补了新条目），想让基线库跟上；
- `data/baseline.db` 丢失或损坏。

重新生成前先确认现库就是想要的样子：脚本只做「清脏数据 + 复制 + 清迁移记录」，
不会把内容改回任何历史版本。
