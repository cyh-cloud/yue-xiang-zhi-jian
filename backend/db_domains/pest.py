# -*- coding: utf-8 -*-
"""病虫害域的数据访问层：作物、条目、来源、条目与来源多对多、实拍图。

T07 把读取从代码常量切到 T04 建的五张 pest 表。内容由
migrations/0001_content_to_db.py 灌入，本模块只负责读，不写。

T14 补上写侧（运营后台），读侧口径一条不动。写侧守住同一批硬约定：

  1. 五个 JSON 列（symptoms / treatment / prevention / registered / chem_table）
     只接受 list 输入，空列表写 '[]'，绝不写 None 或不合法 JSON；
  2. 来源必须是 pest_sources 里已登记的 key，写不存在的 key 等于造一条
     「看不到出处」的条目，直接 ValueError；
  3. 实拍图表 entry_id 是主键（一条条目最多一张图），重复写入按覆盖处理。

两条硬约定由这个模块兜住，不靠路由自觉：

  1. 来源没给就显示未提供：JSON 列解析失败或字段缺失时按「空」处理，绝不用一个
     看起来合理的值补上（不写默认药剂名、不写「以当地农技站为准」当代填文案）。
  2. 无授权图不冒充：pest_images 里没有行的条目，image 就是 None。没有任何
     「找不到图就给个示意图 URL」的分支。

输出形状与切换前的代码常量视图逐字段一致，这是路由层能零改动的前提：
  · 条目 dict 的键、类型、空值表示（'' 与 None）与旧 entry 相同；
  · sources 展开成带全部来源字段的 dict，顺序按 pest_entry_sources.sort_order
    （迁移脚本按 entry['sources'] 的列表顺序写入，故与旧版逐项一致）；
  · image 与 pest_image_manifest.PEST_IMAGES 的值同形。

查询次数是固定的三次（条目、来源关联、实拍图），不随条目数增长：
45 条条目按条目循环查两次的话是 91 次查询，本地 SQLite 每次都要开关一次连接。
"""

import json

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES 与
# tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import 本模块，
# 谁就必须持 pest.manage（读操作受 pest.read 管，它是空元组，公开）。
CAPABILITY = 'pest'

# 存 JSON 数组文本的列。解析失败按空列表处理，不抛异常、不猜内容。
_JSON_LIST_COLUMNS = ('symptoms', 'treatment', 'prevention', 'registered', 'chem_table')

# 写侧字段白名单。id / extra 不在其中：id 由调用方给出（条目是字符串主键），
# extra 是预留列，运营后台不碰。
_ENTRY_WRITABLE = ('crop_id', 'disease', 'alias', 'kind', 'pathogen', 'part',
                   'severity', 'symptoms', 'occurrence', 'treatment', 'prevention',
                   'registered', 'chem_table', 'safety_note', 'is_verified',
                   'sort_order')
_CROP_WRITABLE = ('name', 'icon', 'summary', 'sort_order')
_SOURCE_WRITABLE = ('name', 'org', 'doc_type', 'doc_no', 'date', 'url', 'sort_order')
_IMAGE_WRITABLE = ('file', 'credit', 'license', 'caption', 'source_url',
                   'shot_date', 'note')

# 复核过期阈值（天）。与 farming.REVIEW_STALE_DAYS 同口径：半年按 365/2 取整，
# 不按 30*6，否则 2 月核的到 8 月就该重核，比「半年」短了 12 天。
REVIEW_STALE_DAYS = 183

# 作物列表的排序键：与切换前 PEST_CROP_ORDER 一致（迁移脚本按它写 sort_order）
_CROPS_SQL = "SELECT * FROM pest_crops ORDER BY sort_order, id"

# 条目列表：JOIN 作物层把作物名与图标一起取回来（切换前的 crop_name / crop_icon
# 就是从作物层取的），排序先作物序、再条目序，与切换前 iter_pest_entries() 一致，
# 这样不带参数取全量时，条目顺序逐字节等价。
_ENTRIES_SQL = """SELECT e.id, e.crop_id, e.disease, e.alias, e.kind, e.pathogen,
                          e.part, e.severity, e.symptoms, e.occurrence, e.treatment,
                          e.prevention, e.registered, e.chem_table, e.safety_note,
                          e.is_verified, e.verified_by, e.verified_at,
                          c.name AS crop_name, c.icon AS crop_icon
                     FROM pest_entries e
                     JOIN pest_crops c ON c.id = e.crop_id
                    WHERE (? IS NULL OR e.crop_id = ?)
                 ORDER BY c.sort_order, e.sort_order, e.id"""

