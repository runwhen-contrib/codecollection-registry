const playwright = require('playwright');
const fs = require('fs');
const path = require('path');

async function captureFullPageScreenshots() {
  const browser = await playwright.chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  const url = 'http://localhost:3000/collections/aws-c7n-codecollection/codebundles/aws-c7n-ebs-health';
  
  console.log(`Navigating to ${url}...`);
  await page.goto(url, { waitUntil: 'networkidle' });
  
  // Wait for content to load
  await page.waitForTimeout(2000);
  
  // Create screenshots directory
  const screenshotsDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir);
  }

  // Capture full page screenshot
  console.log('Capturing full page screenshot...');
  await page.screenshot({
    path: path.join(screenshotsDir, 'full-page.png'),
    fullPage: true
  });
  
  // Capture viewport screenshot (top of page)
  console.log('Capturing viewport screenshot (top)...');
  await page.screenshot({
    path: path.join(screenshotsDir, 'viewport-top.png'),
    fullPage: false
  });
  
  // Scroll to middle and capture
  console.log('Scrolling to middle section...');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(screenshotsDir, 'viewport-middle.png'),
    fullPage: false
  });
  
  // Scroll to bottom and capture
  console.log('Scrolling to bottom section...');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(screenshotsDir, 'viewport-bottom.png'),
    fullPage: false
  });
  
  // Capture sidebar specifically
  console.log('Capturing sidebar...');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  const sidebar = await page.$('aside, [class*="sidebar"], [class*="Sidebar"]');
  if (sidebar) {
    await sidebar.screenshot({
      path: path.join(screenshotsDir, 'sidebar.png')
    });
  }

  console.log(`\nScreenshots saved to: ${screenshotsDir}`);
  console.log('Files created:');
  console.log('  - full-page.png (complete page)');
  console.log('  - viewport-top.png (top section)');
  console.log('  - viewport-middle.png (middle section)');
  console.log('  - viewport-bottom.png (bottom section)');
  if (sidebar) {
    console.log('  - sidebar.png (sidebar only)');
  }

  await browser.close();
}

captureFullPageScreenshots().catch(console.error);
