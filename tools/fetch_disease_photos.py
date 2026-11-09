# -*- coding: utf-8 -*-
"""病害症状图的候选抓取：按学名多取几帧，供人工筛选。

与 tools/fetch_pest_photos.py 的差别：

  · 虫害照只要认对虫即可，一条足够；病害要看「症状」，同一分类单元下既有田间病斑照，
    也有培养皿、镜检照，所以这里对每条取多帧候选，由人过目。
  · 候选只落到 output/pest-photos/candidates/ 供复核，**不写 images/pest，也不进库**。

用法：
    py -3.9 tools/fetch_disease_photos.py --per 3
    py -3.9 tools/fetch_disease_photos.py --per 2 --ids rice_blast,citrus_canker
"""

from __future__ import print_function

import argparse
import csv
import io
import os
import re
import sqlite3
import sys

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, 'data', 'yuexiang.db')
OUT_DIR = os.path.join(REPO_ROOT, 'output', 'pest-photos', 'candidates')
CSV_PATH = os.path.join(REPO_ROOT, 'output', 'pest-photos', 'disease-candidates.csv')
API = 'https://api.inaturalist.org/v1'
UA = {'User-Agent': 'yuexiang-zhijiang-content/1.0 (education project)'}
LICENSES = 'cc0,cc-by,cc-by-nc'
LICENSE_LABEL = {'cc0': 'CC0', 'cc-by': 'CC BY', 'cc-by-nc': 'CC BY-NC'}

# 常用异名与有性型名。iNat 一般跟最新分类，中文资料里的名字常对不上。
ALIASES = {
    'Magnaporthe oryzae': ['Pyricularia oryzae'],
    'Ustilaginoidea virens': ['Villosiclava virens'],
    'Sphaceloma fawcettii': ['Elsinoe fawcettii', 'Elsinoë fawcettii'],
    'Guignardia musae': ['Phyllosticta musae'],
    'Guignardia camelliae': ['Phyllosticta camelliae'],
    'Rhizoctonia solani': ['Thanatephorus cucumeris'],
    'Candidatus Liberibacter asiaticus': ['Liberibacter asiaticus'],
    'Aeromonas punctata': ['Aeromonas caviae'],
}

BINOMIAL = re.compile(r'([A-Z][a-z]{2,})\s+([a-z][a-z\-]{2,})')


def binomial(text):
    match = BINOMIAL.search(text or '')
    return '%s %s' % (match.group(1), match.group(2)) if match else None


def disease_entries(only_ids=None):
    conn = sqlite3.connect(DATA)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT e.id, e.disease, e.pathogen, c.name AS crop_name "
        "FROM pest_entries e JOIN pest_crops c ON c.id = e.crop_id "
        "LEFT JOIN pest_images i ON i.entry_id = e.id "
        "WHERE i.entry_id IS NULL AND e.kind = 'disease' "
        "ORDER BY c.sort_order, e.sort_order").fetchall()
    conn.close()
    out = [dict(row) for row in rows]
    if only_ids:
        out = [row for row in out if row['id'] in only_ids]
    return out


def find_taxon(name):
    """名字完全一致才算命中；异名逐个再试。"""
    for candidate in [name] + ALIASES.get(name, []):
        try:
            response = requests.get('%s/taxa' % API,
                                    params={'q': candidate, 'rank': 'species,subspecies'},
                                    headers=UA, timeout=25)
            response.raise_for_status()
        except Exception:
            continue
        for item in response.json().get('results', []):
            if (item.get('name') or '').lower() == candidate.lower():
                return item, candidate
    return None, name


def observations(taxon_id, per_page=8):
    response = requests.get('%s/observations' % API, params={
        'taxon_id': taxon_id,
        'quality_grade': 'research',
        'photo_license': LICENSES,
        'photos': 'true',
        'order_by': 'votes',
        'per_page': per_page,
    }, headers=UA, timeout=30)
    response.raise_for_status()
    return response.json().get('results', [])


