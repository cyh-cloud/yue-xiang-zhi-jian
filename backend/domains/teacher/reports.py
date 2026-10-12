# -*- coding: utf-8 -*-
"""教师管理域的教学报告：名册归一、概览组装、兜底报告与上游调用。

从 app.py 迁出（后端按领域拆分 T16），逐行保持原样，只把两处依赖改成显式参数：

- `datetime` 仍从标准库导入；
- AI 调用走共享层 ai.client，且按模块属性调用（`ai.client.ai_configured()`），
  因为测试改写的是这个模块属性（开关的真正持有者），import 时绑定本地名字会让
  patch 失效，用例会从「验证明确失败」退化成真的去打上游。

因 spec 的「单个领域路由文件不超过 600 行」，本域拆成两个模块，共用同一个蓝图
对象 teacher_bp：routes.py 管名册增删改查与账号绑定，本文件管教学报告。

三条口径（2026-10-07 用户拍板）在这里集中体现，改一处即可全链路一致：

- 学情口径一律是「证书真实完成度」（学员名下 certificates.progress 的平均值），
  不再读 students.progress 这个**手填**字段；
- 没有任何证书记录的学员单独列出，**不**当成 0% 完成 —— 把他们算进风险名单
  属于编造结论；
- 上游不可用时返回兜底报告，概览口径与主路径逐字一致。
"""

import logging

from ai.client import call_ai_service

logger = logging.getLogger(__name__)

def _normalize_roster_rows(students):
    """把 get_roster_completion() 的行归一成报告用的统一结构。

    ⚠️ 2026-10-07 起学情/报告口径 = **证书真实完成度**（students.progress 是手填字段，
    不再使用）。归一后统一叫 `progress`，下文沿用原变量名，避免两套口径并存。
    `has_cert_data=False` 表示该学员名下没有任何证书记录 —— 不能当成「0% 完成」。
    """
    rows = []
    for s in students or []:
        rows.append({
            'id': s.get('id', ''), 'name': s.get('name', ''),
            'direction': s.get('direction') or '未分类',
            'progress': s.get('completion', 0) or 0,
            'has_cert_data': bool(s.get('has_cert_data')),
            'cert_earned': s.get('cert_earned', 0),
            'cert_total': s.get('cert_total', 0),
            'has_account': bool(s.get('has_account')),
        })
    return rows


def _build_fallback_overview(students, prompt):
    """兜底报告的概览数据（口径：证书真实完成度）"""
    students = _normalize_roster_rows(students)
    if not students:
        return None
    total = len(students)
    with_data = [s for s in students if s['has_cert_data']]
    avg_progress = (sum(s['progress'] for s in with_data) / len(with_data)) if with_data else 0
    directions = {}
    for s in students:
        d = s.get('direction', '未分类')
        directions.setdefault(d, {'count': 0, 'progresses': [], 'students': []})
        directions[d]['count'] += 1
        directions[d]['progresses'].append(s['progress'])
        directions[d]['students'].append(s['name'])
    at_risk = [s for s in with_data if s['progress'] < 30]
    excellent = [s for s in with_data if s['progress'] >= 80]
    completed = [s for s in students if s['cert_earned'] > 0]
    brackets = {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0}
    for s in with_data:
        p = s['progress']
        if p < 25: brackets['0-25%'] += 1
        elif p < 50: brackets['25-50%'] += 1
        elif p < 75: brackets['50-75%'] += 1
        else: brackets['75-100%'] += 1

    overview = {
        "total": total, "avg_progress": round(avg_progress, 1),
        "no_cert_count": len(students) - len(with_data),
        "direction_count": len(directions), "completed_count": len(completed),
        "risk_count": len(at_risk), "excellent_count": len(excellent),
        "brackets": brackets,
        "directions": [{"name": d, "count": info['count'],
                        "avg_progress": round(sum(info['progresses'])/info['count'], 1),
                        "students": info['students']} for d, info in directions.items()],
        "at_risk": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in at_risk],
        "excellent": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in excellent]
    }

    p = prompt.lower()
    if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
        overview['focus'] = 'risk'; overview['title'] = '风险预警概览'
        overview['highlight_stats'] = ['risk_count', 'total', 'avg_progress']
    elif any(k in p for k in ['方向', '对比', '比较', '哪个', '排名']):
        overview['focus'] = 'direction'; overview['title'] = '方向对比概览'
        overview['highlight_stats'] = ['direction_count', 'total', 'avg_progress']
    elif any(k in p for k in ['进度', '滞后', '完成', '速度']):
        overview['focus'] = 'progress'; overview['title'] = '进度分析概览'
        overview['highlight_stats'] = ['avg_progress', 'completed_count', 'total']
    elif any(k in p for k in ['优秀', '突出', '表扬', '领先']):
        overview['focus'] = 'excellent'; overview['title'] = '优秀学员概览'
        overview['highlight_stats'] = ['excellent_count', 'completed_count', 'total']
    elif any(k in p for k in ['预测', '趋势', '未来', '计划']):
        overview['focus'] = 'trend'; overview['title'] = '趋势预测概览'
        overview['highlight_stats'] = ['avg_progress', 'completed_count', 'risk_count']
    elif any(k in p for k in ['效果', '评估', '教学', '质量']):
        overview['focus'] = 'performance'; overview['title'] = '教学效果概览'
        overview['highlight_stats'] = ['completed_count', 'avg_progress', 'excellent_count']
    else:
        overview['focus'] = 'general'; overview['title'] = '班级总览'
        overview['highlight_stats'] = ['total', 'avg_progress', 'direction_count']
    return overview


