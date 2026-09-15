#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_data.py — 解析 raw/*.csv（各战役 sheet 导出）→ data.json

CSV 表头含引号内换行，必须用 csv.reader 正确读取（跨行引号）。
每张 sheet 可能包含多个「区块」（如 美乐肺辅=区域赛+省级赛；53学苑=大咖线上会+MDT+大咖行）。
按「第二列 == 分配场次」识别区块表头，向下取区域行，遇到空行或下一个表头前结束。
"""
import csv, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')

REGIONS = ['东部区域', '南部区域', '东南区域', '西部区域', '北部区域', '西北区域', '华北区域', '湘桂区域']
REGION_ALIAS = {
    '东部区域': '东部区域', '东部': '东部区域',
    '南部区域': '南部区域', '南部': '南部区域',
    '东南区域': '东南区域', '东南': '东南区域',
    '西部区域': '西部区域', '西部': '西部区域',   # 表中「西部区域」= 项目总览「中部区域」口径
    '北部区域': '北部区域', '北部': '北部区域', '北区': '北部区域',
    '中部区域': '西部区域', '中部': '西部区域',   # 兼容总览表叫法
    '西北区域': '西北区域', '西北': '西北区域',
    '华北区域': '华北区域', '华北': '华北区域',
    '湘桂区域': '湘桂区域', '湘桂': '湘桂区域',
}

# 文件 -> (组名, 默认战役名, 肺肿线)
# 「项目总览」共 13 个项目：早肺 5 个 / 晚肺 7 个 / 未分类 1 个（CACA基层行）
FILE_MAP = [
    ('sri7pl_美乐肺辅.csv',               '美乐肺辅',   '美乐肺辅',              '早肺'),
    ('df4vyl_胸外老友线上会.csv',          '胸外老友',   '胸外老友线上会',        '早肺'),
    ('3v11ux_肺凡新生-患教项目-线上.csv',   '肺凡新生',   '肺凡新生-患教项目-线上', '早肺'),
    ('l9rlwe_云端ARTS2.0.csv',            '云端ARTS2.0', '云端ARTS2.0（停止）',   '早肺'),
    ('i1re8u_靶化线下会.csv',              '靶化上市会', '靶化上市会（地区级线下）',  '晚肺'),
    ('udqfdo_靶化线上会.csv',              '靶化上市会', '靶化上市会-线上会',      '晚肺'),
    ('tqqzde_肺凡新生-患教项目-线下.csv',   '肺凡新生',   '肺凡新生-患教项目-线下', '晚肺'),
    ('tvc48s_肺凡新生-大咖直播-线上.csv',   '肺凡新生',   '肺凡新生-大咖直播-线上', '晚肺'),
    ('gekn8l_53学苑.csv',                 '53学苑',     '53学苑',                '晚肺'),
    ('123v6y_CACA基层行.csv',              'CACA基层行', 'CACA基层行',            '晚肺'),
]

# 战役名归一（对齐「项目总览」的项目名，并修正原表错别字）
NAME_FIX = {
    '美乐肺辅区域赛': '美乐肺辅-区域赛',
    '美乐肺辅省级赛': '美乐肺辅-省级赛',
    '美乐肺腑省级赛': '美乐肺辅-省级赛',
    '靶化线下会': '靶化上市会（地区级线下）',
    '靶化线上会': '靶化上市会-线上会',
    '肺凡新生-患教项目-线上-早肺': '肺凡新生-患教项目（线上）',
    '肺凡新生-患教项目-线下-晚肺': '肺凡新生-线下患教项目',
    '肺凡新生-大咖直播-线上-晚肺': '肺凡新生-大咖直播',
    '云端ARTS2.0区域': '云端ARTS2.0（停止）',
    'CACA基层行': 'CACA基层行',
}


def num(v):
    if v is None: return None
    s = str(v).strip().replace(',', '').replace('%', '')
    if s in ('', '-', '—', '#DIV/0!', '#VALUE!', '#REF!', '#N/A'): return None
    try:
        return float(s)
    except ValueError:
        return None


def norm_region(s):
    return REGION_ALIAS.get((s or '').strip(), None)


def clean_title(t, fallback):
    t = (t or '').strip().lstrip('\ufeff')
    if not t or t.startswith('填表') or t.startswith('C列'):
        return fallback
    return NAME_FIX.get(t, t)


def parse_block(rows, hi, fallback_title):
    header = rows[hi]
    def col(*keys):
        for i, h in enumerate(header):
            hh = (h or '').replace('\n', '')
            for k in keys:
                if k in hh: return i
        return None

    c_alloc  = col('分配场次')
    c_done   = col('已开展场次（项目开始')
    if c_done is None: c_done = col('已开展场次')
    c_plan   = col('已确定未开场次（7.1以后所有')
    if c_plan is None: c_plan = col('已确定未开场次')
    c_cancel = col('确定后取消场次')
    c_sell   = col('已完成核销场次')
    c_conf   = col('确定场次（包含已开）')
    c_rp     = col('规划总进度')
    c_re     = col('执行总进度')
    c_rs     = col('核销进度')
    c_nol, c_yol, c_rol = col('NOL'), col('YOL'), col('ROL')
    c_note   = col('备注')

    def g(r, i):
        return r[i] if (i is not None and i < len(r)) else ''

    out, total = [], None
    for r in rows[hi + 1:]:
        if not r or not any((x or '').strip() for x in r):
            break  # 空行 → 区块结束
        first = (r[0] or '').strip()
        second = (r[1] or '').strip() if len(r) > 1 else ''
        if second == '分配场次' or first in ('填表说明',):
            break  # 下一个表头 → 区块结束
        row = {
            'region': norm_region(first),
            'raw': first,
            'alloc': num(g(r, c_alloc)),
            'done': num(g(r, c_done)),
            'planOpen': num(g(r, c_plan)),
            'cancel': num(g(r, c_cancel)),
            'settled': num(g(r, c_sell)),
            'confirmed': num(g(r, c_conf)),
            'planRate': num(g(r, c_rp)),
            'execRate': num(g(r, c_re)),
            'settleRate': num(g(r, c_rs)),
            'nol': num(g(r, c_nol)),
            'yol': num(g(r, c_yol)),
            'rol': num(g(r, c_rol)),
            'note': (g(r, c_note) or '').strip(),
        }
        if first in ('合计', '总计'):
            total = row
        elif row['region']:
            out.append(row)
    return {'title': clean_title(header[0] if header else '', fallback_title),
            'rows': out, 'total': total}


def parse_file(path, fallback_title):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    blocks, i = [], 0
    while i < len(rows):
        r = rows[i]
        second = (r[1] or '').strip() if len(r) > 1 else ''
        if second == '分配场次':
            blk = parse_block(rows, i, fallback_title)
            if blk['rows'] or blk['total']:
                blocks.append(blk)
        i += 1
    return blocks


# 项目展示顺序（严格对齐「项目总览」sheet 的行序）
ORDER = [
    '美乐肺辅-区域赛',
    '美乐肺辅-省级赛',
    '胸外老友线上会',
    '肺凡新生-患教项目（线上）',
    '云端ARTS2.0（停止）',
    '靶化上市会（地区级线下）',
    '靶化上市会-线上会',
    '肺凡新生-线下患教项目',
    '肺凡新生-大咖直播',
    '53学苑-大咖线上会',
    '53学苑-MDT',
    '53学苑-大咖行',
    'CACA基层行',
]


def main():
    items = []
    for fname, group, cname, line in FILE_MAP:
        p = os.path.join(RAW, fname)
        if not os.path.exists(p):
            print('MISSING', fname); continue
        for blk in parse_file(p, cname):
            t = blk['total'] or {}
            rows = blk['rows']
            # 若合计行缺失，用区域行汇总
            def agg(k):
                vals = [r[k] for r in rows if r[k] is not None]
                return sum(vals) if vals else None
            alloc = t.get('alloc');  alloc = alloc if alloc is not None else agg('alloc')
            done  = t.get('done');   done  = done  if done  is not None else agg('done')
            sell  = t.get('settled');sell  = sell  if sell  is not None else agg('settled')
            conf  = t.get('confirmed'); conf = conf if conf is not None else agg('confirmed')
            planO = t.get('planOpen'); planO = planO if planO is not None else agg('planOpen')
            cancel= t.get('cancel');  cancel= cancel if cancel is not None else agg('cancel')
            name = NAME_FIX.get(blk['title'], blk['title'])
            # 计算进度（若原表缺失）
            pr = t.get('planRate')
            if pr is None and conf and alloc: pr = round(conf / alloc * 100, 0)
            er = t.get('execRate')
            if er is None and done and alloc: er = round(done / alloc * 100, 0)
            sr = t.get('settleRate')
            if sr is None and sell is not None and done: sr = round(sell / done * 100, 0) if done else None
            items.append({
                'id': re.sub(r'[^\w\u4e00-\u9fa5]+', '-', f'{group}-{name}').strip('-'),
                'name': name,
                'group': group,
                'line': line,
                'alloc': alloc, 'done': done, 'settled': sell, 'confirmed': conf,
                'planOpen': planO, 'cancel': cancel,
                'planRate': pr, 'execRate': er, 'settleRate': sr,
                'nol': t.get('nol') if t.get('nol') is not None else agg('nol'),
                'yol': t.get('yol') if t.get('yol') is not None else agg('yol'),
                'rol': t.get('rol') if t.get('rol') is not None else agg('rol'),
                'rows': rows,
            })

    if not items:
        raise SystemExit('ERROR: 未解析到任何战役，请检查 raw/ 目录')

    # 按「项目总览」顺序排序（不在 ORDER 中的排最后）
    def order_key(it):
        try:
            return ORDER.index(it['name'])
        except ValueError:
            return len(ORDER) + 1
    items.sort(key=order_key)

    # 汇总
    tot_alloc = sum(i['alloc'] for i in items if i['alloc'])
    tot_done  = sum(i['done'] for i in items if i['done'])
    tot_sell  = sum(i['settled'] for i in items if i['settled'])
    data = {
        'meta': {
            'updated': '2026-09-15',
            'source': '全国配套项目执行追踪群-H2',
            'regions': REGIONS,
            'lines': ['早肺', '晚肺'],
            'totals': {
                'alloc': tot_alloc, 'done': tot_done, 'settled': tot_sell,
                'projects': len(items), 'regions': len(REGIONS),
            },
        },
        'items': items,
    }
    out = os.path.join(HERE, 'data.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'OK items={len(items)} alloc={tot_alloc:.0f} done={tot_done:.0f} settled={tot_sell:.0f} -> {out}')
    for it in items:
        print(f"   {it['line']:4s} | {it['name']:24s} | alloc={it['alloc']} done={it['done']} settled={it['settled']} plan%={it['planRate']} rows={len(it['rows'])}")
    # 校验：按区域聚合 vs 按项目合计
    agg_done = sum(r['done'] for it in items for r in it['rows'] if r['done'] is not None)
    ok = abs(agg_done - tot_done) < 0.5
    print(f"校验：按区域聚合 done={agg_done:.0f} vs 按项目合计 done={tot_done:.0f} -> {'✅ 一致' if ok else '❌ 不一致'}")


if __name__ == '__main__':
    main()
