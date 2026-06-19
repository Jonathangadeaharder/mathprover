import { test, expect } from "@playwright/test";

test.describe("Tracks view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Tracks" }).click();
  });

  test("tracks heading renders", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Tracks" })).toBeVisible();
  });

  test("tracks show lane titles", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Leaves" })).toBeVisible();
  });

  test("tracks render theorem names", async ({ page }) => {
    await expect(page.getByText("Kernel Founder Mass Lemma")).toBeVisible();
  });

  test("screenshot: tracks view", async ({ page }) => {
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "tests/screenshots/05-tracks-view.png",
      fullPage: true,
    });
  });
});

test.describe("Frontier view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Frontier" }).click();
  });

  test("frontier heading renders", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Frontier" })).toBeVisible();
  });

  test("frontier shows ready section", async ({ page }) => {
    await expect(page.getByText("Ready to attempt")).toBeVisible();
  });

  test("frontier shows ranked candidates", async ({ page }) => {
    await expect(page.getByText(/#1/)).toBeVisible();
  });

  test("frontier shows theorem in ready list", async ({ page }) => {
    await expect(page.getByText("Core A3a Survival Bound")).toBeVisible();
  });

  test("frontier shows dispatch button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: "Dispatch", exact: true }).first(),
    ).toBeVisible();
  });

  test("frontier shows blocked section", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Blocked" })).toBeVisible();
  });

  test("frontier meter bars render with width", async ({ page }) => {
    const meterFills = page.locator(".frontier-row .meter-fill");
    const count = await meterFills.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      const width = await meterFills
        .nth(i)
        .evaluate((el) => el.getBoundingClientRect().width);
      expect(width).toBeGreaterThan(0);
    }
  });

  test("screenshot: frontier view", async ({ page }) => {
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "tests/screenshots/06-frontier-view.png",
      fullPage: true,
    });
  });
});

test.describe("Paper ⇄ Lean view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Paper ⇄ Lean" }).click();
  });

  test("paper-lean heading renders", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Paper ⇄ Lean" }),
    ).toBeVisible();
  });

  test("paper pane shows filepath", async ({ page }) => {
    await expect(page.getByText("paper/main.tex")).toBeVisible();
  });

  test("paper pane renders theorem blocks", async ({ page }) => {
    await expect(page.getByText("Lemma 2.1")).toBeVisible();
    await expect(page.getByText("Lemma 3.2")).toBeVisible();
    await expect(page.getByText("Theorem 5.4")).toBeVisible();
  });

  test("lean pane renders code blocks", async ({ page }) => {
    await expect(page.getByText("Test/Theorems/Runtime.lean")).toBeVisible();
  });

  test("node selector dropdown present", async ({ page }) => {
    await expect(page.locator("select.pane-header-select")).toBeVisible();
  });

  test("screenshot: paper-lean view", async ({ page }) => {
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "tests/screenshots/07-paper-lean-view.png",
      fullPage: true,
    });
  });
});

test.describe("Agent runs view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Agent runs" }).click();
  });

  test("agent runs heading renders", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Agent runs" }),
    ).toBeVisible();
  });

  test("agent list shows runs", async ({ page }) => {
    await expect(page.getByText("Agent runs").first()).toBeVisible();
  });

  test("agent detail shows timeline and log tabs", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Timeline" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Streaming log" }),
    ).toBeVisible();
  });

  test("screenshot: agents view", async ({ page }) => {
    await page.waitForTimeout(500);
    await page.screenshot({
      path: "tests/screenshots/08-agents-view.png",
      fullPage: true,
    });
  });
});

test.describe("Failures view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Failure shelf" }).click();
  });

  test("failures heading renders", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Failure shelf" }),
    ).toBeVisible();
  });

  test("failures show recorded approaches count", async ({ page }) => {
    await expect(page.getByText(/recorded failed approaches/)).toBeVisible();
  });

  test("failures show counterexample text", async ({ page }) => {
    await expect(page.getByText(/Counterexample:/)).toBeVisible();
  });

  test("failures show cost breakdown", async ({ page }) => {
    await expect(page.getByText(/tokens/).first()).toBeVisible();
  });

  test("failures show view node button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /view node/i }).first(),
    ).toBeVisible();
  });

  test("screenshot: failures view", async ({ page }) => {
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "tests/screenshots/09-failures-view.png",
      fullPage: true,
    });
  });
});

test.describe("Foundations view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Foundations" }).click();
  });

  test("foundations heading renders", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Foundations" }),
    ).toBeVisible();
  });

  test("foundations render cards", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Stochastic Dominance Lemma" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Markov Chain Hitting Time" }),
    ).toBeVisible();
  });

  test("foundations show status pills", async ({ page }) => {
    await expect(
      page.locator(".found-card .status-pill").first(),
    ).toBeVisible();
  });

  test("foundations show progress bars", async ({ page }) => {
    const bars = page.locator(".progress-fill");
    const count = await bars.count();
    expect(count).toBeGreaterThan(0);
  });

  test("foundations show subgoals", async ({ page }) => {
    await expect(page.getByText("Prove coupling exists")).toBeVisible();
    await expect(page.getByText("Tail bound via Azuma")).toBeVisible();
  });

  test("screenshot: foundations view", async ({ page }) => {
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "tests/screenshots/10-foundations-view.png",
      fullPage: true,
    });
  });
});

test.describe("Definitions view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
    const aside = page.locator("aside.sidebar");
    await aside.getByRole("button", { name: "Definitions" }).click();
  });

  test("definitions heading renders", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Definitions" }),
    ).toBeVisible();
  });

  test("definitions list shows entries", async ({ page }) => {
    await expect(page.getByText("Chemical Reaction Network")).toBeVisible();
    await expect(page.getByText("Runtime Function")).toBeVisible();
    await expect(page.getByText("Founder Species")).toBeVisible();
  });

  test("definitions show lean names", async ({ page }) => {
    await expect(page.getByText("Test.CRN")).toBeVisible();
    await expect(page.getByText("Test.runtime")).toBeVisible();
    await expect(page.getByText("Test.Founder")).toBeVisible();
  });

  test("definitions search filters results", async ({ page }) => {
    const search = page.locator('input[placeholder="Search definitions..."]');
    await search.fill("Founder");
    await expect(page.getByText("Founder Species")).toBeVisible();
    await expect(page.getByText("Chemical Reaction Network")).toHaveCount(0);
  });

  test("definitions show kind pills", async ({ page }) => {
    await expect(page.locator(".kind-pill").first()).toBeVisible();
  });

  test("screenshot: definitions view", async ({ page }) => {
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "tests/screenshots/11-definitions-view.png",
      fullPage: true,
    });
  });
});
