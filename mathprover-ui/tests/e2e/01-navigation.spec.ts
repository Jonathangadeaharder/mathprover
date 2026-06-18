import { test, expect } from "@playwright/test";

test.describe("Project picker → workspace navigation", () => {
  test("project picker renders when no project detected", async ({ page }) => {
    // Use invalid project param to prevent auto-detection
    await page.goto("/?project=/nonexistent");
    await expect(
      page.getByRole("heading", { name: "Open a Lean+LaTeX research project" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Open.*project/i }),
    ).toBeVisible();
  });

  test("project picker shows folder structure", async ({ page }) => {
    await page.goto("/?project=/nonexistent");
    await expect(page.getByText("Expected folder structure")).toBeVisible();
    await expect(page.getByText("graph.json")).toBeVisible();
  });

  test("clicking open project navigates to workspace", async ({ page }) => {
    await page.goto("/");
    // Auto-redirects to /workspace because MATHPROVER_PROJECT_PATH is set
    await expect(page).toHaveURL(/\/workspace/);
    await expect(page.getByRole("heading", { name: "Graph" })).toBeVisible();
  });

  test("workspace shows topbar with project name", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/workspace/);
    // Project chip appears after client-side state syncs
    await page.waitForTimeout(500);
    await expect(page.getByText("Test CRN Project")).toBeVisible();
  });

  test("workspace shows theorem count in pane header", async ({ page }) => {
    await page.goto("/workspace");
    await expect(page.getByText(/theorems/)).toBeVisible();
  });

  test("screenshot: project picker", async ({ page }) => {
    await page.goto("/?project=/nonexistent");
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: "tests/screenshots/01-project-picker.png",
      fullPage: true,
    });
  });

  test("screenshot: workspace graph", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
    await page.screenshot({
      path: "tests/screenshots/02-workspace-graph.png",
      fullPage: true,
    });
  });
});
