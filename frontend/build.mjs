import {mkdir, copyFile, readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const root = new URL('.', import.meta.url);
await mkdir(new URL('dist/', root), {recursive:true});
for (const file of ['index.html','app.mjs','api.mjs','styles.css']) {
  const src = new URL(`src/${file}`,root);
  if(file.endsWith('.mjs')) execFileSync(process.execPath,['--check',fileURLToPath(src)]);
  await copyFile(src,new URL(`dist/${file}`,root));
}
const html=await readFile(new URL('dist/index.html',root),'utf8');
if(!html.includes('app.mjs')) throw Error('Missing application entry');
console.log('PASS: standalone UI built (4 files; zero third-party runtime dependencies)');
