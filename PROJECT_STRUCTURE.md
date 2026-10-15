# 粤乡智匠 - 项目目录结构

本文件描述仓库的职责分区，不枚举具体文件：文件会改名搬家，按职责找才找得准。

## 顶层分区

| 目录 | 放什么 |
| --- | --- |
| `backend/` | 全部后端代码：应用工厂、领域路由蓝图、数据访问层、共享层 |
| `docs/` | ADR（历史决策）、重构方案、运维说明 |
| `e2e/` | Playwright 端到端测试与专用启动器 |
| `tests/` | 领域级单测 |
| `tools/` | 机械检查（架构边界、Python 静态检查） |
| `js/` | 跨页复用的前端模块 |
| `images/` `uploads/` | 静态图片素材、用户上传产物 |
| `data/` | SQLite 库与运行日志（不进版本库，见 `.gitignore`） |
 | `migrations/` | 一次性内容迁移脚本与测试探针（ADR 0002） |

仓库根还放着多页面前端的 HTML 页面、全局样式与脚本，以及 `requirements.txt`
与 `.env`（配置模板是 `.env.example`）。

## 后端分层

后端按领域拆分，一个领域一个蓝图目录，领域之间不互相 import。改后端前先读
`docs/adr/0001-backend-domain-split.md`（边界与裁决）与
`docs/adr/0002-content-into-database.md`（内容落库）。术语见 `GLOSSARY.md`。

- **共享层**：`core`（应用工厂、会话与角色鉴权、限流、统一错误响应）、
  `ai`（上游模型调用的唯一出口）、`shared`（零领域状态的纯函数与纯配置）。
  共享层不感知任何具体领域。
- **领域路由层**：`domains/<领域>/`，一个领域一个目录，承载该领域全部 HTTP 接口。
- **数据访问层**：`db_domains/<领域>.py`，一个领域一个模块。
- **基础设施**：连接工厂、建表定义、口令散列、播种逻辑，各自独立成模块。
- **路径基准**：`repo_paths.py` 的 `REPO_ROOT` 指向仓库根（不是 `backend/`），
  因为 `data/`、`uploads/`、`.env` 都在仓库根。

## 部署

自托管单机：`python backend/run.py` 起一个 Flask 进程，默认多线程，静态文件由
同一个进程伺服。没有反向代理、没有多 worker、没有 serverless。

### 新环境怎么起

库文件不进版本库，新环境用基线库还原：

    python migrations/0001_content_to_db.py --make-baseline
    cp data/baseline.db data/yuexiang.db
    python backend/run.py

详见 `docs/baseline-database.md`。

## 功能模块

### 1. 农业技能培训
- 广东特色农产品选择（荔枝、龙眼、水产等）
- 农时智能日历
- AI农技问答

### 2. 电商运营实训
- 直播带货模拟
- AI话术生成
- 商品文案创作
- 店铺装修指导

### 3. 手工技能传承
- 广绣、潮汕木雕等非遗技艺
- 3D步骤拆解
- 材料采购指南

### 4. 虚拟实训沙盒
- 病虫害AI诊断
- 直播间模拟训练
- AR手工技能指导

### 5. 本土化资源库
- 方言交互支持（粤语、客家话、潮汕话）
- 本地成功案例
- 政策信息推送

### 6. 就业与供应链对接
- 积分激励体系
- 技能证书认证
- 人才供需匹配
- 创业支持服务

### 7. 教师管理
- 学员管理
- 学习数据分析
- 教学报告生成

## 启动方式

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动应用
```bash
python backend/run.py
```

### 3. 访问应用
打开浏览器访问: http://localhost:5000

端口由 `PORT`（环境变量或 `.env`）覆盖，留空或非法时回落 5000。

## 演示账户

- **教师账户**: teacher_demo / 123456
- **学员账户**: student_demo / 123456

## 技术栈

### 前端
- HTML5 + CSS3 + JavaScript
- Font Awesome图标库
- 响应式设计

### 后端
- Python Flask
- RESTful API设计
- JSON数据格式

### AI服务
- SiliconFlow API
- Qwen3-32B模型

## 注意事项

1. 首次运行需要安装Python依赖包
2. AI功能需要网络连接
3. 建议使用现代浏览器访问
4. 移动端体验可能有所差异

## 数据库

SQLite 单文件库放在 `data/` 下，`.gitignore` 忽略 `data/*.db`，库文件不进版本库。
新环境用一份基线库文件还原即可启动；测试与 e2e 用 `YUEXIANG_DB` 指向可弃副本，
不碰真实库。
