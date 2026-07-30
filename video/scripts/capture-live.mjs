import {mkdir, rename} from "node:fs/promises";
import {resolve} from "node:path";
import {chromium} from "playwright-core";

const repositoryRoot = resolve(import.meta.dirname, "../..");
const captureDirectory = resolve(repositoryRoot, "video/public/captures");
await mkdir(captureDirectory, {recursive: true});

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--disable-dev-shm-usage"],
});
const context = await browser.newContext({
  viewport: {width: 1920, height: 1080},
  recordVideo: {
    dir: captureDirectory,
    size: {width: 1920, height: 1080},
  },
});
const page = await context.newPage();
const recordedVideo = page.video();

await page.goto("http://127.0.0.1:8000/", {waitUntil: "networkidle"});
await page.waitForTimeout(3500);
await page.locator("#run-review").hover();
await page.waitForTimeout(750);
await page.locator("#run-review").click();
await page.locator("#result-state").waitFor({state: "visible", timeout: 45000});
await page.waitForTimeout(9000);
await page.locator("#lineage-heading").scrollIntoViewIfNeeded();
await page.waitForTimeout(8000);
await page.locator("#actions-heading").scrollIntoViewIfNeeded();
await page.waitForTimeout(8000);
await page.evaluate(() => window.scrollTo({top: 0, behavior: "smooth"}));
await page.waitForTimeout(7000);

await context.close();
await browser.close();
const temporaryPath = await recordedVideo.path();
const finalPath = resolve(captureDirectory, "live-review.webm");
await rename(temporaryPath, finalPath);
console.log(JSON.stringify({capture: finalPath, status: "passed"}));