def _build_fallback_report(students, prompt):
    """AI不可用时根据prompt生成不同的兜底报告（口径：证书真实完成度）"""
    students = _normalize_roster_rows(students)
    if not students:
        return "## 暂无数据\n\n当前没有学员数据，请先添加学员。"

    total = len(students)
    with_data = [s for s in students if s['has_cert_data']]
    no_cert = [s for s in students if not s['has_cert_data']]
    avg_progress = (sum(s['progress'] for s in with_data) / len(with_data)) if with_data else 0
    directions = {}
    for s in students:
        d = s.get('direction', '未分类')
        directions.setdefault(d, []).append(s)

    # 风险/优秀只在「有证书记录」的学员里判 —— 没有证书记录 ≠ 0% 完成
    at_risk = sorted([s for s in with_data if s['progress'] < 30], key=lambda x: x['progress'])
    excellent = sorted([s for s in with_data if s['progress'] >= 80], key=lambda x: -x['progress'])
    completed = [s for s in students if s['cert_earned'] > 0]
    mid_risk = [s for s in with_data if 30 <= s['progress'] < 50]

    p = prompt.lower()

    # 风险主题
    if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、风险概况",
            f"当前共 **{total}** 名学员，其中 **{len(at_risk)}** 人完成度低于30%，处于高风险状态。",
            f"另有 **{len(mid_risk)}** 人完成度在30%-50%之间，需要持续关注。",
            f"**{len(no_cert)}** 人暂无任何证书记录，无法评估（不是 0% 完成）。",
            ""
        ]
        if at_risk:
            lines.append("## 二、高风险学员详情")
            for s in at_risk:
                lines.append(f"- **{s['name']}**（{s['direction']}）：完成度仅 **{s['progress']}%**，建议优先介入")
            lines.append("")
        if mid_risk:
            lines.append("## 三、中等风险学员")
            for s in mid_risk:
                lines.append(f"- {s['name']}（{s['direction']}）：完成度 {s['progress']}%，有下滑风险")
            lines.append("")
        if no_cert:
            lines.append("## 四、暂无证书记录的学员")
            for s in no_cert:
                tail = '（未关联平台账号，无法产生学习记录）' if not s['has_account'] else ''
                lines.append(f"- {s['name']}（{s['direction']}）{tail}")
            lines.append("")
        lines.append("## 五、分级干预方案")
        lines.append(f"1. **高风险（<30%）**：一对一约谈，了解学习障碍，制定个性化追赶计划")
        lines.append(f"2. **中等风险（30-50%）**：安排学习伙伴，每周检查进度")
        lines.append(f"3. **无证书记录的学员**：先确认是否已关联平台账号，再补录/核对学习记录")
        return "\n".join(lines)

    # 方向对比主题
    if any(k in p for k in ['方向', '对比', '比较', '哪个', '排名']):
        dir_stats = []
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            if not d_with:
                dir_stats.append((d, len(sts), 0.0, 0, 0, d_with))
                continue
            avg = sum(s['progress'] for s in d_with) / len(d_with)
            hi = max(s['progress'] for s in d_with)
            lo = min(s['progress'] for s in d_with)
            dir_stats.append((d, len(sts), avg, hi, lo, d_with))
        dir_stats.sort(key=lambda x: -x[2])

        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、方向排名",
            f"共 **{len(dir_stats)}** 个方向，按平均完成度排名如下：", ""
        ]
        for i, (d, cnt, avg, hi, lo, d_with) in enumerate(dir_stats):
            medal = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'{i+1}.'
            if not d_with:
                lines.append(f"{medal} **{d}**：{cnt}人，暂无证书记录，无法评估")
            else:
                lines.append(f"{medal} **{d}**：{cnt}人，平均完成度 {avg:.1f}%（最高{hi}%，最低{lo}%）")
        lines.append("")

        if len(dir_stats) >= 2:
            best = dir_stats[0]
            worst = dir_stats[-1]
            if best[5] and worst[5]:
                lines.append("## 二、差距分析")
                lines.append(f"- 最优方向 **{best[0]}** 平均完成度 {best[2]:.1f}%，最弱方向 **{worst[0]}** 平均完成度 {worst[2]:.1f}%")
                lines.append(f"- 差距 **{best[2]-worst[2]:.1f}** 个百分点")
                lines.append("")

        lines.append("## 三、资源调配建议")
        lines.append(f"1. 对完成度较低的方向增加教学资源和辅导频次")
        lines.append(f"2. 让优秀方向的学员分享学习经验")
        lines.append(f"3. 分析各方向教学方法差异，推广最佳实践")
        return "\n".join(lines)

    # 进度主题
    if any(k in p for k in ['进度', '滞后', '完成', '速度', '加快']):
        brackets = {'0-25%': [], '25-50%': [], '50-75%': [], '75-100%': []}
        for s in with_data:
            if s['progress'] < 25: brackets['0-25%'].append(s)
            elif s['progress'] < 50: brackets['25-50%'].append(s)
            elif s['progress'] < 75: brackets['50-75%'].append(s)
            else: brackets['75-100%'].append(s)

        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、完成度分布",
            f"平均完成度 **{avg_progress:.1f}%**（有证书记录的 {len(with_data)} 人），各阶段分布如下：", ""
        ]
        for k, sts in brackets.items():
            pct = len(sts)/total*100 if total else 0
            names = '、'.join(s['name'] for s in sts[:5])
            extra = f'（{names}）' if names else ''
            lines.append(f"- **{k}**：{len(sts)}人，占 {pct:.0f}% {extra}")
        if no_cert:
            lines.append(f"- **暂无证书记录**：{len(no_cert)}人（{'、'.join(s['name'] for s in no_cert)}）")
        lines.append("")

        if brackets['0-25%']:
            lines.append("## 二、完成度偏低学员")
            for s in brackets['0-25%']:
                lines.append(f"- {s['name']}（{s['direction']}）：{s['progress']}%，需要加速")
            lines.append("")

        lines.append("## 三、提速建议")
        lines.append(f"1. 为完成度<25%的学员制定每周学习目标")
        lines.append(f"2. 完成度>75%的学员可作为小组长带动后进")
        lines.append(f"3. 增加实操练习，减少纯理论学习时间")
        return "\n".join(lines)

    # 优秀主题
    if any(k in p for k in ['优秀', '突出', '表扬', '先进', '领先']):
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、优秀学员概况",
            f"当前共 **{len(excellent)}** 名学员完成度达到80%以上（有证书记录的 {len(with_data)} 人中），"
            f"另有 **{len(completed)}** 人已获得至少一张证书。", ""
        ]
        if excellent:
            lines.append("## 二、优秀学员名单")
            for s in excellent:
                lines.append(f"- **{s['name']}**（{s['direction']}）：完成度 {s['progress']}%，已获得 {s['cert_earned']}/{s['cert_total']} 张证书")
            lines.append("")

        lines.append("## 三、优秀学员特征分析")
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            d_excellent = [s for s in d_with if s['progress'] >= 80]
            if d_with:
                lines.append(f"- **{d}**：{len(d_excellent)}/{len(d_with)} 人优秀（有证书记录者中），比例 {len(d_excellent)/len(d_with)*100:.0f}%")
        lines.append("")

        lines.append("## 四、激励建议")
        lines.append(f"1. 对已获得证书的学员安排进阶课程或实践项目")
        lines.append(f"2. 安排优秀学员担任学习助教，辅导后进学员")
        lines.append(f"3. 为尚未获得证书的学员明确取证路径")
        return "\n".join(lines)

    # 预测/趋势主题
    if any(k in p for k in ['预测', '趋势', '未来', '下月', '计划']):
        completion_rate = len(completed)/total*100 if total else 0
        risk_rate = len(at_risk)/total*100 if total else 0
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、当前状态",
            f"- 获证率：**{completion_rate:.1f}%**（{len(completed)}/{total}人至少获得一张证书）",
            f"- 风险率：**{risk_rate:.1f}%**（{len(at_risk)}人完成度<30%）",
            f"- 平均完成度：**{avg_progress:.1f}%**（有证书记录的 {len(with_data)} 人）",
            f"- 暂无证书记录：**{len(no_cert)}** 人", ""
        ]
        lines.append("## 二、趋势预测")
        if avg_progress >= 60:
            lines.append(f"- 整体趋势向好，预计多数学员可在2-3个月内完成取证")
        elif avg_progress >= 40:
            lines.append(f"- 整体完成度中等，预计需要3-4个月完成，需加强辅导力度")
        else:
            lines.append(f"- 整体完成度偏慢，需要调整教学计划并加大辅导投入")
        lines.append("")
        lines.append("## 三、下阶段计划建议")
        lines.append(f"1. 对{len(at_risk)}名风险学员制定专项提升计划")
        lines.append(f"2. 每周跟踪证书进度，及时调整教学节奏")
        lines.append(f"3. 组织阶段性测评，检验学习效果")
        return "\n".join(lines)

    # 教学效果主题
    if any(k in p for k in ['效果', '评估', '教学', '质量']):
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、教学完成情况",
            f"共 **{total}** 名学员，{len(completed)} 人已获得证书，平均完成度 **{avg_progress:.1f}%**"
            f"（有证书记录的 {len(with_data)} 人），{len(no_cert)} 人暂无证书记录。", ""
        ]
        lines.append("## 二、各方向教学效果")
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            if not d_with:
                lines.append(f"- **{d}**：{len(sts)}人，暂无证书记录，无法评估")
                continue
            avg = sum(s['progress'] for s in d_with) / len(d_with)
            done = len([s for s in d_with if s['cert_earned'] > 0])
            level = '优秀' if avg >= 70 else '良好' if avg >= 50 else '需加强'
            lines.append(f"- **{d}**：{len(sts)}人，平均完成度 {avg:.1f}%，已获证{done}人，评价：{level}")
        lines.append("")
        lines.append("## 三、改进建议")
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            if d_with:
                avg = sum(s['progress'] for s in d_with) / len(d_with)
                if avg < 50:
                    lines.append(f"1. **{d}**方向完成度偏低，建议增加辅导频次和实操练习")
        lines.append(f"2. 建立学员互评机制，促进同伴学习")
        lines.append(f"3. 定期收集学员反馈，优化教学内容")
        return "\n".join(lines)

    # 默认：通用报告
    lines = [
        "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
        "",
        "## 一、总体概况",
        f"- 共 **{total}** 名学员，平均完成度 **{avg_progress:.1f}%**（有证书记录的 {len(with_data)} 人）",
        f"- {len(completed)} 人已获得至少一张证书，{len(no_cert)} 人暂无证书记录",
        f"- 涵盖 **{len(directions)}** 个方向",
        ""
    ]
    lines.append("## 二、各方向情况")
    for d, sts in directions.items():
        d_with = [s for s in sts if s['has_cert_data']]
        if not d_with:
            lines.append(f"- **{d}**：{len(sts)}人，暂无证书记录，无法评估")
            continue
        avg = sum(s['progress'] for s in d_with) / len(d_with)
        names = '、'.join(s['name'] for s in sts)
        lines.append(f"- **{d}**：{len(sts)}人，平均完成度 {avg:.1f}%，学员：{names}")
    lines.append("")
    if at_risk:
        lines.append(f"## 三、风险预警（{len(at_risk)}人）")
        for s in at_risk:
            lines.append(f"- {s['name']}（{s['direction']}）：完成度仅 {s['progress']}%")
        lines.append("")
    if excellent:
        lines.append(f"## 四、优秀学员（{len(excellent)}人）")
        for s in excellent:
            lines.append(f"- {s['name']}（{s['direction']}）：完成度 {s['progress']}%")
        lines.append("")
    lines.append("## 五、建议")
    if at_risk:
        lines.append(f"1. 对 {len(at_risk)} 名风险学员进行一对一辅导，了解学习障碍")
    if no_cert:
        lines.append(f"2. 核对 {len(no_cert)} 名无证书记录学员的账号关联与学习记录")
    lines.append(f"3. 对已获证学员安排进阶内容或实践项目")
    lines.append(f"4. 组织方向间交流活动，促进经验分享")
    return "\n".join(lines)


