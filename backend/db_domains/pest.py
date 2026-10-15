# -*- coding: utf-8 -*-
"""病虫害域的数据访问层：作物、条目、来源、条目与来源多对多、实拍图。

T07 把读取从代码常量切到 T04 建的五张 pest 表。内容由
migrations/0001_content_to_db.py 灌入，本模块只负责读，不写。

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

# 作物列表的排序键：与切换前 PEST_CROP_ORDER 一致（迁移脚本按它写 sort_order）
_CROPS_SQL = "SELECT * FROM pest_crops ORDER BY sort_order, id"

# 条目列表：JOIN 作物层把作物名与图标一起取回来（切换前的 crop_name / crop_icon
# 就是从作物层取的），排序先作物序、再条目序，与切换前 iter_pest_entries() 一致，
# 这样不带参数取全量时，条目顺序逐字节等价。
_ENTRIES_SQL = """SELECT e.id, e.crop_id, e.disease, e.alias, e.kind, e.pathogen,
                          e.part, e.severity, e.symptoms, e.occurrence, e.treatment,
                          e.prevention, e.registered, e.chem_table, e.safety_note,
                          e.is_verified, c.name AS crop_name, c.icon AS crop_icon
                     FROM pest_entries e
                     JOIN pest_crops c ON c.id = e.crop_id
                    WHERE (? IS NULL OR e.crop_id = ?)
                 ORDER BY c.sort_order, e.sort_order, e.id"""


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
    """按 id 取单条条目（含 sources 与 image），不存在返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM pest_entries WHERE id = ?",
                           (entry_id,)).fetchone()
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
