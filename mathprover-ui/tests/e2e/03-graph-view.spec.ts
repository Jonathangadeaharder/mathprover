import { test, expect } from '@playwright/test';

test.describe('Graph view', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/workspace');
    await page.waitForLoadState('networkidle');
  });

  test('graph stage renders with aria label', async ({ page }) => {
    await expect(page.getByRole('application', { name: 'Theorem dependency graph' })).toBeVisible();
  });

  test('graph renders theorem nodes', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await expect(stage.getByText('Constant-Ratio Runtime Theorem')).toBeVisible();
    await expect(stage.getByText('Kernel Founder Mass Lemma')).toBeVisible();
    await expect(stage.getByText('Positive Founder Survival')).toBeVisible();
  });

  test('graph renders paper IDs on nodes', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await expect(stage.getByText('Thm 5.4')).toBeVisible();
    await expect(stage.getByText('Lem 3.2')).toBeVisible();
    await expect(stage.getByText('Lem 3.4')).toBeVisible();
  });

  test('graph shows capstone flag', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await expect(stage.getByText('capstone')).toBeVisible();
  });

  test('graph legend renders all statuses', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    const legend = stage.locator('.graph-legend');
    await expect(legend.getByText('proven', { exact: true })).toBeVisible();
    await expect(legend.getByText('disproven', { exact: true })).toBeVisible();
    await expect(legend.getByText('sorries', { exact: true })).toBeVisible();
    await expect(legend.getByText('in_progress', { exact: true })).toBeVisible();
    await expect(legend.getByText('stuck', { exact: true })).toBeVisible();
    await expect(legend.getByText('ready', { exact: true })).toBeVisible();
    await expect(legend.getByText('unexplored', { exact: true })).toBeVisible();
  });

  test('zoom controls render', async ({ page }) => {
    const zoomOut = page.getByTitle('zoom out');
    const zoomIn = page.getByTitle('zoom in');
    const fit = page.getByTitle('fit');
    await expect(zoomOut).toBeVisible();
    await expect(zoomIn).toBeVisible();
    await expect(fit).toBeVisible();
  });

  test('zoom in increases scale', async ({ page }) => {
    const zoomLabel = page.locator('.zoom-label');
    await expect(zoomLabel).toContainText('85');
    await page.getByTitle('zoom in').click();
    await expect(zoomLabel).toContainText('98');
  });

  test('zoom out decreases scale', async ({ page }) => {
    await page.getByTitle('zoom out').click();
    const zoomLabel = page.locator('.zoom-label');
    await expect(zoomLabel).toContainText('72');
  });

  test('fit resets zoom', async ({ page }) => {
    await page.getByTitle('zoom in').click();
    await page.getByTitle('zoom in').click();
    await page.getByTitle('fit').click();
    const zoomLabel = page.locator('.zoom-label');
    await expect(zoomLabel).toContainText('85');
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    const box = await stage.boundingBox();
    const nodes = await page.locator('.gnode').all();
    let visible = 0;
    for (const n of nodes) {
      const nb = await n.boundingBox();
      if (nb && box && nb.x + nb.width > 0 && nb.x < box.x + box.width && nb.y + nb.height > 0 && nb.y < box.y + box.height) visible++;
    }
    expect(visible).toBeGreaterThan(nodes.length / 2);
  });

  test('clicking a node opens detail panel', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await stage.getByText('Kernel Founder Mass Lemma').click();
    await expect(page.getByRole('heading', { name: 'Kernel Founder Mass Lemma' })).toBeVisible();
    await expect(page.getByText('Lean theorem')).toBeVisible();
  });

  test('graph shows agent chip on node with attempts', async ({ page }) => {
    const stage = page.getByRole('application', { name: 'Theorem dependency graph' });
    await expect(stage.getByText(/qwen3-72b/).first()).toBeVisible();
  });

  test('screenshot: graph view', async ({ page }) => {
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'tests/screenshots/03-graph-view.png', fullPage: true });
  });
});