def generate_report(roster, user_prompt):
    """主路径：把名册数据整理成上下文，交上游生成报告。

    返回 (content, overview)。异常由调用方接管并走兜底路径，这里不做吞错。
    """
    # 全量数据采集
    total = len(roster)
    with_data = [s for s in roster if s['has_cert_data']]
    no_cert = [s for s in roster if not s['has_cert_data']]
    avg_progress = (sum(s['completion'] for s in with_data) / len(with_data)) if with_data else 0

    directions = {}
    for s in roster:
        d = s.get('direction', '未分类')
        directions.setdefault(d, {'count': 0, 'progresses': [], 'students': []})
        directions[d]['count'] += 1
        directions[d]['progresses'].append(s['completion'])
        directions[d]['students'].append(s['name'])

    # 完成度分段（只统计有证书记录的学员）
    brackets = {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0}
    for s in with_data:
        p = s['completion']
        if p < 25: brackets['0-25%'] += 1
        elif p < 50: brackets['25-50%'] += 1
        elif p < 75: brackets['50-75%'] += 1
        else: brackets['75-100%'] += 1

    # 风险/优秀只在「有证书记录」的学员里判 —— 没有证书记录 ≠ 0% 完成，
    # 把他们算进风险名单属于编造结论。
    at_risk = [s for s in with_data if s['completion'] < 30]
    excellent = [s for s in with_data if s['completion'] >= 80]
    completed = [s for s in roster if s['cert_earned'] > 0]

    # 组装数据上下文
    dir_lines = []
    for d, info in directions.items():
        avg = sum(info['progresses']) / info['count']
        hi = max(info['progresses'])
        lo = min(info['progresses'])
        names = '、'.join(info['students'])
        dir_lines.append(f"- {d}：{info['count']}人，平均完成度{avg:.1f}%，最高{hi}%，最低{lo}%，学员：{names}")

    student_lines = []
    for s in roster:
        if not s['has_cert_data']:
            status = '暂无证书记录' + ('（未关联平台账号）' if not s['has_account'] else '')
        elif s['cert_earned'] > 0:
            status = '已获得证书'
        else:
            status = '学习中'
        student_lines.append(
            f"- {s['name']}（学号 {s['id']}{'，账号 ' + s['user_id'] if s['has_account'] else '，未关联平台账号'}）"
            f"方向={s['direction']} 完成度={s['completion']}% "
            f"证书={s['cert_earned']}/{s['cert_total']}已获得 状态={status}")

    risk_lines = [f"- {s['name']}：完成度{s['completion']}%，方向{s['direction']}" for s in at_risk]
    good_lines = [f"- {s['name']}：完成度{s['completion']}%，方向{s['direction']}" for s in excellent]

    data_context = f"""数据口径：证书真实完成度（学员名下证书进度的平均值；没有任何证书记录的学员单独列出，不计入完成度分布）
学员总数：{total}
平均完成度：{avg_progress:.1f}%（有证书记录的 {len(with_data)} 人）
暂无证书记录：{len(no_cert)}人{('（' + '、'.join(s['name'] for s in no_cert) + '）') if no_cert else ''}
方向数量：{len(directions)}
已获得证书学员：{len(completed)}人
风险学员（完成度<30%）：{len(at_risk)}人
优秀学员（完成度>=80%）：{len(excellent)}人

完成度分布：
{chr(10).join(f'{k}: {v}人' for k, v in brackets.items())}

各方向详情：
{chr(10).join(dir_lines)}

全部学员：
{chr(10).join(student_lines)}

风险学员名单：
{chr(10).join(risk_lines) if risk_lines else '无'}

优秀学员名单：
{chr(10).join(good_lines) if good_lines else '无'}"""

    result = call_ai_service(
        system_prompt=(
            "你是一位资深教学数据分析师。用户会给你一份学员数据和一个具体的分析问题。"
            "你必须紧紧围绕用户的问题来生成报告，不要生成与问题无关的内容。\n"
            "要求：\n"
            "1）报告标题和所有小节都要围绕用户的问题展开\n"
            "2）引用具体数据和学员姓名，不要泛泛而谈\n"
            "3）建议要具体可执行，不要空话套话\n"
            "4）不同问题生成完全不同的报告结构和内容，禁止千篇一律"
        ),
        user_message=f"## 用户的问题\n{user_prompt}\n\n## 学员数据\n{data_context}\n\n请围绕上述问题生成报告。"
    )

    # 构建概览数据
    overview = {
        "total": total,
        "avg_progress": round(avg_progress, 1),
        "no_cert_count": len(no_cert),
        "direction_count": len(directions),
        "completed_count": len(completed),
        "risk_count": len(at_risk),
        "excellent_count": len(excellent),
        "brackets": brackets,
        "directions": [
            {"name": d, "count": info['count'],
             "avg_progress": round(sum(info['progresses'])/info['count'], 1),
             "students": info['students']}
            for d, info in directions.items()
        ],
        "at_risk": [{"name": s['name'], "progress": s['completion'], "direction": s['direction']} for s in at_risk],
        "excellent": [{"name": s['name'], "progress": s['completion'], "direction": s['direction']} for s in excellent]
    }

    # 根据 prompt 分析报告主题，决定概览侧重点
    focus, title, highlight = _classify_prompt(user_prompt)
    overview['focus'] = focus
    overview['title'] = title
    overview['highlight_stats'] = highlight

    return {"content": result, "overview": overview}


