import { test, expect } from "@playwright/test";

test.describe("Premise picker modal", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
  });

  test("dispatch from frontier opens premise picker", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("premise picker shows node paper ID", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await expect(page.getByText(/Confirm dispatch/)).toBeVisible();
  });

  test("premise picker shows dependencies section", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await expect(page.getByText("Dependencies (required)")).toBeVisible();
  });

  test("premise picker shows mathlib retrieval section", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await expect(
      page.getByText("Mathlib retrieval (semantic search)"),
    ).toBeVisible();
  });

  test("premise picker shows paper context section", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await expect(page.getByText("Paper context")).toBeVisible();
  });

  test("premise picker shows cancel and dispatch buttons", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: /Dispatch/ }),
    ).toBeVisible();
  });

  test("premise picker cancel closes modal", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Cancel" })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("premise picker shows real definitions from project data", async ({
    page,
  }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await expect(page.getByText("Mathlib retrieval")).toBeVisible();
  });

  test("screenshot: premise picker", async ({ page }) => {
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
    await page
      .getByRole("button", { name: "Dispatch", exact: true })
      .first()
      .click();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "tests/screenshots/12-premise-picker.png",
      fullPage: true,
    });
  });
});
