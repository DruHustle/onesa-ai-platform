// Bind Playwright's normal launch paths to the patched distro browser.
// This image is distinct from official Playwright browser distributions.
const fs = require('node:fs');
const path = require('node:path');
const root = '/opt/onesa-ai-platform/onesa-ai-platform-frontend/apps/chat/node_modules';
const core = require.resolve('playwright-core/package.json', {paths:[root]});
const {registry: {registry}} = require(path.join(path.dirname(core), 'lib/coreBundle.js'));
const wrapper = '/usr/local/bin/onesa-qualification-chromium';
fs.writeFileSync(wrapper, '#!/bin/sh\nexport LIBGL_ALWAYS_SOFTWARE=1 EGL_PLATFORM=surfaceless\nexec /usr/bin/chromium-browser "$@" --ignore-gpu-blocklist --use-gl=angle --use-angle=vulkan --enable-features=CDPScreenshotNewSurface,Vulkan --disable-vulkan-surface\n', {mode:0o755, flag:'wx'});
for (const name of ['chromium', 'chromium-headless-shell']) {
  const executable = registry.findExecutable(name).executablePath();
  if (!executable.startsWith('/ms-playwright/') || !fs.existsSync('/usr/bin/chromium-browser')) throw Error('System browser binding');
  fs.mkdirSync(path.dirname(executable), {recursive:true});
  fs.symlinkSync(wrapper, executable);
}
