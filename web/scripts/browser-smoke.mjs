import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { chromium, expect } from "@playwright/test";

const token = process.env.CALLMAP_TEST_TOKEN;
assert(token, "Set CALLMAP_TEST_TOKEN for this explicitly selected test installation.");
const AxeBuilder = createRequire(import.meta.url)("@axe-core/playwright").default;
const root = new URL("../../", import.meta.url);
const output = fileURLToPath(new URL(".local/browser/", root));
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, acceptDownloads: true });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(process.env.CALLMAP_BROWSER_URL || "http://127.0.0.1:5175");
  await page.getByLabel("Local access token", { exact: true }).fill(token);
  await page.getByRole("button", { name: "Open workspace →" }).click();
  const sample = page.getByRole("button", { name: "Load sample", exact: true });
  await expect(sample).toBeEnabled();
  await expect(page.locator(".live-optin input")).toBeDisabled();
  await sample.click();
  await expect(page.locator(".segment")).toHaveCount(6, { timeout: 20000 });
  await expect(page.locator(".commitment")).toHaveCount(4);
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("audio")?.currentTime > 0.4);
  await page.locator(".segment").nth(1).click();
  const manifest = JSON.parse(await readFile(new URL("fixtures/launch-checkin.json", root), "utf8"));
  assert((await page.locator("audio").evaluate((audio) => audio.currentTime)) >= manifest.segments[1].start - 0.2);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  const first = page.locator(".commitment").first();
  await first.getByText("Exact source quotation", { exact: true }).click();
  await expect(first.getByText(manifest.segments[1].text, { exact: true })).toBeVisible();
  await first.getByRole("textbox", { name: "Owner for item 1" }).fill("Leo reviewed");
  await first.getByRole("button", { name: "Accept action" }).click();
  await first.getByRole("button", { name: "Reviewed · undo" }).waitFor();
  await page.reload();
  await page.locator(".recording-link").first().click();
  await expect(page.locator(".commitment").first().getByRole("textbox", { name: "Owner for item 1" })).toHaveValue("Leo reviewed");
  const downloadPending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export reviewed" }).click();
  await (await downloadPending).saveAs(`${output}/reviewed-items.json`);
  const exported = JSON.parse(await readFile(`${output}/reviewed-items.json`, "utf8"));
  assert.equal(exported.items.length, 1);
  assert.equal(exported.items[0].owner, "Leo reviewed");
  assert.equal(exported.provenance.live_inference, false);
  const scans = [];
  for (const [name, width, height] of [["desktop", 1440, 1050], ["mobile", 390, 844]]) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => window.scrollTo(0, 0));
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} overflow`);
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    scans.push({ viewport: name, violations: result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) })) });
    await page.screenshot({ path: `${output}/${name}.png`, fullPage: true });
  }
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete recording", exact: true }).click();
  await page.getByRole("heading", { name: "Start with a conversation." }).waitFor();
  console.log(JSON.stringify({ workflow: "passed", browserErrors: errors, accessibility: scans }));
  assert.deepEqual(errors, []);
  assert(scans.every((scan) => scan.violations.length === 0), "Accessibility violations; inspect the retained report/screenshots");
} finally {
  await browser.close();
}
