/* Optional UI smoke test: node test_browser.cjs <site root URL> <output folder>. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const root = process.argv[2];
  const out = path.resolve(process.argv[3] || 'build/tafel-browser-qa');
  await fs.mkdir(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  async function ready() { await page.waitForFunction(() => document.body?.dataset.ready); }
  async function change(selector, value) {
    const old = await page.locator('body').getAttribute('data-ready');
    await page.locator(selector).selectOption(value);
    await page.waitForFunction(old => document.body.dataset.ready !== old, old);
  }
  async function mode(value) {
    const old = await page.locator('body').getAttribute('data-ready');
    await page.locator(`input[name=view][value=${value}]`).check({ force: true });
    await page.waitForFunction(old => document.body.dataset.ready !== old, old);
  }
  await page.goto(new URL('tafel/index.html', root).href);
  await ready();
  assert.equal(await page.evaluate(() => TAFEL_DATA.records.length), 3033);
  assert.equal(await page.evaluate(() => selected.length), 3006);
  assert.ok(await page.evaluate(() => selected.every(r => r.group !== 'unknown')));
  assert.equal(await page.locator('.legend span').count(), 3);
  const ptc = await page.evaluate(() => {const s=stats(rowsInWindow(2,'PtC'));return {curves:s.rows.length,median:s.q[2]};});
  assert.equal(ptc.curves,338);
  assert.ok(Math.abs(ptc.median-116.53804670753921)<1e-9);
  assert.ok(await page.evaluate(() => document.getElementById('curve-plot').data.some(t => t.x.length > 500)));
  await page.screenshot({ path: path.join(out, 'desktop-curves.png') });
  await change('#basis', 'all');
  assert.equal(await page.evaluate(() => selected.length), 3030);
  await mode('distribution');
  await change('#window','6');
  assert.ok(await page.evaluate(() => document.getElementById('density-plot').data.every(t=>['Pt/C','PGM (non-Pt/C)','non-PGM'].includes(t.name))));
  assert.ok(await page.evaluate(() => catalog.every(r=>r.group!=='unknown')));
  const excludedIds=await page.evaluate(()=>TAFEL_DATA.records.filter(r=>r.group==='unknown').map(r=>r.id));
  for(const id of excludedIds){
    const old=await page.locator('body').getAttribute('data-ready');
    await page.locator('#search').fill(id);
    await page.waitForFunction(old=>document.body.dataset.ready!==old,old);
    assert.match(await page.locator('#summary').innerText(),/^0 curves/);
  }
  const beforeClear=await page.locator('body').getAttribute('data-ready');
  await page.locator('#search').fill('');
  await page.waitForFunction(old=>document.body.dataset.ready!==old,beforeClear);
  await mode('curves');
  await change('#window','all');
  await change('#template', 'any');
  assert.match(await page.locator('#summary').innerText(), /1,343 curves/);
  await change('#composition', 'pgm');
  assert.match(await page.locator('#summary').innerText(), /695 curves/);
  await change('#composition', 'nonpgm');
  assert.match(await page.locator('#summary').innerText(), /648 curves/);
  await change('#composition', 'ptc');
  assert.match(await page.locator('#summary').innerText(), /0 curves/);
  await mode('distribution');
  assert.match(await page.locator('#statistics').innerText(), /No eligible/);
  await change('#template', 'all');
  await change('#composition', 'all');
  await change('#condition', 'alkaline');
  await change('#basis', 'geometric_area');
  await change('#element', 'Ni');
  await change('#axis', 'current');
  await change('#window', '4');
  assert.ok(await page.locator('#statistics tbody tr').count() >= 2);
  await page.screenshot({ path: path.join(out, 'desktop-ni-distributions.png') });

  const maths = await page.evaluate(() => {
    const s = window.TafelStats;
    const rows = [{paper:'A'}, {paper:'A'}, {paper:'B'}];
    const w = s.weights(rows, 'paper');
    const xs = Array.from({length:2001}, (_,i)=>-100+i*.2);
    const ys = s.density([0,100],[.25,.75],xs,10);
    let area = 0;
    for(let i=1;i<ys.length;i++)area += (ys[i]+ys[i-1])*.1;
    const d = document.getElementById('density-plot').data;
    return {w, q:s.quantiles([10,20,30],w,[.5])[0],area,densityTraces:d.length,
      finite:d.every(t=>t.x.every(Number.isFinite)&&t.y.every(Number.isFinite))};
  });
  assert.deepEqual(maths.w, [.25,.25,.5]);
  assert.equal(maths.q, 20);
  assert.ok(Math.abs(maths.area-1)<1e-10);
  assert.ok(maths.finite && maths.densityTraces >= 2);
  await change('#weight', 'curve');
  await change('#slope-range', 'full');
  await change('#density-mode', 'ecdf');
  assert.ok(await page.evaluate(() => document.getElementById('density-plot').data.every(t=>Math.abs(t.y.at(-1)-1)<1e-10)));
  await change('#density-mode', 'kde');
  await change('#slope-range', '600');
  const beforeLog = await page.locator('#statistics tbody').innerText();
  await change('#density-scale','log');
  assert.equal(await page.evaluate(()=>document.getElementById('density-plot').layout.xaxis.type),'log');
  assert.ok(await page.evaluate(()=>document.getElementById('density-plot').data.every(t=>t.x.every(x=>x>0))));
  assert.equal(await page.locator('#statistics tbody').innerText(),beforeLog);
  await page.screenshot({path:path.join(out,'desktop-log-density.png')});
  await change('#density-mode','ecdf');
  assert.ok(await page.evaluate(()=>document.getElementById('density-plot').data.every(t=>t.x.every(x=>x>0))));
  await change('#density-mode','kde');
  const downloadEvent = page.waitForEvent('download');
  await page.locator('#export-statistics').click();
  const download = await downloadEvent;
  const csvPath = path.join(out, download.suggestedFilename());
  await download.saveAs(csvPath);
  const csv = await fs.readFile(csvPath, 'utf8');
  assert.ok(csv.includes('within_group_window_weight') && csv.includes('20-40'));

  await page.locator('#catalog .curve-link').first().click();
  await page.waitForFunction(() => !document.getElementById('clear-focus').hidden);
  assert.ok(await page.evaluate(() => document.getElementById('curve-plot').data.at(-1).mode === 'lines+markers'));
  await page.locator('#clear-focus').click();
  for (const element of ['Fe','Co','Mo']) {
    await change('#element', element);
    assert.doesNotMatch(await page.locator('#summary').innerText(), /^0 curves/);
  }
  await change('#element','Ni');
  await mode('distribution');
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(500);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.screenshot({ path: path.join(out, 'mobile-distributions.png'), fullPage:true });

  await page.setViewportSize({width:1440,height:1100});
  await page.goto(new URL('index.html?view=bubble',root).href);
  await page.waitForFunction(() => document.getElementById('tafel-link'));
  await page.locator('#condition').selectOption('alkaline');
  await page.locator('#composition').selectOption('nonpgm');
  await page.locator('#element').selectOption('Ni');
  await page.locator('#template').selectOption('T13');
  const bubbleCount = await page.evaluate(() => filtered.length);
  await page.locator('#tafel-link').click();
  await ready();
  const url = new URL(page.url());
  assert.equal(url.searchParams.get('element'),'Ni');
  assert.equal(url.searchParams.get('template'),'T13');
  assert.equal(url.searchParams.get('composition'),'nonpgm');
  assert.equal(url.searchParams.get('basis'),'all');
  assert.equal(await page.evaluate(()=>selected.length),bubbleCount);
  assert.doesNotMatch(await page.locator('#summary').innerText(),/^0 curves/);
  await page.locator('#composition-link').click();
  await page.waitForFunction(() => typeof filtered !== 'undefined' && document.getElementById('element').options.length > 0);
  assert.equal(await page.locator('#element').inputValue(),'Ni');
  assert.equal(await page.locator('#template').inputValue(),'T13');
  assert.equal(await page.locator('#condition').inputValue(),'alkaline');
  assert.equal(await page.evaluate(()=>filtered.length),bubbleCount);
  assert.deepEqual(errors, []);
  await fs.writeFile(path.join(out,'browser-results.json'),JSON.stringify({maths,errors,pass:true},null,2));
  console.log(JSON.stringify({pass:true,maths,errors,out},null,2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
