#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给管理端「内容审核」造待审核 / 已驳回测试数据（2026-10-10）。

做法：全部走真实接口，保证 courses / models_3d / job_listings 目标行与
content_reviews 审核记录一致，管理端卡片详情（公司、薪资、craft 类型等）能正常关联。

  · teacher_demo 建 3 门课程（自动挂 pending 审核）
  · teacher_demo 传 2 个最小合法 glTF 模型（自动挂 pending 审核）
  · enterprise_demo 发 3 个职位（自动挂 pending 审核）
  · admin_demo 驳回其中 3 条（课程 / 模型 / 职位各一），带驳回理由

用法：.venv\\Scripts\\python.exe _seed_review_data.py
"""
import json
import os

import requests

from run import resolve_port

# 跟随 .env / 环境变量的 PORT，多工作树各自改端口时脚本不会打错实例
BASE = 'http://127.0.0.1:' + str(resolve_port()[0])
OUT = os.path.join('uploads', 'models_3d')

# 最小合法 glTF 2.0（一个退化点），模型审核卡片只展示元信息，预览不至于解析失败
MINI_GLTF = {
    "asset": {"version": "2.0", "generator": "yuexiang-seed"},
    "scenes": [{"nodes": [0]}],
    "nodes": [{"mesh": 0, "name": "seed"}],
    "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}], "name": "seed"}],
    "buffers": [{"uri": "data:application/octet-stream;base64,AAAAAAAAAAAAAAAAAAAAAA==", "byteLength": 12}],
    "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 12, "target": 34962}],
    "accessors": [{
        "bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC3",
        "min": [0, 0, 0], "max": [0, 0, 0],
    }],
}


def login(u, p):
    r = requests.post(BASE + '/api/auth/login',
                      json={'username': u, 'password': p}, timeout=20)
    d = r.json()
    assert d.get('success'), d
    return d['session_id']


def call(sid, method, path, payload=None):
    r = requests.request(method, BASE + path, json=payload, timeout=30,
                         headers={'X-Session-Id': sid})
    return r.status_code, r.json()


def find_review(admin, ctype, cid):
    """按 (内容类型, 内容 ID) 找待审核记录 ID。

    注意：审核接口吃的是 content_reviews.id，与内容 ID 是两条序列，不能混用。
    """
    code, body = call(admin, 'GET', '/api/admin/reviews?status=pending')
    rid = None
    for rv in body.get('reviews') or []:
        if rv['content_type'] == ctype and rv['content_id'] == cid:
            rid = rv['id']
    return rid


def create_courses(teacher):
    specs = [
        ('荔枝冬季管理实战：清园、控梢与防寒', '种植基础',
         '围绕广东荔枝产区的冬季管理窗口，讲解清园封园、控梢促花、防寒防冻三个环节的操作要点与常见失误。'),
        ('淡水养殖水质快速判断法', '水产养殖',
         '教养殖户用看水色、测透明度、观鱼情三种低成本方法判断水质，配套对应调水措施。'),
        ('镇村电商服务站经营入门', '农村电商',
         '面向镇村一级的电商服务站经营者，讲解代买代卖、收发快递、增值服务的组合经营模式。'),
    ]
    ids = []
    for title, category, desc in specs:
        code, body = call(teacher, 'POST', '/api/teacher/courses', {
            'title': title, 'description': desc, 'category': category,
        })
        assert body.get('success'), body
        ids.append(body['id'])
        print('课程 %s -> %s' % (body['id'], title))
    return ids


def upload_models(teacher):
    os.makedirs(OUT, exist_ok=True)
    specs = [
        ('广绣 Triple-Stitch 针法分解模型', 'embroidery', '广绣基础针法教学模型，含起针、走线、收针三个关键步骤。'),
        ('潮汕木雕龙虾蟹篓结构模型', 'woodcarving', '经典「龙虾蟹篓」镂空结构示意，展示层次穿透关系。'),
    ]
    ids = []
    for title, craft, desc in specs:
        path = os.path.join(OUT, 'seed_%s.gltf' % craft)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(MINI_GLTF, f)
        with open(path, 'rb') as f:
            r = requests.post(
                BASE + '/api/teacher/models-3d', timeout=60,
                headers={'X-Session-Id': teacher},
                data={'title': title, 'description': desc, 'craft_type': craft},
                files={'file': (os.path.basename(path), f, 'model/gltf+json')})
        body = r.json()
        assert body.get('success'), body
        ids.append(body['id'])
        print('模型 %s -> %s' % (body['id'], title))
    return ids


def create_jobs(enterprise):
    specs = [
        ('荔枝园季节性管护工', '面议', '茂名·高州', '农业种植',
         ['能适应户外作业', '有果园管护经验者优先'],
         '负责荔枝园冬季修剪、施肥与病虫害巡查，管护期提供住宿。'),
        ('农村电商直播助播', '5000-8000元/月', '广州·白云', '电商运营',
         ['普通话流利', '可接受晚间直播排班'],
         '协助主播完成直播带货，负责场控、改价与售后登记。'),
        ('非遗广绣文创质检员', '4500-6000元/月', '汕头·潮州', '手工艺',
         ['熟悉广绣针法基础', '工作细致'],
         '对广绣文创成品进行针法、色差与完整性抽检，记录质检结果。'),
    ]
    ids = []
    for title, salary, location, category, reqs, desc in specs:
        code, body = call(enterprise, 'POST', '/api/enterprise/jobs', {
            'title': title, 'salary': salary, 'location': location,
            'category': category, 'requirements': reqs, 'description': desc,
            'job_type': '全职', 'education': '不限', 'experience': '不限',
        })
        assert body.get('success'), body
        ids.append(body['id'])
        print('职位 %s -> %s' % (body['id'], title))
    return ids


def reject_some(admin, course_ids, model_ids, job_ids):
    targets = [
        ('course', course_ids[0], '课程', '缺少配套课件与课时安排，请补充后再提交。'),
        ('model_3d', model_ids[0], '3D模型', '模型面数过低，针法细节无法看清，请替换为精细版。'),
        ('job', job_ids[1], '职位', '薪资区间与岗位职责不匹配，请核实后重新发布。'),
    ]
    for ctype, cid, label, comment in targets:
        rid = find_review(admin, ctype, cid)
        assert rid, '找不到 %s #%s 的待审核记录' % (ctype, cid)
        code, body = call(admin, 'POST', '/api/admin/reviews/%d/reject' % rid,
                          {'comment': comment})
        print('驳回 %s（审核记录 #%d）-> %s（%s）' % (label, rid, body.get('message'), comment))


def summary(admin):
    for st in ('pending', 'rejected', 'approved'):
        code, body = call(admin, 'GET', '/api/admin/reviews?status=' + st)
        by_type = {}
        for rv in body.get('reviews') or []:
            by_type[rv['content_type']] = by_type.get(rv['content_type'], 0) + 1
        total = sum(by_type.values())
        counts = body.get('counts') or {}
        print('%-9s 列表 %d 条 %s | 页签计数 pending=%s approved=%s rejected=%s'
              % (st, total, by_type, counts.get('pending'), counts.get('approved'),
                 counts.get('rejected')))


if __name__ == '__main__':
    teacher = login('teacher_demo', '123456')
    enterprise = login('enterprise_demo', '123456')
    admin = login('admin_demo', 'admin123')

    print('=== 创建待审核内容 ===')
    course_ids = create_courses(teacher)
    model_ids = upload_models(teacher)
    job_ids = create_jobs(enterprise)

    print('')
    print('=== 驳回 3 条（课程 / 模型 / 职位各一）===')
    reject_some(admin, course_ids, model_ids, job_ids)

    print('')
    print('=== 审核列表汇总 ===')
    summary(admin)
