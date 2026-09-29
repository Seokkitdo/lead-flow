import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';

const roots = ['apps/web/src', 'apps/admin/src', 'packages/crm/src', 'packages/ui/src'];
const errors = [];
let checked = 0;
async function scan(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      await scan(path);
      continue;
    }
    if (!/\.(svelte|css)$/.test(path)) continue;
    const source = await readFile(path, 'utf8');
    checked++;
    source.split('\n').forEach((line, i) => {
      const fail = (message) => errors.push(`${relative('.', path)}:${i + 1} ${message}`);
      const font = line.match(/font-size:\s*([\d.]+)(px|rem)\b/);
      if (font) {
        const pixels = Number(font[1]) * (font[2] === 'rem' ? 16 : 1);
        if (pixels > 0 && pixels < 12) fail('텍스트 최소 크기는 12px(0.75rem)입니다.');
      }
      if (path === 'packages/ui/src/theme.css') return;
      if (/#[\da-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch)\s*\(/.test(line))
        fail('색상 리터럴 대신 theme.css의 의미 토큰을 사용하세요.');
      if (
        /\b(?:bg|text|border|ring|fill|stroke)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d/.test(
          line,
        )
      )
        fail('Tailwind 색상 팔레트 대신 의미 토큰을 사용하세요.');
      if (/\bstyle\s*=/.test(line)) fail('inline style 대신 공통 스타일/클래스를 사용하세요.');
      if (/\b(?:bg|text|border|ring)-\[/.test(line))
        fail('임의 Tailwind 값 대신 디자인 토큰을 사용하세요.');
    });
  }
}
for (const root of roots) await scan(root);
if (errors.length) {
  console.error(errors.join('\n'));
  process.exitCode = 1;
} else console.log(`Design system: ${checked} files passed.`);
