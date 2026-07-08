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
    await expect(page.locator('#results thead')).toContainText('Verse', { timeout: 10000 });
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
    expect(texts.some(t => t.includes('# verses'))).toBeTruthy();
    expect(texts.some(t => t.includes('# comments'))).toBeTruthy();
    expect(texts.some(t => t.includes('Comments / verse'))).toBeTruthy();
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

  test('can add commentator columns from the + popover', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, sample, { gran: 'play' });
    let texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('# verses'))).toBeTruthy();
    expect(texts.some(t => t.includes('Comments / verse'))).toBeTruthy();
    expect(texts.some(t => t.includes('Augustine of Hippo'))).toBeFalsy();

    await page.locator('#results thead th.add-column-th').click();
    const popover = page.locator('.add-column-popover');
    await expect(popover).toBeVisible();
    await popover.locator('.add-column-search').fill('augustine of hippo');
    await popover.locator('.add-column-option', { hasText: 'Augustine of Hippo' }).first().click();
    await popover.locator('.add-column-search').fill('theophylact');
    const theophylact = popover.locator('.add-column-option', { hasText: 'Theophylact' });
    await expect(theophylact).toHaveCount(1);
    await expect(theophylact.locator('.count')).toHaveText('8,088');
    await theophylact.click();
    await page.keyboard.press('Escape');
    texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Augustine of Hippo'))).toBeTruthy();
    expect(texts.some(t => t.includes('Theophylact of Ohrid'))).toBeTruthy();
  });

  test('count cells drill down and ancestor cells filter', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    // Books → the 50 chapters of Genesis (1. Mose)
    await page.locator('#results tbody tr').first().locator('td:nth-child(4) button.drill-link').click();
    await expect(page.locator('#gran')).toHaveValue('act');
    await expect(page.locator('#segmentsTotalInfo')).toContainText('(50 total rows)');
    await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 01.Gen.');
    // Back un-drills
    await page.goBack();
    await expect(page.locator('#gran')).toHaveValue('play');
    // Testament cell filters books to that testament
    await page.locator('#results tbody tr').first().locator('td:nth-child(3) .drill-link').click();
    await expect(page.locator('#results tbody tr')).toHaveCount(39);
    await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('is Old Testament');
  });

  test('vocabulary granularities put n-grams in the rows', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    await page.selectOption('#gran', 'word');
    await expect(page.locator('#results thead th[data-key="ngram"]')).toHaveCount(1);
    await expect(page.locator('#results thead th[data-key="unusualness"]')).toHaveCount(1);
    // No proper-name data in this corpus, so the toggle stays hidden
    await expect(page.locator('#vocabNamesToggle')).toBeHidden();
    // The search box filters the Word column here
    await page.fill('#q', 'licht');
    await page.locator('#addColumnBtn').click();
    await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('matches licht');
    const words = await page.locator('#results tbody tr td:first-child').allTextContents();
    expect(words.length).toBeGreaterThan(0);
    expect(words.every(w => w.includes('licht'))).toBeTruthy();
  });

  test('supports regex mode with explicit ngram selection', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, `^${sample}$`, { gran: 'play', matchMode: 'regex', ngramMode: '1' });
    expect(await page.locator('#results tbody tr').count()).toBeGreaterThan(0);
  });

  test('verse rows render highlights', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, sample, { gran: 'line' });
    await page.locator('#segmentsTab details summary').click();
    await expect(page.locator('#results tbody td .hit').first()).toBeVisible({ timeout: 10000 });
  });

  test('granularity selector uses Verse for verse text rows', async ({ page }) => {
    const options = await page.locator('#gran option').evaluateAll((opts) =>
      opts.map((opt) => ({ value: opt.value, text: (opt.textContent || '').trim() }))
    );
    expect(options.some((opt) => opt.value === 'scene')).toBeFalsy();
    expect(options).toContainEqual({ value: 'line', text: 'Verse' });
  });

  test('maps legacy verse URL granularities to text-backed Verse view', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await page.goto(`/?q=${sample}&nm=1&gran=line&mm=exact&sk=location&sd=asc&cs=1&zr=0&hl=1`);
    await waitForDataLoaded(page);
    await page.waitForSelector('#results tbody tr', { timeout: 10000 });
    await expect(page.locator('#gran')).toHaveValue('line');
    let texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Verse'))).toBeTruthy();

    await page.goto(`/?q=${sample}&nm=1&gran=scene&mm=exact&sk=location&sd=asc&cs=1&zr=0&hl=1`);
    await waitForDataLoaded(page);
    await page.waitForSelector('#results tbody tr', { timeout: 10000 });
    await expect(page.locator('#gran')).toHaveValue('line');
    texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Verse'))).toBeTruthy();
  });
});

test.describe('Verses Tab', () => {
  test('shows matching verse rows at Verse granularity', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    const sample = await pickSampleQuery(page);
    await search(page, sample, { gran: 'line' });
    const texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Book'))).toBeTruthy();
    expect(texts.some(t => t.includes('Chapter'))).toBeTruthy();
    expect(texts.some(t => t.includes('Verse #'))).toBeTruthy();
    expect(texts.some(t => t.includes('# comments'))).toBeTruthy();
    await expect(page.locator('#results tbody tr').first()).toBeVisible();
  });
});

test('vocabulary scope survives switching the n-gram size', async ({ page }) => {
  await page.goto('/?gran=word&s_ft_location=%5E01%5C.Gen%5C.');
  await waitForDataLoaded(page);
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 01.Gen.');
  // Switching word -> bigram keeps the same scope in place
  await page.selectOption('#gran', 'bigram');
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 01.Gen.');
  await page.selectOption('#gran', 'trigram');
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 01.Gen.');
  // ...and carries into the location granularities
  await page.selectOption('#gran', 'act');
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 01.Gen.');
  // Jumping coarser than the scope shows its containing row, not nothing
  await page.selectOption('#gran', 'play');
  await expect(page.locator('#results tbody tr')).toHaveCount(1);
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 01.Gen.');
});
