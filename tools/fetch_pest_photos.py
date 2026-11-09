# -*- coding: utf-8 -*-
"""按学名从 iNaturalist 取「研究级观察」的授权照片，补进病虫害速查的实拍图。

用法（仓库根，需要 py -3.9 且能访问 api.inaturalist.org）：

    py -3.9 tools/fetch_pest_photos.py --review
        只查询候选，把结果写进 _pest_photos.json，不下载任何文件。
    py -3.9 tools/fetch_pest_photos.py --apply --only-pests
        只给「虫害」类条目下载（虫体/为害状照片，误用风险低），病害类只留候选。
    py -3.9 tools/fetch_pest_photos.py --apply --ids citrus_rust_mite,tea_weevil
        指定条目下载，供人工挑选后补拍。

三条硬约束，与 db_domains/pest.py 的口径一致：

  1. **只要研究级观察**（quality_grade=research）：意味着已有至少两位社区鉴定者
     认同到该物种，比自己按关键词搜图靠谱。
  2. **只要可再分发的授权**：CC0 / CC BY / CC BY-NC。CC BY-NC-ND、全版权一律跳过。
     下载后把署名、授权、观察编号一并写进 pest_images，缺一项就不入库。
  3. **不下载就不知道是不是虫**：脚本按学名取，但照片里拍的可能只是叶片病斑，
     所以病害类默认不自动入库，只产出候选供人工过目（--review 的 CSV）。

输出：
  output/pest-photos/candidates.json   下载结果与元数据，供生成迁移用
  output/pest-photos/candidates.csv    候选清单，人工复核用（含观察链接）
"""

from __future__ import print_function

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import sys

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, 'data', 'yuexiang.db')
IMAGE_DIR = os.path.join(REPO_ROOT, 'images', 'pest')
MANIFEST = os.path.join(REPO_ROOT, 'output', 'pest-photos', 'candidates.json')
REVIEW_CSV = os.path.join(REPO_ROOT, 'output', 'pest-photos', 'candidates.csv')

API = 'https://api.inaturalist.org/v1'
UA = {'User-Agent': 'yuexiang-zhijiang-content/1.0 (education project)'}

# 允许的授权，与库里现有 18 张一致。ND/SA 不在此列。
LICENSES = 'cc0,cc-by,cc-by-nc'
LICENSE_LABEL = {
    'cc0': 'CC0',
    'cc-by': 'CC BY',
    'cc-by-nc': 'CC BY-NC',
}

BINOMIAL = re.compile(r'([A-Z][a-z]{2,})\s+([a-z][a-z\-]{2,})')
MAX_BYTES = 4 * 1024 * 1024


def latin_name(text):
    """从「荔枝瘿螨（Aceria litchii）」里取第一个拉丁双名。取不到返回 None。"""
    match = BINOMIAL.search(text or '')
    return '%s %s' % (match.group(1), match.group(2)) if match else None


def missing_entries(only_ids=None):
    conn = sqlite3.connect(DATA)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT e.id, e.disease, e.kind, e.pathogen, c.name AS crop_name "
        "FROM pest_entries e JOIN pest_crops c ON c.id = e.crop_id "
        "LEFT JOIN pest_images i ON i.entry_id = e.id "
        "WHERE i.entry_id IS NULL ORDER BY c.sort_order, e.sort_order").fetchall()
    conn.close()
    out = []
    for row in rows:
        if only_ids and row['id'] not in only_ids:
            continue
        out.append(dict(row))
    return out


def find_taxon(name):
    """按学名找分类单元。只接受名字完全一致的物种/亚种。"""
    response = requests.get('%s/taxa' % API,
                            params={'q': name, 'rank': 'species,subspecies'},
                            headers=UA, timeout=25)
    response.raise_for_status()
    for item in response.json().get('results', []):
        if (item.get('name') or '').lower() == name.lower():
            return item
    return None


def pick_observation(taxon_id):
    """取一条研究级、有授权照片的观察。按收藏数排序，尽量选清晰且被认可的。"""
    response = requests.get('%s/observations' % API, params={
        'taxon_id': taxon_id,
        'quality_grade': 'research',
        'photo_license': LICENSES,
        'photos': 'true',
        'order_by': 'votes',
        'per_page': 5,
    }, headers=UA, timeout=30)
    response.raise_for_status()
    for obs in response.json().get('results', []):
        photos = [p for p in obs.get('photos', [])
                  if (p.get('license_code') or '').lower() in LICENSE_LABEL]
        if not photos:
            continue
        photo = photos[0]
        # square 缩略图换成 large（最长边 1024），与既有 18 张同一口径。
        url = (photo.get('url') or '').replace('/square.', '/large.')
        if not url:
            continue
        user = obs.get('user') or {}
        return {
            'photo_url': url,
            'license_code': photo['license_code'].lower(),
            'credit': user.get('name') or user.get('login') or '',
            'observation_url': 'https://www.inaturalist.org/observations/%s' % obs.get('id'),
            'shot_date': obs.get('observed_on') or '',
            'place': (obs.get('place_guess') or '')[:60],
            'taxon_name': (obs.get('taxon') or {}).get('name') or '',
        }
    return None


