#!/usr/bin/env node
/**
 * 通过 GitHub Contents API 上传文件（绕开 git 协议 / 代理 502 问题）
 * 用法: node _upload_via_api.js <owner> <repo> <branch> <localDir> [相对路径...]
 */
const fs = require('fs');
const path = require('path');
const cp = require('child_process');

const GH = 'C:/Program Files/GitHub CLI/gh.exe';
const [, , owner, repo, branch, localDir, ...explicit] = process.argv;

const SKIP_DIRS = new Set(['.git', '_qa', 'node_modules']);
const SKIP_FILES = new Set(['.gitignore']);

function walk(dir, base = '') {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = base ? base + '/' + e.name : e.name;
    if (e.isDirectory()) {
      if (SKIP_DIRS.has(e.name)) continue;
      out.push(...walk(path.join(dir, e.name), rel));
    } else {
      out.push(rel);
    }
  }
  return out;
}

function gh(args, input) {
  const opts = { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] };
  if (input !== undefined) opts.input = input;
  return cp.execFileSync(GH, args, opts);
}

function upload(relPath) {
  const abs = path.join(localDir, relPath);
  const content = fs.readFileSync(abs).toString('base64');
  const body = JSON.stringify({
    message: `add: ${relPath}`,
    content,
    branch,
  });
  const args = ['api', '-X', 'PUT',
    `repos/${owner}/${repo}/contents/${encodeURIComponent(relPath).replace(/%2F/g, '/')}`,
    '--input', '-'];
  try {
    gh(args, body);
    return { ok: true };
  } catch (e) {
    const msg = ((e.stdout || '') + (e.stderr || '')).trim();
    return { ok: false, msg };
  }
}

const files = explicit.length ? explicit : walk(localDir).filter(f => !SKIP_FILES.has(f));
console.log(`准备上传 ${files.length} 个文件 → ${owner}/${repo}@${branch}\n`);

let ok = 0, fail = 0;
for (const f of files) {
  const r = upload(f);
  if (r.ok) { console.log('  ✅', f); ok++; }
  else { console.log('  ❌', f, '\n     ', r.msg.slice(0, 300)); fail++; }
}
console.log(`\n完成：成功 ${ok} / 失败 ${fail}`);
