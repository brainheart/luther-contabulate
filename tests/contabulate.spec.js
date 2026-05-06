// @ts-check
const { test, expect } = require('@playwright/test');

async function waitForDataLoaded(page) {
  await page.waitForFunction(() => {
    return window.__contabulateReady === true;
  }, { timeout: 15000 });
}

async function pickSampleQuery(page) {
  return 'gott';
}

async function search(page, query, { gran = 'play', ngramMode = '1', matchMode = 'exact' } = {}) {
  await page.selectOption('#gran', gran);
  await page.selectOption('#matchMode', matchMode);
  if (matchMode === 'regex') {
    await page.selectOption('#ngramMode', ngramMode);
  }
  await page.fill('#q', query);
  await page.press('#q', 'Enter');
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
  if (gran === 'line') {
    await expect(page.locator('#results thead')).toContainText('Verse Text', { timeout: 10000 });
  }
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
    const texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Location'))).toBeTruthy();
    expect(texts.some(t => t.includes('Book'))).toBeTruthy();
    expect(texts.some(t => t.includes('# words'))).toBeTruthy();
    expect(texts.some(t => t.includes('# comments'))).toBeTruthy();
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
    await page.locator('#results thead th button.term-col-remove').click();
    await expect(page.locator('#results thead th')).not.toContainText([`"${sample} ${sample}"`]);
  });

  test('can add and filter individual commentator columns', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, sample, { gran: 'play' });
    let texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Augustine of Hippo'))).toBeFalsy();

    await page.locator('#segmentsTab details summary').click();
    const optionTexts = await page.locator('#commentatorColumnSelect option').allTextContents();
    expect(optionTexts.length).toBeGreaterThan(100);
    expect(optionTexts.some(t => t === 'Theophylact of Ohrid (8,088)')).toBeTruthy();

    await page.locator('#commentatorColumnSelect').selectOption('augustine');
    await page.locator('#addCommentatorColumn').click();
    texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Augustine of Hippo'))).toBeTruthy();

    await page.locator('#commentatorColumnFilter').fill('theophylact');
    const filteredOptionTexts = await page.locator('#commentatorColumnSelect option').allTextContents();
    expect(filteredOptionTexts.length).toBe(2);
    expect(filteredOptionTexts.some(t => t === 'Theophylact of Ohrid (8,088)')).toBeTruthy();
    await expect(page.locator('#commentatorColumnControls .commentator-filter-count')).toContainText('1 of');
    await page.locator('#addCommentatorColumn').click();
    texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Augustine of Hippo'))).toBeTruthy();
    expect(texts.some(t => t.includes('Theophylact of Ohrid'))).toBeTruthy();
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
    await expect(page.locator('#results tbody td .hit').first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Verses Tab', () => {
  test('shows matching verse rows', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    const sample = await pickSampleQuery(page);
    await page.evaluate(() => {
      const tabs = document.querySelector('.tabs');
      tabs.classList.remove('is-hidden');
      tabs.style.display = 'flex';
    });
    await page.click('.tab-btn[data-tab="lines"]');
    await page.fill('#linesQuery', sample);
    await page.press('#linesQuery', 'Enter');
    await expect(page.locator('#linesResults thead')).toContainText('Verse Text', { timeout: 10000 });
    const texts = await page.locator('#linesResults thead th').allTextContents();
    expect(texts.some(t => t.includes('Book'))).toBeTruthy();
    expect(texts.some(t => t.includes('Chapter'))).toBeTruthy();
    expect(texts.some(t => t.includes('Verse'))).toBeTruthy();
    expect(texts.some(t => t.includes('# comments'))).toBeTruthy();
    expect(texts.some(t => t.includes('Verse Text'))).toBeTruthy();
  });
});
