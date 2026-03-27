// @ts-check
const { test, expect } = require('@playwright/test');

async function waitForDataLoaded(page) {
  await page.waitForFunction(() => {
    return window.__contabulateReady === true;
  }, { timeout: 15000 });
}

async function pickSampleQuery(page) {
  return page.evaluate(async () => {
    const tokens = await fetch('data/tokens.json').then((r) => r.json());
    return Object.keys(tokens).find((key) => key.length >= 4) || Object.keys(tokens)[0];
  });
}

async function search(page, query, { gran = 'play', ngramMode = '1', matchMode = 'exact' } = {}) {
  await page.selectOption('#gran', gran);
  await page.selectOption('#ngramMode', ngramMode);
  await page.selectOption('#matchMode', matchMode);
  await page.fill('#q', query);
  await page.press('#q', 'Enter');
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
}

test.describe('Page Load', () => {
  test('loads and shows the Luther title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Luther Bible/);
  });

  test('shows base stats on first load with no search terms', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    await page.waitForSelector('#results tbody tr', { timeout: 10000 });
    await expect(page.locator('#results tbody tr')).toHaveCount(50);
    await expect(page.locator('#results thead th')).toContainText(['Location', 'Book', '# words']);
  });
});

test.describe('Segments Search', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
  });

  test('supports exact-term auto ngram detection and removable headers', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await page.fill('#q', `${sample} ${sample}`);
    await page.click('#addColumnBtn');
    await expect(page.locator('#results thead th')).toContainText([`"${sample} ${sample}"`]);
    await page.locator('#results thead th button.remove-col').click();
    await expect(page.locator('#results thead th')).not.toContainText([`"${sample} ${sample}"`]);
  });

  test('supports regex mode with explicit ngram selection', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, `^${sample}$`, { gran: 'play', matchMode: 'regex', ngramMode: '1' });
    expect(await page.locator('#results tbody tr').count()).toBeGreaterThan(0);
  });

  test('verse text rows render highlights', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, sample, { gran: 'line' });
    await page.locator('#segmentsTab details summary').click();
    expect(await page.locator('#results tbody td .hit').count()).toBeGreaterThan(0);
  });
});

test.describe('Verses Tab', () => {
  test('shows matching verse rows', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    const sample = await pickSampleQuery(page);
    await page.evaluate(() => { document.querySelector('.tabs').style.display = 'flex'; });
    await page.click('.tab-btn[data-tab="lines"]');
    await page.fill('#linesQuery', sample);
    await page.press('#linesQuery', 'Enter');
    await page.waitForSelector('#linesResults tbody tr', { timeout: 10000 });
    await expect(page.locator('#linesResults thead th')).toContainText(['Book', 'Chapter', 'Verse', 'Verse Text']);
  });
});
