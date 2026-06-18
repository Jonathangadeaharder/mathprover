import { test, expect } from "@playwright/test";

test.describe("Sidebar navigation + status counts", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
  });

  test("sidebar renders all route buttons", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    for (const label of [
      "Graph",
      "Tracks",
      "Frontier",
      "Definitions",
      "Paper ⇄ Lean",
      "Agent runs",
      "Failure shelf",
      "Foundations",
    ]) {
      await expect(aside.getByRole("button", { name: label })).toBeVisible();
    }
  });

  test("sidebar shows status counts", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await expect(aside.getByText("proven", { exact: true })).toBeVisible();
    await expect(aside.getByText("in progress", { exact: true })).toBeVisible();
    await expect(aside.getByText("stuck", { exact: true })).toBeVisible();
    await expect(aside.getByText("ready", { exact: true })).toBeVisible();
  });

  test("sidebar shows badge counts for graph", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    const graphButton = aside.getByRole("button", { name: "Graph" });
    await expect(graphButton).toBeVisible();
  });

  test("clicking Tracks navigates to tracks view", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Tracks" }).click();
    await expect(page.getByRole("heading", { name: "Tracks" })).toBeVisible();
  });

  test("clicking Frontier navigates to frontier view", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await expect(page.getByRole("heading", { name: "Frontier" })).toBeVisible();
  });

  test("clicking Definitions navigates to definitions view", async ({
    page,
  }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Definitions" }).click();
    await expect(
      page.getByRole("heading", { name: "Definitions" }),
    ).toBeVisible();
  });

  test("clicking Agent runs navigates to agents view", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Agent runs" }).click();
    await expect(
      page.getByRole("heading", { name: "Agent runs" }),
    ).toBeVisible();
  });

  test("clicking Failure shelf navigates to failures view", async ({
    page,
  }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Failure shelf" }).click();
    await expect(
      page.getByRole("heading", { name: "Failure shelf" }),
    ).toBeVisible();
  });

  test("clicking Foundations navigates to foundations view", async ({
    page,
  }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Foundations" }).click();
    await expect(
      page.getByRole("heading", { name: "Foundations" }),
    ).toBeVisible();
  });

  test("clicking Paper ⇄ Lean navigates to paper-lean view", async ({
    page,
  }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Paper ⇄ Lean" }).click();
    await expect(
      page.getByRole("heading", { name: "Paper ⇄ Lean" }),
    ).toBeVisible();
  });

  test("clicking Graph returns to graph view", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await aside.getByRole("button", { name: "Graph" }).click();
    await expect(page.getByRole("heading", { name: "Graph" })).toBeVisible();
  });
});
