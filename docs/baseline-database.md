# 基线库

## 它是什么

`data/baseline.db` 是一份**灌完内容的 SQLite 库**：58 张表、5 个视图、14 张内容表
全部有行，外加演示账号、政策、轮播等种子数据。新环境拿到它就能直接启动，不需要
再跑代码里的播种逻辑。

它由 `migrations/0001_content_to_db.py` 生成，不是手产物。

## 为什么需要它

T17 把 `data/*.db` 加进 `.gitignore` 并从 git 移除跟踪后，仓库里没有任何机制产出
一份可用的库。而现有测试与 e2e 都依赖种子数据：没有它，`data/yuexiang.db` 不存在时
330 个用例直接报错（登录打不了、岗位列表空的、案例审核记录缺失）。基线库补上这一环：
库文件不进版本库（二进制不该污染 git 历史），但生成它的命令进。

## 怎么生成

在仓库根跑：

    python migrations/0001_content_to_db.py --make-baseline

默认输出到 `data/baseline.db`。想换位置加 `--baseline-path <路径>`。

脚本做三件事：

1. 对目标库（默认 `data/yuexiang.db`，可用 `--db` 覆盖）执行内容迁移，灌入 14 张内容表；
2. 把灌完的库复制成基线库；
3. 清掉基线库里的 `schema_migrations` 记录，并把 journal_mode 从 WAL 切回 DELETE。

第三步是刻意的：基线库代表「迁移前的形状」，留着迁移记录会让后续任何迁移脚本
在它身上直接跳过。清掉之后，往基线库上跑新迁移与在现库上跑完全一样。

## 新环境怎么用

    cp data/baseline.db data/yuexiang.db
    python backend/run.py

e2e 用同一份库：`e2e/serve.py` 把 `YUEXIANG_DB` 指向临时路径，启动时从基线库复制
过去（见 T03 对 `e2e/serve.py` 的改写，本节只约定契约）。

## 与现库的关系

现库 `data/yuexiang.db` 是用户数据，不要直接写它。迁移脚本对现库做两件写操作：

- 灌内容（对已有行按自然键就地更新，不动自增 id）；
- 清两处脏数据（`points` 的 NULL 主键行、`messages` 的孤儿收件人行）。

清理动作逐行记进 `schema_migrations.extra`，不静默丢弃。想在副本上先看效果：

    cp data/yuexiang.db /tmp/probe.db
    YUEXIANG_DB=/tmp/probe.db python migrations/0001_content_to_db.py
    YUEXIANG_DB=/tmp/probe.db python migrations/0001_content_to_db.py   # 第二次应提示已执行

## 为什么基线库不入版本库

`.gitignore` 已忽略 `data/*.db`。二进制文件进 git 会让每次内容变更都产生一份全量
diff，且历史里的旧版本永远删不干净。生成命令进版本库，产物不进：`--make-baseline`
是幂等的，任何人任何时候都能重建出一份一样的。

## 什么情况下要重新生成

- 改了 `migrations/0001_content_to_db.py` 的灌库逻辑（补字段、改映射）；
- 改了 `backend/domain_data/` 或 `domains/` 里的内容常量，想让基线库跟上；
- `data/baseline.db` 丢失或损坏。

注意：T10 删掉 `domain_data/` 之后，本脚本的 `_load_sources()` 会导入失败，届时它
只剩「防重入」的作用，重新生成基线库要改用别的方式（见 ADR 0002 的执行顺序一节，
第 7 步是切换点）。