def download(url, target, width=800):
    url = url.replace('/square.', '/large.')
    response = requests.get(url, headers=UA, timeout=60)
    response.raise_for_status()
    body = response.content
    if len(body) < 4000:
        raise ValueError('文件过小')
    with io.open(target, 'wb') as handle:
        handle.write(body)
    return len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description='抓病害症状图候选（不自动入库）')
    parser.add_argument('--per', type=int, default=3, help='每条最多取几帧候选')
    parser.add_argument('--ids', default='', help='只处理这些条目，逗号分隔')
    parser.add_argument('--append', action='store_true',
                        help='追加到既有清单（分批跑时用，避免整表被覆盖）')
    args = parser.parse_args(argv)

    only = [x.strip() for x in args.ids.split(',') if x.strip()]
    entries = disease_entries(only or None)
    os.makedirs(OUT_DIR, exist_ok=True)

    rows = []
    for entry in entries:
        name = binomial(entry['pathogen'])
        if not name:
            rows.append({'id': entry['id'], 'disease': entry['disease'],
                         'crop': entry['crop_name'], 'latin': '', 'status': 'no-latin'})
            continue
        taxon, used = find_taxon(name)
        if not taxon:
            rows.append({'id': entry['id'], 'disease': entry['disease'],
                         'crop': entry['crop_name'], 'latin': name,
                         'status': 'no-taxon'})
            continue
        try:
            obs_list = observations(taxon['id'])
        except Exception as exc:
            rows.append({'id': entry['id'], 'disease': entry['disease'],
                         'crop': entry['crop_name'], 'latin': used,
                         'status': 'obs-error:%s' % type(exc).__name__})
            continue

        taken = 0
        for obs in obs_list:
            if taken >= args.per:
                break
            photos = [p for p in obs.get('photos', [])
                      if (p.get('license_code') or '').lower() in LICENSE_LABEL]
            if not photos:
                continue
            photo = photos[0]
            taken += 1
            filename = '%s-%d.jpg' % (entry['id'], taken)
            target = os.path.join(OUT_DIR, filename)
            record = {
                'id': entry['id'],
                'disease': entry['disease'],
                'crop': entry['crop_name'],
                'latin': used,
                'obs_id': obs.get('id'),
                'obs_url': 'https://www.inaturalist.org/observations/%s' % obs.get('id'),
                'license': LICENSE_LABEL[photo['license_code'].lower()],
                'credit': (obs.get('user') or {}).get('name')
                          or (obs.get('user') or {}).get('login') or '',
                'shot_date': obs.get('observed_on') or '',
                'place': (obs.get('place_guess') or '')[:50],
                'local': filename,
                'status': 'candidate',
            }
            try:
                record['bytes'] = download(photo.get('url') or '', target)
            except Exception as exc:
                record['status'] = 'download-error:%s' % type(exc).__name__
                if os.path.exists(target):
                    os.remove(target)
            rows.append(record)

        if taken == 0:
            rows.append({'id': entry['id'], 'disease': entry['disease'],
                         'crop': entry['crop_name'], 'latin': used,
                         'status': 'no-licensed-photo'})

    append = args.append and os.path.exists(CSV_PATH)
    with io.open(CSV_PATH, 'a' if append else 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        if not append:
            writer.writerow(['条目', '病害', '作物', '学名', '候选文件', '授权',
                             '摄影者', '拍摄日期', '地点', '观察链接', '状态'])
        for row in rows:
            writer.writerow([row['id'], row['disease'], row['crop'],
                             row.get('latin', ''), row.get('local', ''),
                             row.get('license', ''), row.get('credit', ''),
                             row.get('shot_date', ''), row.get('place', ''),
                             row.get('obs_url', ''), row['status']])

    ok = len([r for r in rows if r.get('status') == 'candidate'])
    print('条目 %d，候选 %d 帧，清单 %s' % (len(entries), ok, CSV_PATH))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        with io.open(os.path.join(REPO_ROOT, 'output', 'pest-photos', '_error.txt'),
                     'w', encoding='utf-8') as handle:
            handle.write(traceback.format_exc())
        raise
