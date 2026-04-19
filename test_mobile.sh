#!/bin/bash
# Mobile screenshot test harness for Homegrown map
# Takes screenshots at various mobile viewports for visual review
# Usage: ./test_mobile.sh [url]
#
# Requires: npx playwright (auto-installs if needed)

URL="${1:-http://localhost:8080/index.html}"
OUT_DIR="mobile_screenshots"
mkdir -p "$OUT_DIR"

echo "📱 Taking mobile screenshots from $URL"
echo "   Output: $OUT_DIR/"

node -e "
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const devices = [
    { name: 'iPhone_SE',       w: 375,  h: 667,  dpr: 2 },
    { name: 'iPhone_14',       w: 390,  h: 844,  dpr: 3 },
    { name: 'iPhone_14_Pro_Max', w: 430, h: 932, dpr: 3 },
    { name: 'Pixel_7',         w: 412,  h: 915,  dpr: 2.625 },
    { name: 'iPad_Mini',       w: 768,  h: 1024, dpr: 2 },
  ];

  for (const dev of devices) {
    console.log('  → ' + dev.name + ' (' + dev.w + 'x' + dev.h + ')');
    const ctx = await browser.newContext({
      viewport: { width: dev.w, height: dev.h },
      deviceScaleFactor: dev.dpr,
      isMobile: dev.w < 769,
      hasTouch: dev.w < 769,
    });
    const page = await ctx.newPage();
    await page.goto('${URL}', { waitUntil: 'networkidle', timeout: 30000 });
    // Wait for Three.js to render
    await page.waitForTimeout(3000);

    // Screenshot 1: Initial load
    await page.screenshot({ path: '${OUT_DIR}/' + dev.name + '_1_load.png', fullPage: false });

    // Screenshot 2: Scroll down to see schedule (mobile)
    if (dev.w < 769) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
      await page.waitForTimeout(500);
      await page.screenshot({ path: '${OUT_DIR}/' + dev.name + '_2_schedule.png', fullPage: false });

      // Screenshot 3: Full page
      await page.screenshot({ path: '${OUT_DIR}/' + dev.name + '_3_full.png', fullPage: true });
    }

    await ctx.close();
  }

  await browser.close();
  console.log('✅ Done! Screenshots in ${OUT_DIR}/');
})();
" 2>&1

echo ""
echo "Open screenshots:"
echo "  open $OUT_DIR/"
