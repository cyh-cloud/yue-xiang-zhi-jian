# -*- coding: utf-8 -*-
"""上传体积上限的单一真相源。

应用工厂用它配置 Flask，领域路由用它做业务级校验；nginx 的对应值由
``tests/test_frontend_build_contract.py`` 机械比对，避免代理层先于应用拒绝请求。
"""

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_UPLOAD_MEGABYTES = MAX_UPLOAD_BYTES // (1024 * 1024)

# Flask's MAX_CONTENT_LENGTH covers the whole multipart request, not just the
# file part. Leave deterministic room for boundaries, filenames and form fields
# so a file exactly at the product limit is not rejected by transport overhead.
MULTIPART_OVERHEAD_BYTES = 1 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
MAX_REQUEST_MEGABYTES = (MAX_REQUEST_BYTES + 1024 * 1024 - 1) // (1024 * 1024)

# 模型上传的格式白名单。路由校验与前端提示都从这里取，避免两边各写一份。
MODEL_3D_EXTENSIONS = ('glb', 'gltf', 'obj', 'fbx', 'stl', 'dae', 'ply', 'usdz')


__all__ = [
    'MAX_UPLOAD_BYTES',
    'MAX_UPLOAD_MEGABYTES',
    'MULTIPART_OVERHEAD_BYTES',
    'MAX_REQUEST_BYTES',
    'MAX_REQUEST_MEGABYTES',
    'MODEL_3D_EXTENSIONS',
]
