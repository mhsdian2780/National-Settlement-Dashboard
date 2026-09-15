#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_sheets.py — 从腾讯文档「全国配套项目执行追踪群-H2」导出各战役 sheet 的 CSV。

表结构（每张战役 sheet 通用）：
  第0行 填表说明 / 第1行 列包含说明 / 第2行 真实表头 / 第3..N行 区域明细 / 末行 合计
  列：A区域 B分配场次 C已开展 D已开展(当月) E已确定未开 F已确定未开(当月)
      G确定后取消 H已完成核销 I确定场次(含已开) J规划总进度 K执行总进度 L核销进度
      M/N/O 覆盖人数(NOL/YOL/ROL) P备注

用法：python export_sheets.py
"""
import subprocess, json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))

# 自动定位运行环境（兼容不同电脑的用户名 / 不同版本的 python 与插件目录）
_HOME = os.path.expanduser('~')
_WB = os.path.join(_HOME, '.workbuddy')


def _find_python():
    """优先用 WorkBuddy 自带 python，其次回落到系统 python。"""
    base = os.path.join(_WB, 'binaries', 'python', 'versions')
    if os.path.isdir(base):
        for ver in sorted(os.listdir(base), reverse=True):
            exe = os.path.join(base, ver, 'python.exe')
            if os.path.isfile(exe):
                return exe
    return sys.executable


def _find_doc_py():
    """在插件缓存里找任意版本的 tencent-docs 桥接脚本。"""
    root = os.path.join(_WB, 'plugins', 'cache', 'workbuddy-builtin', 'tencent-docs-plugin')
    if not os.path.isdir(root):
        return None
    cands = []
    for dirpath, _, filenames in os.walk(root):
        if 'tencentdocs.py' in filenames and os.path.basename(dirpath) == 'tencent-docs':
            cands.append(os.path.join(dirpath, 'tencentdocs.py'))
    return sorted(cands)[-1] if cands else None


PY_EXE = _find_python()
DOC_PY = _find_doc_py()
if not DOC_PY:
    raise SystemExit('ERROR: 未找到腾讯文档桥接脚本 tencentdocs.py，请确认 tencent-docs 插件已安装')

FILE_ID = 'IPItsCBmNiMC'

# sheet_id -> 中文名（用于生成 raw/ 文件名）
SHEETS = [
    ('BB08J2', '项目总览'),
    ('sri7pl', '美乐肺辅'),
    ('df4vyl', '胸外老友线上会'),
    ('3v11ux', '肺凡新生-患教项目-线上'),
    ('tqqzde', '肺凡新生-患教项目-线下'),
    ('tvc48s', '肺凡新生-大咖直播-线上'),
    ('i1re8u', '靶化线下会'),
    ('udqfdo', '靶化线上会'),
    ('gekn8l', '53学苑'),
    ('l9rlwe', '云端ARTS2.0'),        # 该 sheet 在文档中为隐藏状态，但需统计（项目已停止）
    ('123v6y', 'CACA基层行'),
]


def call(sheet_id, start_row, end_row, start_col=0, end_col=16):
    args = json.dumps({
        'file_id': FILE_ID, 'sheet_id': sheet_id,
        'start_row': start_row, 'start_col': start_col,
        'end_row': end_row, 'end_col': end_col,
        'return_csv': True
    }, ensure_ascii=False)
    r = subprocess.run([PY_EXE, DOC_PY, 'tdoc_call', 'sheet-mcp', 'get_cell_data', args],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print('STDERR:', r.stderr[:2000]); return None
    try:
        outer = json.loads(r.stdout)
        text = outer['result']['content'][0]['text']
        return json.loads(text).get('csv_data', '')
    except Exception as e:
        print('parse failed:', e, r.stdout[:500]); return None


MAX_ROW = 60  # 足够覆盖 53学苑 三个子战役区块


def main():
    outdir = os.path.join(HERE, 'raw')
    os.makedirs(outdir, exist_ok=True)
    for sid, name in SHEETS:
        csv_data = call(sid, 0, MAX_ROW, 0, 16)
        if csv_data is None:
            print(f'FAIL {name}')
            continue
        path = os.path.join(outdir, f'{sid}_{name}.csv')
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(csv_data)
        print(f'OK {name}: {csv_data.count(chr(10))} lines')


if __name__ == '__main__':
    main()
