// Verify backend HTML output in real browsers; no platform frontend is required.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const require = createRequire(new URL('../../platform-web/package.json', import.meta.url));
const { chromium, firefox } = require('@playwright/test');
const source = `<h1>Architecture</h1><div style="color: red">Service A</div>
<script>parent.document.body.dataset.leaked='yes'; fetch('https://blocked.invalid/script'); location='https://blocked.invalid/navigation';</script>
<meta http-equiv="refresh" content="0;url=https://blocked.invalid/refresh">
<a href="https://blocked.invalid/link">Link</a>
<form action="https://blocked.invalid/form"><button>Submit</button></form>
<img src="https://blocked.invalid/image" onerror="alert(1)">
<style>@import url('https://blocked.invalid/css'); div { background: url('https://blocked.invalid/background'); }</style>
<iframe src="https://blocked.invalid/frame"></iframe>`;
const result = spawnSync(fileURLToPath(new URL('../.venv/bin/python', import.meta.url)),
  ['-c', 'import sys; from runtime_service.workspace.html_preview import safe_html; print(safe_html(sys.stdin.read()))'],
  { input: source, encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);

for (const [name, engine] of Object.entries({ chromium, firefox })) {
  const browser = await engine.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const externalRequests = [];
    await page.route('**/*', async route => {
      if (route.request().url() === 'http://workspace.test/') {
        await route.fulfill({ contentType: 'text/html', body: '<main>Platform</main><iframe sandbox=""></iframe>' });
      } else {
        externalRequests.push(route.request().url());
        await route.abort();
      }
    });
    await page.goto('http://workspace.test/');
    await page.locator('iframe').evaluate((frame, html) => { frame.srcdoc = html; }, result.stdout);
    const frame = page.frameLocator('iframe');
    await frame.locator('h1').waitFor();
    assert.equal(await frame.locator('h1').textContent(), 'Architecture');
    assert.equal(await frame.locator('div').evaluate(el => getComputedStyle(el).color), 'rgb(255, 0, 0)');
    await page.waitForTimeout(300);
    assert.deepEqual(externalRequests, []);
    assert.equal(await page.locator('body').getAttribute('data-leaked'), null);
    assert.equal(await frame.locator('script, iframe, a[href], form, meta[http-equiv="refresh"]').count(), 0);
    assert.equal(await frame.locator('body').evaluate(() => {
      try { return !!parent.document; } catch { return false; }
    }), false);
    console.log(`${name}: static layout, opaque origin, script/navigation/network isolation PASS`);
  } finally {
    await browser.close();
  }
}
