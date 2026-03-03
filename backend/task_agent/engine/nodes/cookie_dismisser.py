"""cookie_dismisser — JS injection to dismiss cookie consent overlays.

Targets common cookie consent libraries (OneTrust, CookieBot, Osano, etc.)
and generic patterns.  Zero LLM cost.

LLM call: None.
"""

import asyncio

from browser import api as browser_api
from models.state import AgentState
import run_context


COOKIE_DISMISS_JS = """
(() => {
    // Strategy 1: Click common "Accept" buttons
    const acceptTexts = [
        'accept all', 'accept cookies', 'accept', 'agree', 'i agree',
        'got it', 'ok', 'allow all', 'allow cookies', 'consent',
        '接受', '同意', '全部接受', '我同意', '确定',
    ];
    const buttons = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
    for (const btn of buttons) {
        const text = (btn.textContent || btn.value || '').trim().toLowerCase();
        if (acceptTexts.some(t => text === t || text.startsWith(t))) {
            btn.click();
            return 'clicked_accept: ' + text;
        }
    }

    // Strategy 2: Remove common cookie consent containers
    const selectors = [
        '#onetrust-banner-sdk', '#onetrust-consent-sdk',
        '.cookie-banner', '.cookie-consent', '.cookie-notice',
        '#cookie-banner', '#cookie-consent', '#cookie-notice',
        '#CybotCookiebotDialog', '.cc-banner', '#cc-main',
        '[class*="cookie-popup"]', '[class*="cookie-overlay"]',
        '[class*="consent-banner"]', '[class*="gdpr"]',
        '[id*="cookie-popup"]', '[id*="cookie-overlay"]',
        '[id*="consent-banner"]',
    ];
    let removed = 0;
    for (const sel of selectors) {
        document.querySelectorAll(sel).forEach(el => {
            el.remove();
            removed++;
        });
    }

    // Strategy 3: Remove fixed overlays with high z-index
    document.querySelectorAll('[class*="overlay"], [class*="backdrop"]').forEach(el => {
        const style = getComputedStyle(el);
        if (style.position === 'fixed' && parseFloat(style.zIndex) > 999) {
            el.remove();
            removed++;
        }
    });

    // Strategy 4: Restore body scroll
    document.body.style.overflow = '';
    document.documentElement.style.overflow = '';

    return removed > 0 ? 'removed_' + removed : 'no_overlay_found';
})()
"""


async def cookie_dismisser_node(state: AgentState) -> dict:
    """Attempt to dismiss cookie popups via JS injection. Zero LLM."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    br = state.browser
    new_count = state.guard_dismiss_count + 1

    try:
        result = await browser_api.execute_js(COOKIE_DISMISS_JS)
        msg = result.get("message", "")
        print(f"  [cookie_dismisser] Result: {msg}")
        br.add_log(
            action={"action": "js_inject", "_source": "cookie_dismisser"},
            response=msg,
            status="ok",
        )
    except Exception as e:
        print(f"  [cookie_dismisser] JS injection failed: {e}")
        br.add_log(
            action={"action": "js_inject", "_source": "cookie_dismisser"},
            response=str(e),
            status="error",
        )

    return {"browser": br, "guard_dismiss_count": new_count}