def download(url, target):
    response = requests.get(url, headers=UA, timeout=60)
    response.raise_for_status()
    body = response.content
    if len(body) > MAX_BYTES:
        raise ValueError('图片超过 4MB')
    if not body[:2] == b'\xff\xd8' and body[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('不是 JPEG/PNG')
    with io.open(target, 'wb') as handle:
        handle.write(body)
    return len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description='从 iNaturalist 补病虫害实拍图')
    parser.add_argument('--review', action='store_true', help='只查候选，不下载')
    parser.add_argument('--apply', action='store_true', help='下载图片并写清单')
    parser.add_argument('--only-pests', action='store_true',
                        help='--apply 时只处理 kind=pest 的条目')
    parser.add_argument('--ids', default='', help='只处理这些条目 id，逗号分隔')
    args = parser.parse_args(argv)

    if not args.review and not args.apply:
        parser.error('需要 --review 或 --apply')

    only_ids = [x.strip() for x in args.ids.split(',') if x.strip()]
    entries = missing_entries(only_ids or None)
    results = []
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)

    for entry in entries:
        name = latin_name(entry['pathogen'])
        record = {
            'entry_id': entry['id'],
            'disease': entry['disease'],
            'crop_name': entry['crop_name'],
            'kind': entry['kind'],
            'latin': name or '',
            'status': '',
        }
        if not name:
            record['status'] = 'no-latin'
            results.append(record)
            continue
        try:
            taxon = find_taxon(name)
        except Exception as exc:
            record['status'] = 'taxa-error:%s' % type(exc).__name__
            results.append(record)
            continue
        if not taxon:
            record['status'] = 'no-taxon'
            results.append(record)
            continue

        record['taxon_id'] = taxon['id']
        record['observations'] = taxon.get('observations_count')
        try:
            obs = pick_observation(taxon['id'])
        except Exception as exc:
            record['status'] = 'obs-error:%s' % type(exc).__name__
            results.append(record)
            continue
        if not obs:
            record['status'] = 'no-licensed-photo'
            results.append(record)
            continue

        record.update(obs)
        record['status'] = 'candidate'
        if args.apply:
            want = entry['kind'] == 'pest' or not args.only_pests
            if not want:
                record['status'] = 'candidate-skipped'
            else:
                target = os.path.join(IMAGE_DIR, '%s.jpg' % entry['id'])
                try:
                    size = download(obs['photo_url'], target)
                    record['status'] = 'downloaded'
                    record['bytes'] = size
                    record['file'] = '/images/pest/%s.jpg' % entry['id']
                except Exception as exc:
                    record['status'] = 'download-error:%s' % type(exc).__name__
                    if os.path.exists(target):
                        os.remove(target)
        results.append(record)

    with io.open(MANIFEST, 'w', encoding='utf-8') as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
        handle.write('\n')

    with io.open(REVIEW_CSV, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['条目', '病虫名', '作物', '类型', '学名', '状态',
                         '授权', '摄影者', '拍摄日期', '地点', '观察链接', '图片地址'])
        for item in results:
            writer.writerow([
                item['entry_id'], item['disease'], item['crop_name'],
                '虫害' if item['kind'] == 'pest' else '病害',
                item.get('latin', ''), item['status'],
                LICENSE_LABEL.get(item.get('license_code', ''), ''),
                item.get('credit', ''), item.get('shot_date', ''),
                item.get('place', ''), item.get('observation_url', ''),
                item.get('photo_url', ''),
            ])

    counts = {}
    for item in results:
        key = item['status'].split(':')[0]
        counts[key] = counts.get(key, 0) + 1
    print('条目 %d：%s' % (len(results), ', '.join(
        '%s=%d' % (k, v) for k, v in sorted(counts.items()))))
    print('清单：%s' % MANIFEST)
    print('复核表：%s' % REVIEW_CSV)
    return 0


if __name__ == '__main__':
    sys.exit(main())
