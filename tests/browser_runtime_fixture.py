"""Synthetic local browser dependencies for runtime-check CLI contract tests."""
import json
import os


def browser_runtime_env(tmp_path, prefix, *, browser_present=True):
    module = tmp_path / "playwright.cjs"
    module.write_text(
        "module.exports = {chromium: {executablePath: () => 'fixture-chromium', "
        "launchPersistentContext: () => {throw new Error('runtime-check must not launch a browser')}}};"
    )
    preload = tmp_path / "browser-filesystem.cjs"
    # Only this subprocess sees the simulated installation. Module resolution
    # and the helper's actual runtime-check CLI still execute normally.
    preload.write_text(
        "require('node:fs').existsSync = () => " + json.dumps(browser_present) + ";"
    )
    return {
        **os.environ,
        f"{prefix}_PLAYWRIGHT_MODULE": str(module),
        f"{prefix}_BROWSER_CHANNEL": "chrome",
        f"{prefix}_BROWSER_HEADLESS": "0",
        "NODE_OPTIONS": "--require " + json.dumps(str(preload)),
    }
