# 中国农业人才网 审核记录

来源 ID: `nzrc`

审核时间: `2026-10-19 01:28 Asia/Shanghai`

审核结论: `approved-with-gaps`

## 审核范围

- 待审文档: `crawler/docs/sources/nzrc.md`
- 审核者: 来源审核 agent
- 复核方式: 实际 HTTP GET 首页、`career_seek.html` 列表、两个岗位详情、联系方式 Ajax 和 `robots.txt`；用页面 DOM 与下载快照逐项核对字段、分页、样本位置和 SHA-256。另验证 `career_seek.html` 第 2、3 页 PostBack 可返回不同岗位。

## 逐项结论

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 入口 URL | 通过 | 首页 `http://www.nzrc.com.cn/` 返回 200；列表 `http://www.nzrc.com.cn/career_seek.html` 返回 200；详情模式 `company/jobs/{id}.html` 可用 |
| 列表页与分页 | 基本通过，存在实现约束 | 第 1 页 20 个岗位；分页控件显示 903 页，页码链接为 `__doPostBack('ctl00$ContentPlaceHolder1$AspNetPager1', '{page}')`。实测带会话和 `__VIEWSTATE` 提交第 2、3 页，分别得到不同岗位，页面标记为第 2、3 页 |
| 详情页 URL | 通过 | 两个样本详情均返回 200：`http://www.nzrc.com.cn/company/jobs/8235500.html`、`http://www.nzrc.com.cn/company/jobs/8240109.html` |
| JSON 字段或 DOM 选择器 | 基本通过，选择器名称需修正说明 | 列表字段可从 `div.career_name a.green`、`div.corp_name a.green`、`div.suozaidi`、`div.shijian` 取得；详情可从 `#project_L h1 a`、`#project_L h2`、`#project_L li`、`#brief_info` 取得。原文把联系方式接口写成 `post` 与 `postNumber` 混用，实际 Ajax 键为 `post`，详情 DOM 为 `#postNumber` |
| 样本记录 | 部分通过 | 两个详情和字段内容可复现；但文档称样本位于 `career_seek.html` 第 1 页第 1 条和列表第 1 页，实测第 1 页 20 条中不含 `8235500` 与 `8240109`。快照中的样本只出现在首页推荐区，不在职位查询列表第 1 页 |
| 字段映射 | 基本通过，有具体缺口 | 公司、地区、薪资、学历、招聘人数、发布日期、有效期和正文均可定位；当前来源没有独立 `工作经验` 标签，经验要求只在正文中出现，映射文档需明确这一缺口。`#brief_info p` 只有 1 个 `p`，但内容完整；`#brief_info` 还含一个标题 `div`，按 `p` 取正文可行 |
| 访问限制 | 通过，但联系方式描述不准确 | 详情页联系方式在未登录时显示星号，并出现“个人登录”；Ajax 返回 `islogin=0`，但公开返回企业 `address` 和 `site`，不返回联系人、电话、传真、邮编和邮箱。文档“未登录返回空联系方式”应理解为敏感联系方式为空，而不是整个响应为空 |
| 版权与用途 | 基本通过，有错误事实 | 站点页脚有 `All Rights Reserved`，但首页、列表和两个详情页均未找到“未经授权不得转载”原文；该表述来自站外或误读。实际仍应按未发现开放数据许可处理，保留来源链接并限制全文转载 |
| 下载记录 | 通过 | `home.html`、`career-seek.html`、两个详情、Ajax 和 `robots.txt` 的大小与 SHA-256 均与文档一致；`robots.txt` 为 IIS 404 页面，未提供 robots 规则 |

## 发现的问题

- 样本位置错误：文档明确写两个样本在职位查询第 1 页，实测 `career_seek.html` 第 1 页 20 个岗位 ID 不含 `8235500`、`8240109`；两样本在首页的岗位推荐链接中出现。
- 联系方式接口结论过宽：真实响应为 `{"islogin":"0","address":"江苏省南京市栖霞区恒竞路31-1号","site":"www.jsnys.com/","officeuser":"","tel":"","fax":"","post":"","email":""}`。企业地址和网址可以公开取得，联系人、电话、传真、邮编和邮箱为空。
- 版权证据不准确：`nzrc` 页面能确认 `Copyright` / `All Rights Reserved`，未确认“招聘信息及作品未经授权不得转载”的原句。
- 搜索入口不可复现：首页表单的岗位搜索目标实际为 `/user/personjobsearch_list.html?whichfile=6.2`，直接 GET 返回“文件不存在”；`.aspx` 版本也同样返回“文件不存在”。文档虽已标为缺口，但 URL 写法应以后续实现文档修正为准，不能当作稳定 GET 入口。
- 首页不是列表页：首页有大量 `company/jobs/*.html` 推荐链接，但没有 `div.detail_headline` 结构；实现时必须区分首页推荐链接与 `career_seek.html` 列表行。
- 分页实测依赖会话与视图状态：分页控件使用 `__doPostBack`，第 2、3 页需提交当前页面会话中的 `__VIEWSTATE`、`__VIEWSTATEGENERATOR`、`__EVENTTARGET` 和 `__EVENTARGUMENT`。

## 必须补齐

- 修正两个样本的“列表位置”，将首页推荐位置与职位查询列表第 1 页区分开。
- 修正联系方式 Ajax 字段说明：公开返回 `address`、`site`，敏感字段为空；不要把整个响应记为空。
- 修正版权依据，删除未能在本来源页面复现的转载禁令原句，或标注为站外资料。
- 在实现文档中记录分页必须带会话和 PostBack 隐藏字段，并明确第 1 页是默认页，第 2 页起按 `__EVENTARGUMENT` 提交。

## 可后续处理

- 补充详情正文中经验要求的独立判定规则；当前来源没有独立的 `工作经验` 标签，只能在正文或职位描述里识别。
- 验证第 903 页及中间页的岗位唯一性，本次只实测第 2、3 页。
- 补充企业详情页 `company/companys/{id}.html` 的字段核对，本次未把它作为岗位发布的必要字段。
