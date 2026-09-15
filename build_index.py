#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py — 将 data.json 注入 template.html 的 /*__DATA__*/ 占位符，
生成自包含、零依赖的 index.html（可直接 GitHub Pages 发布）。

用法：python build_index.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
    with open(os.path.join(HERE, 'data.json'), encoding='utf-8') as f:
        data = json.load(f)

    if '/*__DATA__*/' not in tpl:
        raise SystemExit('ERROR: template.html 中未找到 /*__DATA__*/ 占位符')

    payload = 'var DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';'
    out = tpl.replace('/*__DATA__*/', payload)

    out_path = os.path.join(HERE, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(out)

    m = data['meta']
    t = m.get('totals', {})
    print(f"OK 生成 index.html ({os.path.getsize(out_path):,} bytes) | "
          f"战役={t.get('projects')} 规划={t.get('alloc')} 已开展={t.get('done')} 已核销={t.get('settled')}")


if __name__ == '__main__':
    main()