def _classify_prompt(prompt):
    """按 prompt 判定报告主题，返回 (focus, title, highlight_stats)。

    关键词顺序即优先级：风险优先于方向，方向优先于进度，依此类推。
    主路径与兜底路径共用这一份判定，保证同一个 prompt 在两种路径下得到同一个
    主题判断 —— 否则同一个问题会在 AI 可用/不可用时呈现出不同侧重点。
    """
    p = prompt.lower()
    if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
        return 'risk', '风险预警概览', ['risk_count', 'total', 'avg_progress']
    if any(k in p for k in ['方向', '对比', '比较', '哪个', '排名', '对比分析']):
        return 'direction', '方向对比概览', ['direction_count', 'total', 'avg_progress']
    if any(k in p for k in ['进度', '滞后', '完成', '速度', '加快']):
        return 'progress', '进度分析概览', ['avg_progress', 'completed_count', 'total']
    if any(k in p for k in ['优秀', '突出', '表扬', '先进', '领先']):
        return 'excellent', '优秀学员概览', ['excellent_count', 'completed_count', 'total']
    if any(k in p for k in ['预测', '趋势', '未来', '下月', '计划']):
        return 'trend', '趋势预测概览', ['avg_progress', 'completed_count', 'risk_count']
    if any(k in p for k in ['效果', '评估', '教学', '质量']):
        return 'performance', '教学效果概览', ['completed_count', 'avg_progress', 'excellent_count']
    return 'general', '班级总览', ['total', 'avg_progress', 'direction_count']