import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {routes,escapeHTML,can,actionLabel} from '../src/api.mjs';
test('Untrusted evidence and AI strings are escaped',()=>{assert.equal(escapeHTML('<img onerror="x">&'), '&lt;img onerror=&quot;x&quot;&gt;&amp;');});
test('Role capabilities preserve separation',()=>{for(const r of ['admin','viewer','analyst']) assert.equal(can(r,'approve'),false);assert.equal(can('operator','approve'),true);assert.equal(can('viewer','investigate'),false);assert.equal(can('admin','propose'),false);});
test('Simulation is explicitly labeled',()=>{assert.match(actionLabel({dry_run:true}),/DRY RUN.*no firewall or endpoint changed/);});
test('Every UI API route exists in exported backend contract',async()=>{const api=JSON.parse(await readFile(new URL('../../docs/openapi.json',import.meta.url),'utf8'));for(const path of Object.values(routes))assert.ok(api.paths[path],path);});
test('No browser service credential storage or unsafe DOM sink',async()=>{const app=await readFile(new URL('../src/app.mjs',import.meta.url),'utf8');assert.doesNotMatch(app,/localStorage|sessionStorage|eval\(|document\.write|Authorization.*Bearer/);assert.match(app,/Citation validation/);});