# 单条条目查询：列清单与 _ENTRIES_SQL 逐字相同（_entry_dict 依赖同样的键），
# 只把过滤条件换成主键。⚠️ 不能直接复用 _ENTRIES_SQL 传 (None, entry_id)：
# 它的两个占位符都是 crop_id，第二个会把 entry_id 当成作物 id 去比，永远查不到。
_ENTRY_SQL = _ENTRIES_SQL.replace("(? IS NULL OR e.crop_id = ?)", "e.id = ?")


def _json_list(value):
    """把 JSON 数组列解析成列表。空值、非数组、解析失败一律给 []。"""
    if value is None or value == '':
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _crop_dict(row):
    return {'id': row['id'], 'name': row['name'], 'icon': row['icon'] or '',
            'summary': row['summary'] or ''}


def _entry_dict(row):
    """把 pest_entries 一行转成与切换前 entry dict 同形的视图。

    只放条目自己的字段。sources 与 image 由 get_pest_entries 统一补上，
    因为它们是另外两张表，按条目循环查会把查询次数放大 45 倍。
    """
    entry = {
        'id': row['id'],
        'crop': row['crop_id'],
        'crop_name': row['crop_name'],
        'crop_icon': row['crop_icon'] or '',
        'disease': row['disease'],
        'alias': row['alias'] or '',
        'kind': row['kind'] or '',
        'pathogen': row['pathogen'] or '',
        'part': row['part'] or '',
        'severity': row['severity'] or '',
        'occurrence': row['occurrence'] or '',
        'safety_note': row['safety_note'] or '',
        'is_verified': int(row['is_verified'] or 0),
        # T14：复核人与复核时间一并带出，供运营后台的「该重新核了」列表用。
        # 不下发给前台：domains/pest/knowledge.py 的 pest_entry_view 是显式挑字段的，
        # 多这两个键不会出现在对外响应里。
        'verified_by': row['verified_by'] or '',
        'verified_at': row['verified_at'] or '',
    }
    for column in _JSON_LIST_COLUMNS:
        entry[column] = _json_list(row[column])
    return entry


def _image_dict(row):
    """实拍图视图。字段与 pest_image_manifest.PEST_IMAGES 的值逐一对齐。"""
    return {
        'file': row['file'] or '',
        'credit': row['credit'] or '',
        'license': row['license'] or '',
        'caption': row['caption'] or '',
        'source_url': row['source_url'] or '',
        'shot_date': row['shot_date'] or '',
        'note': row['note'] or '',
    }


def get_pest_crops():
    """返回全部作物，按 sort_order 排序（与切换前 PEST_CROP_ORDER 同序）。"""
    conn = get_connection()
    try:
        rows = conn.execute(_CROPS_SQL).fetchall()
    except Exception:
        return []
    finally:
        conn.close()
    return [_crop_dict(row) for row in rows]


def get_pest_crop_ids():
    """返回全部作物 id，按 sort_order 排序（与切换前 PEST_CROP_ORDER 同序）。"""
    return [crop['id'] for crop in get_pest_crops()]


def get_pest_crop(crop_id):
    """按 id 取单个作物，不存在返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM pest_crops WHERE id = ?",
                           (crop_id,)).fetchone()
    except Exception:
        row = None
    finally:
        conn.close()
    return _crop_dict(row) if row else None


# 来源下发给前端的字段。刻意不是 pest_sources 的全部列：sort_order 与 extra 是
# 排序和扩展用的，切换前 PEST_SOURCE_MAP 的值里没有这两个键，带上它们会让接口
# 响应多出字段，破坏逐字节一致。
_SOURCE_FIELDS = ('key', 'name', 'org', 'doc_type', 'doc_no', 'date', 'url')


def _source_dict(row):
    return {field: (row[field] or '') for field in _SOURCE_FIELDS}


def get_pest_source_map():
    """返回 {source_key: 来源 dict}，字段与切换前 PEST_SOURCE_MAP 的值一致。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM pest_sources ORDER BY sort_order, key").fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return {row['key']: _source_dict(row) for row in rows}


def _source_keys_by_entry(conn):
    """返回 {entry_id: [source_key, ...]}，顺序按 pest_entry_sources.sort_order。"""
    try:
        rows = conn.execute(
            "SELECT entry_id, source_key FROM pest_entry_sources "
            "ORDER BY entry_id, sort_order, source_key").fetchall()
    except Exception:
        return {}
    out = {}
    for row in rows:
        out.setdefault(row['entry_id'], []).append(row['source_key'])
    return out


