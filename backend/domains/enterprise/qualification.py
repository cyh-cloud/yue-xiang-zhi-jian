# -*- coding: utf-8 -*-
"""企业资质认证的企业侧接口：查看状态、提交材料、取回自己的证件照。

三条边界：

1. **证件照存私有目录**。`data/qualifications/` 不在静态放行目录里
   （见 domains/static_files/routes.py 只放行 uploads 与 images），只能经本文件的
   鉴权接口取回；对外响应只给 `has_license` 布尔值，不给路径。
2. **提交只认本人**。user_id 一律取自会话，不接受请求体传入。
3. **不覆盖历史**。重交是新行，旧行留着；已有待审或有效期内的通过记录时直接拒绝，
   避免审核队列里出现同一家企业的多份材料。
"""

import os
import re
import uuid

from flask import jsonify, request, send_file

from core.permissions import require_capability
from core.session import get_session_user
from db_domains import qualifications
from domains.enterprise.routes import enterprise_bp
from shared.credit_code import is_valid as credit_code_valid
from shared.credit_code import mask as mask_credit_code
from shared.credit_code import normalize as normalize_credit_code
from shared.enterprise_limits import (
    QUALIFICATION_ALLOWED_EXTENSIONS,
    QUALIFICATION_LICENSE_DIR,
    QUALIFICATION_MAX_BYTES,
    QUALIFICATION_STATUS_LABELS,
    UNVERIFIED_ACTIVE_JOB_LIMIT,
)

# 蓝图对象在 routes.py 里定义，本模块只往它上面挂路由（一个领域一个蓝图）。


def _safe_name(user_id):
    """用户 id 转成安全文件名前缀。用户名含中文或符号时统一归一化。"""
    return re.sub(r'[^A-Za-z0-9_-]', '_', user_id or 'enterprise')


def _public_record(record):
    """对外视图：去掉证件路径，只留布尔；信用代码脱敏。"""
    if not record:
        return None
    return {
        'id': record['id'],
        'company_name': record['company_name'],
        'credit_code_masked': mask_credit_code(record['credit_code']),
        'legal_person': record['legal_person'],
        'contact_phone': record['contact_phone'],
        'address': record['address'],
        'industry': record['industry'],
        'company_size': record['company_size'],
        'status': record['status'],
        'status_label': QUALIFICATION_STATUS_LABELS.get(record['status'],
                                                        record['status']),
        'review_comment': record['review_comment'],
        'submitted_at': record['submitted_at'],
        'reviewed_at': record['reviewed_at'] or '',
        'expires_at': record['expires_at'] or '',
        'has_license': bool(record['license_file']),
        'license_name': record['license_name'],
    }


@enterprise_bp.route('/api/enterprise/qualification', methods=['GET'])
@require_capability('job.manage')
def enterprise_get_qualification():
    user = get_session_user()
    state = qualifications.status_of(user['username'])
    return jsonify({
        "success": True,
        "status": state['status'],
        "status_label": QUALIFICATION_STATUS_LABELS.get(state['status'],
                                                        state['status']),
        "verified": state['verified'],
        "record": _public_record(state['record']),
        "limits": {"unverified_active_jobs": UNVERIFIED_ACTIVE_JOB_LIMIT},
    })


