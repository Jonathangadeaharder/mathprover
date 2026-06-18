import { test, expect } from '@playwright/test';

test.describe('Node detail panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/workspace');
    await page.waitForLoadState('networkidle');
  });

  test('detail panel hidden when no node selected', async ({ page }) => {
    const overlay = page.locator('.detail-overlay');
    await expect(overlay).toHaveClass(/\bhidden\b/);
  });

  test('clicking node shows detail panel with heading', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Constant-Ratio Runtime Theorem').click();
    await expect(page.getByRole('heading', { name: 'Constant-Ratio Runtime Theorem' })).toBeVisible();
  });

  test('detail panel shows paper statement', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Constant-Ratio Runtime Theorem').click();
    const overlay = page.locator('.detail-overlay');
    await expect(overlay.getByText('Statement (paper)')).toBeVisible();
    await expect(overlay.getByText('Every stochastically CRN admits a constant-ratio runtime bound.')).toBeVisible();
  });

  test('detail panel shows metadata', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Kernel Founder Mass Lemma').click();
    const overlay = page.locator('.detail-overlay');
    await expect(overlay.getByText('Metadata')).toBeVisible();
    await expect(overlay.getByText('Importance')).toBeVisible();
    await expect(overlay.getByText('Difficulty')).toBeVisible();
    await expect(overlay.getByText('Tokens spent')).toBeVisible();
  });

  test('detail panel shows tabs', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Constant-Ratio Runtime Theorem').click();
    const overlay = page.locator('.detail-overlay');
    await expect(overlay.getByRole('button', { name: 'Overview' })).toBeVisible();
    await expect(overlay.getByRole('button', { name: 'Paper source' })).toBeVisible();
    await expect(overlay.getByRole('button', { name: 'Lean code' })).toBeVisible();
    await expect(overlay.getByRole('button', { name: 'Mapping' })).toBeVisible();
    await expect(overlay.getByRole('button', { name: 'Attempts' })).toBeVisible();
    await expect(overlay.getByRole('button', { name: 'Subgoals' })).toBeVisible();
  });

  test('detail panel shows depends on section', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Constant-Ratio Runtime Theorem').click();
    const overlay = page.locator('.detail-overlay');
    await expect(overlay.getByText('Depends on')).toBeVisible();
  });

  test('detail panel shows uses definitions section', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Constant-Ratio Runtime Theorem').click();
    const overlay = page.locator('.detail-overlay');
    await expect(overlay.getByText('Uses definitions')).toBeVisible();
    await expect(overlay.getByText('Test.CRN')).toBeVisible();
  });

  test('detail panel close button works', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Kernel Founder Mass Lemma').click();
    await expect(page.getByRole('heading', { name: 'Kernel Founder Mass Lemma' })).toBeVisible();
    await page.getByRole('button', { name: 'close' }).click();
    const overlay = page.locator('.detail-overlay');
    await expect(overlay).toHaveClass(/\bhidden\b/);
  });

  test('Meter component renders with width (triple-style bug fix)', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Kernel Founder Mass Lemma').click();
    const meterFill = page.locator('.detail-overlay .meter-inline-fill').first();
    await expect(meterFill).toBeVisible();
    const width = await meterFill.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return rect.width;
    });
    expect(width).toBeGreaterThan(0);
  });

  test('Meter importance bar has correct width', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Kernel Founder Mass Lemma').click();
    const meters = page.locator('.detail-overlay .meter-inline');
    const firstMeter = meters.first();
    const fill = firstMeter.locator('.meter-inline-fill');
    const width = await fill.evaluate((el) => {
      const parent = el.parentElement;
      if (!parent) return 0;
      const parentWidth = parent.getBoundingClientRect().width;
      const fillWidth = el.getBoundingClientRect().width;
      return fillWidth / parentWidth;
    });
    expect(fill).toBeDefined();
    expect(width).toBeGreaterThan(0);
  });

  test('attempts tab shows attempt log', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Constant-Ratio Runtime Theorem').click();
    const overlay = page.locator('.detail-overlay');
    await overlay.getByRole('button', { name: 'Attempts' }).click();
    await expect(overlay.getByText('1 attempt')).toBeVisible();
    await expect(overlay.getByText('Strategy:')).toBeVisible();
    await expect(overlay.getByText('direct_search', { exact: true })).toBeVisible();
  });

  test('subgoals tab shows sorries for node with sorries', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Robust Fill Assembly').click();
    const overlay = page.locator('.detail-overlay');
    await overlay.getByRole('button', { name: 'Subgoals' }).click();
    await expect(overlay.getByText('Agent-proposed subgoals')).toBeVisible();
    await expect(overlay.getByText('sorry_assembly')).toBeVisible();
  });

  test('subgoals tab shows empty state for proven node', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Kernel Founder Mass Lemma').click();
    const overlay = page.locator('.detail-overlay');
    await overlay.getByRole('button', { name: 'Subgoals' }).click();
    await expect(overlay.getByText('Theorem is fully derived.')).toBeVisible();
  });

  test('mapping tab shows LaTeX mapping', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Kernel Founder Mass Lemma').click();
    const overlay = page.locator('.detail-overlay');
    await overlay.getByRole('button', { name: 'Mapping' }).click();
    await expect(overlay.getByText('In LaTeX')).toBeVisible();
    await expect(overlay.getByText('@lean:')).toBeVisible();
  });

  test('screenshot: node detail', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Constant-Ratio Runtime Theorem').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: 'tests/screenshots/04-node-detail.png', fullPage: true });
  });
});