def _images_by_entry(conn):
    """返回 {entry_id: 实拍图 dict}。没有授权图的条目不出现在结果里。

    这条对应硬约定「无授权图不冒充」：缺行就是缺图，读出来就是 None，
    不在这里补任何占位值。
    """
    try:
        rows = conn.execute("SELECT * FROM pest_images").fetchall()
    except Exception:
        return {}
    return {row['entry_id']: _image_dict(row) for row in rows if row['file']}


def get_pest_entries(crop_id=None, with_details=True):
    """返回病虫害条目列表（可按作物过滤），按作物序与条目序排序。

    with_details=True 时每条带上 sources（展开成来源 dict）与 image（无授权图
    为 None）；False 时只给条目自身字段，供诊断降级路径用 —— 它只读病名与症状，
    少两次无关查询。

    不带参数时与切换前的 iter_pest_entries() 逐条等价（键、值、顺序都对齐）。
    """
    conn = get_connection()
    try:
        rows = conn.execute(_ENTRIES_SQL, (crop_id, crop_id)).fetchall()
        if not with_details:
            return [_entry_dict(row) for row in rows]
        source_map = get_pest_source_map()
        source_keys = _source_keys_by_entry(conn)
        images = _images_by_entry(conn)
    except Exception:
        return []
    finally:
        conn.close()

    entries = []
    for row in rows:
        entry = _entry_dict(row)
        keys = source_keys.get(entry['id'], [])
        entry['sources'] = [source_map[key] for key in keys if key in source_map]
        entry['image'] = images.get(entry['id'])
        entries.append(entry)
    return entries


def get_pest_entry(entry_id):
    """按 id 取单条条目（含 sources 与 image），不存在返回 None。

    SELECT 必须带 JOIN 作物层：_entry_dict 要 crop_name 与 crop_icon，
    用 SELECT * 会 KeyError，再被下面的 except 吞成 None —— 症状是
    「库里明明有这一条却永远取不到」。T14 补写侧时实测到这一点。
    """
    conn = get_connection()
    try:
        row = conn.execute(_ENTRY_SQL, (entry_id,)).fetchone()

        if not row:
            return None
        entry = _entry_dict(row)
        source_map = get_pest_source_map()
        keys = _source_keys_by_entry(conn).get(entry_id, [])
        images = _images_by_entry(conn)
    except Exception:
        return None
    finally:
        conn.close()
    entry['sources'] = [source_map[key] for key in keys if key in source_map]
    entry['image'] = images.get(entry_id)
    return entry


def get_pest_stats():
    """统计作物数、条目数、有授权图条目数、已复核条目数。

    口径与切换前 pest_data.get_pest_stats() 一致：crops 数
    pest_crops、entries 数 pest_entries、with_image 数 pest_images 里有 file 的行、
    verified 数 is_verified 非零的条目。
    """
    conn = get_connection()
    try:
        return {
            'crops': conn.execute("SELECT COUNT(*) FROM pest_crops").fetchone()[0],
            'entries': conn.execute("SELECT COUNT(*) FROM pest_entries").fetchone()[0],
            'with_image': conn.execute(
                "SELECT COUNT(*) FROM pest_images "
                "WHERE file IS NOT NULL AND file != ''").fetchone()[0],
            'verified': conn.execute(
                "SELECT COUNT(*) FROM pest_entries WHERE is_verified = 1"
            ).fetchone()[0],
        }
    except Exception:
        return {'crops': 0, 'entries': 0, 'with_image': 0, 'verified': 0}
    finally:
        conn.close()


# ==================== 运营维护（写侧，T14） ====================
# 三条口径见模块 docstring。所有写函数都遵守同一个形状：取值 -> 校验 -> 开连接
# -> 执行 -> commit -> close。本域没有跨域删除，pest_* 五张表的外键级联
# （foreign_keys=ON）覆盖了「删作物连带删条目、删条目连带删关联与图」。


def _pick(fields, allowed):
    """按白名单挑出要写的列。None 表示「不碰这一列」，与「置空」是两件事。"""
    return {k: v for k, v in fields.items() if k in allowed and v is not None}