@enterprise_bp.route('/api/enterprise/qualification', methods=['POST'])
@require_capability('job.manage')
def enterprise_submit_qualification():
    user = get_session_user()

    company_name = (request.form.get('company_name') or '').strip()
    credit_code = normalize_credit_code(request.form.get('credit_code') or '')
    legal_person = (request.form.get('legal_person') or '').strip()
    contact_phone = (request.form.get('contact_phone') or '').strip()
    address = (request.form.get('address') or '').strip()
    industry = (request.form.get('industry') or '').strip()
    company_size = (request.form.get('company_size') or '').strip()

    if not company_name:
        return jsonify({"success": False, "code": "bad_request",
                        "message": "请填写企业名称"}), 400
    if not credit_code:
        return jsonify({"success": False, "code": "bad_request",
                        "message": "请填写统一社会信用代码"}), 400
    if not credit_code_valid(credit_code):
        return jsonify({
            "success": False, "code": "invalid_credit_code",
            "message": "统一社会信用代码校验不通过：请核对 18 位代码是否与营业执照一致"
        }), 400

    upload = request.files.get('license')
    license_file = ''
    license_name = ''
    if upload is not None and (upload.filename or '').strip():
        filename = upload.filename.strip()
        ext = os.path.splitext(filename)[1].lower()
        if ext not in QUALIFICATION_ALLOWED_EXTENSIONS:
            return jsonify({
                "success": False, "code": "bad_file_type",
                "message": "营业执照仅支持 JPG / PNG / PDF 三种格式"
            }), 400
        blob = upload.read()
        if len(blob) > QUALIFICATION_MAX_BYTES:
            return jsonify({
                "success": False, "code": "file_too_large",
                "message": "营业执照文件不能超过 5MB"
            }), 400
        if not blob:
            return jsonify({"success": False, "code": "bad_request",
                            "message": "营业执照文件为空，请重新选择"}), 400
        os.makedirs(QUALIFICATION_LICENSE_DIR, exist_ok=True)
        license_name = filename
        # 文件名用 uuid 而不是时间戳：同一秒内的两次提交会撞名（实测：第一次提交
        # 成功后紧接着重交被 409 拒绝，清理时按同名删掉了第一次的文件）。
        license_file = '%s-%s%s' % (_safe_name(user['username']),
                                    uuid.uuid4().hex[:12], ext)
        with open(os.path.join(QUALIFICATION_LICENSE_DIR, license_file), 'wb') as handle:
            handle.write(blob)

    qualification_id, error = qualifications.submit(user['username'], {
        'company_name': company_name,
        'credit_code': credit_code,
        'legal_person': legal_person,
        'contact_phone': contact_phone,
        'address': address,
        'industry': industry,
        'company_size': company_size,
        'license_file': license_file,
        'license_name': license_name,
    })
    if error:
        # 提交被拒时不留下孤儿文件，否则私有目录会越积越多。
        if license_file:
            try:
                os.remove(os.path.join(QUALIFICATION_LICENSE_DIR, license_file))
            except OSError:
                pass
        return jsonify({"success": False, "code": "conflict",
                        "message": error}), 409

    return jsonify({
        "success": True,
        "id": qualification_id,
        "message": "资质材料已提交，等待审核" if license_file
                   else "资质材料已提交（未上传营业执照，审核时可能被要求补充）"
    })


@enterprise_bp.route('/api/enterprise/qualification/withdraw', methods=['POST'])
@require_capability('job.manage')
def enterprise_withdraw_qualification():
    """撤回在审的资质申请。传错文件时不用干等审核。"""
    user = get_session_user()
    record = qualifications.get_latest(user['username'])
    if not record or record['status'] != 'pending':
        return jsonify({"success": False, "code": "conflict",
                        "message": "当前没有正在审核的申请"}), 409
    if not qualifications.withdraw(record['id'], user['username']):
        return jsonify({"success": False, "code": "conflict",
                        "message": "撤回失败，请刷新后重试"}), 409
    return jsonify({"success": True, "message": "已撤回，可重新提交材料"})


@enterprise_bp.route('/api/enterprise/qualification/license', methods=['GET'])
@require_capability('job.manage')
def enterprise_get_license():
    """取回本企业最近一次提交的证件照。"""
    user = get_session_user()
    record = qualifications.get_latest(user['username'])
    if not record or not record['license_file']:
        return jsonify({"success": False, "code": "not_found",
                        "message": "尚未上传营业执照"}), 404

    path = os.path.join(QUALIFICATION_LICENSE_DIR,
                        os.path.basename(record['license_file']))
    if not os.path.isfile(path):
        return jsonify({"success": False, "code": "not_found",
                        "message": "文件已不存在"}), 404
    return send_file(path, as_attachment=False,
                     download_name=record['license_name'] or 'license')