def _json_dump_list(value, column):
    """把 list 字段序列化回 JSON 文本。只接受 list，其余一律 ValueError。

    与读侧 _json_list 对称：读侧解析失败给 []，写侧就必须拒绝写坏，
    否则一条坏数据会被静默读成空列表，「来源写了但没存进去」这种事看不出痕迹。
    """
    if not isinstance(value, list):
        raise ValueError('%s 必须是数组' % column)
    return json.dumps(value, ensure_ascii=False)


def _require_source_keys(conn, keys):
    """来源 key 必须已登记在 pest_sources 里。返回去重后的合法 key 列表。"""
    known = {row['key'] for row in conn.execute("SELECT key FROM pest_sources").fetchall()}
    unknown = [k for k in keys if k not in known]
    if unknown:
        raise ValueError('未登记的来源：%s' % ', '.join(sorted(unknown)))
    return list(dict.fromkeys(keys))


def _replace_entry_sources(conn, entry_id, source_keys):
    """整表替换某条条目的来源关联（多对多，按传进来的顺序写 sort_order）。"""
    conn.execute("DELETE FROM pest_entry_sources WHERE entry_id = ?", (entry_id,))
    for order, key in enumerate(source_keys):
        conn.execute(
            "INSERT INTO pest_entry_sources (entry_id, source_key, sort_order) "
            "VALUES (?, ?, ?)", (entry_id, key, order))


# ---- 病虫害条目 ----

def create_pest_entry(entry_id, crop_id, disease, **fields):
    """新增一条病虫害条目，返回 entry_id（字符串主键由调用方给出）。"""
    entry_id = (entry_id or '').strip()
    crop_id = (crop_id or '').strip()
    disease = (disease or '').strip()
    if not entry_id:
        raise ValueError('条目 id 不能为空')
    if not crop_id:
        raise ValueError('缺少 crop_id')
    if not disease:
        raise ValueError('病害名称不能为空')

    values = _pick(fields, _ENTRY_WRITABLE)
    for column in _JSON_LIST_COLUMNS:
        if column in values:
            values[column] = _json_dump_list(values[column], column)
    if 'disease' in values:
        values['disease'] = (values['disease'] or '').strip()
    if values.get('disease') == '':
        raise ValueError('病害名称不能为空')
    values.update({'id': entry_id, 'crop_id': crop_id, 'disease': disease})

    conn = get_connection()
    try:
        _require_crop(conn, crop_id)
        columns = ', '.join(values)
        conn.execute(
            "INSERT INTO pest_entries (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        if 'source_keys' in fields:
            _replace_entry_sources(conn, entry_id, _require_source_keys(
                conn, _string_list(fields.get('source_keys'))))
        conn.commit()
    finally:
        conn.close()
    return entry_id


def update_pest_entry(entry_id, **fields):
    """按白名单改一条条目。source_keys 单独走多对多整表替换。"""
    source_keys = fields.pop('source_keys', None)
    updates = _pick(fields, _ENTRY_WRITABLE)
    for column in _JSON_LIST_COLUMNS:
        if column in updates:
            updates[column] = _json_dump_list(updates[column], column)
    if 'disease' in updates:
        updates['disease'] = (updates['disease'] or '').strip()
    if updates.get('disease') == '':
        raise ValueError('病害名称不能为空')

    conn = get_connection()
    try:
        if 'crop_id' in updates:
            updates['crop_id'] = (updates['crop_id'] or '').strip()
            _require_crop(conn, updates['crop_id'])
        if not updates and source_keys is None:
            return False
        if updates:
            set_clause = ', '.join('%s=?' % column for column in updates)
            conn.execute("UPDATE pest_entries SET %s WHERE id=?"
                         % set_clause, list(updates.values()) + [entry_id])
        if source_keys is not None:
            _replace_entry_sources(conn, entry_id, _require_source_keys(
                conn, _string_list(source_keys)))
        conn.commit()
    finally:
        conn.close()
    return True


def delete_pest_entry(entry_id):
    """删除一条条目。来源关联与实拍图由外键级联删除。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


def verify_pest_entry(entry_id, verifier):
    """标记已复核：写 is_verified=1 与 verified_by / verified_at（当前登录用户）。

    verified_at 走 SQLite 的 localtime，与库里其它时间列同一口径。
    """
    verifier = (verifier or '').strip()
    if not verifier:
        raise ValueError('复核人不能为空')
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE pest_entries SET is_verified = 1, verified_by = ?, "
            "verified_at = datetime('now','localtime') WHERE id = ?", (verifier, entry_id))
        updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return updated > 0


def get_overdue_pest_entries(days=REVIEW_STALE_DAYS, crop_id=None):
    """复核超期的条目：超过 days 天没再核的，以及从未复核的。

    口径与 farming.get_farming_overdue_tasks 一致：verified_at 距今天超过
    days 天算超期，为空的（从未复核）同样该核。按复核时间升序。
    """
    conn = get_connection()
    try:
        sql = ("SELECT e.*, c.name AS crop_name FROM pest_entries e "
               "JOIN pest_crops c ON c.id = e.crop_id "
               "WHERE e.verified_at = '' OR "
               "julianday('now', 'localtime') - julianday(e.verified_at) > ?")
        params = [days]
        if crop_id:
            sql += " AND e.crop_id = ?"
            params.append(crop_id)
        sql += " ORDER BY e.verified_at = '' DESC, e.verified_at"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


# ---- 实拍图（一条条目最多一张） ----

def set_pest_image(entry_id, **fields):
    """写入 / 覆盖某条条目的实拍图。缺 file 视为删除这张图的关联。"""
    conn = get_connection()
    try:
        if (fields.get('file') or '').strip() == '':
            conn.execute("DELETE FROM pest_images WHERE entry_id = ?", (entry_id,))
            conn.commit()
            return
        updates = _pick(fields, _IMAGE_WRITABLE)
        updates['entry_id'] = entry_id
        columns = ', '.join(updates)
        # entry_id 是主键，所以「改」与「建」是同一句：冲突即覆盖。
        conn.execute(
            "INSERT OR REPLACE INTO pest_images (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(updates))), list(updates.values()))
        conn.commit()
    finally:
        conn.close()


def delete_pest_image(entry_id):
    """摘掉某条条目的实拍图。返回是否真的删掉了行。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM pest_images WHERE entry_id = ?", (entry_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


# ---- 作物 ----

def _require_crop(conn, crop_id):
    row = conn.execute("SELECT id FROM pest_crops WHERE id = ?", (crop_id,)).fetchone()
    if row is None:
        raise ValueError('作物不存在：%s' % crop_id)


def create_pest_crop(crop_id, name, **fields):
    """新增一个速查作物，返回 crop_id（字符串主键由调用方给出）。"""
    crop_id = (crop_id or '').strip()
    name = (name or '').strip()
    if not crop_id:
        raise ValueError('作物 id 不能为空')
    if not name:
        raise ValueError('作物名称不能为空')
    values = _pick(fields, _CROP_WRITABLE)
    if 'name' in values:
        values['name'] = (values['name'] or '').strip()
    values.update({'id': crop_id, 'name': name})
    columns = ', '.join(values)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO pest_crops (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        conn.commit()
    finally:
        conn.close()
    return crop_id


def update_pest_crop(crop_id, **fields):
    updates = _pick(fields, _CROP_WRITABLE)
    if not updates:
        return False
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if updates.get('name') == '':
        raise ValueError('作物名称不能为空')
    set_clause = ', '.join('%s=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE pest_crops SET %s WHERE id=?"
                           % set_clause, list(updates.values()) + [crop_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_pest_crop(crop_id):
    """删除作物。条目、条目来源关联、实拍图由外键级联删除。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM pest_crops WHERE id = ?", (crop_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


# ---- 来源 ----

def create_pest_source(key, name, **fields):
    key = (key or '').strip()
    name = (name or '').strip()
    if not key:
        raise ValueError('来源 key 不能为空')
    if not name:
        raise ValueError('来源名称不能为空')
    values = _pick(fields, _SOURCE_WRITABLE)
    if 'name' in values:
        values['name'] = (values['name'] or '').strip()
    if values.get('name') == '':
        raise ValueError('来源名称不能为空')
    values.update({'key': key, 'name': name})
    columns = ', '.join(values)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO pest_sources (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        conn.commit()
    finally:
        conn.close()
    return key


def update_pest_source(key, **fields):
    updates = _pick(fields, _SOURCE_WRITABLE)
    if not updates:
        return False
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if updates.get('name') == '':
        raise ValueError('来源名称不能为空')
    set_clause = ', '.join('%s=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE pest_sources SET %s WHERE key=?"
                           % set_clause, list(updates.values()) + [key])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_pest_source(key):
    """删除来源。条目与它的关联由外键级联删除（pest_entry_sources 有 FK）。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM pest_sources WHERE key = ?", (key,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


def _string_list(value):
    """把入参规整成字符串列表：单个字符串包一层，None 给 []，其余元素转字符串。"""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]
