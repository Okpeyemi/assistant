import asyncio
import base64
import re
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright
from typing import Optional


class BrowserManager:
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="fr-FR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = await self._context.new_page()

    async def navigate(self, url: str) -> bool:
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1.5)
            return True
        except Exception as e:
            print(f"Navigation error: {e}")
            return False

    async def take_screenshot(self) -> str:
        try:
            screenshot = await self.page.screenshot(type="jpeg", quality=65)
            return base64.b64encode(screenshot).decode()
        except Exception:
            return ""

    async def get_page_info(self) -> dict:
        try:
            info = await self.page.evaluate("""() => {
                const getLabel = (el) => {
                    if (el.id) {
                        const lbl = document.querySelector(`label[for="${el.id}"]`);
                        if (lbl) return lbl.textContent.trim();
                    }
                    const parent = el.closest('label');
                    if (parent) return parent.textContent.replace(el.value || '', '').trim();
                    // Try aria-labelledby
                    const lblId = el.getAttribute('aria-labelledby');
                    if (lblId) {
                        const lbl = document.getElementById(lblId);
                        if (lbl) return lbl.textContent.trim();
                    }
                    return el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
                };

                const getBestSelector = (el, idx) => {
                    if (el.id) return `#${el.id}`;
                    const fcn = el.getAttribute('formcontrolname');
                    if (fcn) return `[formcontrolname="${fcn}"]`;
                    if (el.name) return `[name="${el.name}"]`;
                    if (el.placeholder) return `[placeholder="${el.placeholder}"]`;
                    // Positional fallback: nth visible input
                    return `__input_index_${idx}`;
                };

                const mapInput = (el, idx) => {
                    const base = {
                        type: el.type || el.tagName.toLowerCase(),
                        name: el.name || '',
                        id: el.id || '',
                        formcontrolname: el.getAttribute('formcontrolname') || '',
                        placeholder: el.placeholder || '',
                        currentValue: el.value || '',
                        required: el.required || false,
                        label: getLabel(el),
                        selector: getBestSelector(el, idx),
                        visible: el.offsetParent !== null,
                    };
                    // For <select>, expose available options so the agent knows what values to use
                    if (el.tagName === 'SELECT') {
                        base.options = Array.from(el.options)
                            .filter(o => o.value)
                            .slice(0, 30)
                            .map(o => ({ value: o.value, text: o.text.trim() }));
                    }
                    return base;
                };

                // Scan forms
                const forms = Array.from(document.querySelectorAll('form')).map(form => ({
                    id: form.id || '',
                    action: form.action || '',
                    inputs: Array.from(
                        form.querySelectorAll('input:not([type="hidden"]), select, textarea')
                    ).map((el, i) => mapInput(el, i)),
                }));

                // Also scan ALL visible inputs (Angular often uses [formGroup] on div, no <form>)
                const allInputs = Array.from(
                    document.querySelectorAll('input:not([type="hidden"]), select, textarea')
                ).filter(el => el.offsetParent !== null)
                 .slice(0, 20)
                 .map((el, i) => mapInput(el, i));

                const allBtns = Array.from(
                    document.querySelectorAll('button, [type="submit"], [role="button"]')
                );
                const buttons = allBtns.slice(0, 15).map((btn, i) => {
                    let sel = '';
                    if (btn.id) sel = `#${btn.id}`;
                    else if (btn.getAttribute('data-testid')) sel = `[data-testid="${btn.getAttribute('data-testid')}"]`;
                    else if (btn.className && typeof btn.className === 'string') {
                        const cls = btn.className.trim().split(/\s+/).find(c => c.length > 3 && !/ng-|mat-|cdk-/.test(c));
                        if (cls) sel = `button.${cls}`;
                    }
                    if (!sel) sel = `__btn_index_${i}`;
                    return {
                        text: btn.textContent?.trim().substring(0, 80) || '',
                        id: btn.id || '',
                        type: btn.type || '',
                        disabled: btn.disabled || btn.getAttribute('disabled') !== null || btn.getAttribute('aria-disabled') === 'true',
                        selector: sel,
                        index: i,
                    };
                });

                const links = Array.from(document.querySelectorAll('a[href]'))
                    .slice(0, 20)
                    .map(a => ({
                        text: a.textContent?.trim().substring(0, 80) || '',
                        href: a.href || '',
                    }));

                return {
                    title: document.title,
                    url: window.location.href,
                    forms,
                    allInputs,
                    buttons,
                    links,
                    bodyText: document.body?.innerText?.substring(0, 2000) || '',
                };
            }""")
            return info
        except Exception as e:
            print(f"get_page_info error: {e}")
            return {}

    async def click_by_text(self, text: str) -> bool:
        url_before = self.page.url

        # 0. If text matches an <a> with href, navigate directly (Angular SPA fix)
        try:
            href = await self.page.evaluate(
                """([txt]) => {
                    const links = Array.from(document.querySelectorAll('a'));
                    const link = links.find(a => (a.textContent || '').trim().includes(txt));
                    return (link && link.href && link.href.startsWith('http')) ? link.href : null;
                }""",
                [text],
            )
            if href:
                await self.page.goto(href, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(1.5)
                print(f"click_by_text: navigated to href {href!r} for text {text!r} (Angular SPA)")
                return True
        except Exception:
            pass

        # 1. Clic normal
        try:
            await self.page.get_by_text(text, exact=False).first.click(timeout=5000)
            await asyncio.sleep(1.2)
            if self.page.url != url_before:
                return True
        except Exception:
            pass
        # 2. Force click (bypasse la vérification de visibilité)
        try:
            await self.page.get_by_text(text, exact=False).first.click(
                force=True, timeout=3000
            )
            await asyncio.sleep(1.2)
            if self.page.url != url_before:
                return True
        except Exception:
            pass
        # 3. JavaScript click via goto (pour les liens Angular)
        try:
            navigated = await self.page.evaluate(
                """([txt]) => {
                    const links = Array.from(document.querySelectorAll('a'));
                    const link = links.find(a => a.textContent.trim().includes(txt));
                    if (link && link.href) { window.location.href = link.href; return true; }
                    return false;
                }""",
                [text],
            )
            if navigated:
                await asyncio.sleep(2.0)
                return True
        except Exception:
            pass
        # 4. JavaScript click direct sur bouton/clickable (Angular, Material, etc.)
        try:
            clicked = await self.page.evaluate(
                """([txt]) => {
                    const candidates = Array.from(document.querySelectorAll(
                        'button, [role="button"], input[type="submit"], input[type="button"], ' +
                        'a, mat-button, mat-raised-button, [matbutton], [mat-button], ' +
                        '[mat-raised-button], [mat-flat-button], [mat-stroked-button]'
                    ));
                    const el = candidates.find(e => {
                        const t = (e.textContent || e.value || '').trim();
                        return t === txt || t.includes(txt);
                    });
                    if (el) {
                        // Fire full click event chain that Angular/Material listens to
                        ['mousedown','mouseup','click'].forEach(evName => {
                            el.dispatchEvent(new MouseEvent(evName, {
                                bubbles: true, cancelable: true, view: window
                            }));
                        });
                        el.click();
                        return true;
                    }
                    return false;
                }""",
                [text],
            )
            if clicked:
                await asyncio.sleep(1.5)
                return True
        except Exception:
            pass
        # 5. Scroll element into view then JS click (last resort for off-screen buttons)
        try:
            clicked = await self.page.evaluate(
                """([txt]) => {
                    const all = Array.from(document.querySelectorAll('*'));
                    const el = all.find(e =>
                        ['BUTTON','A','INPUT'].includes(e.tagName) &&
                        (e.textContent || e.value || '').trim().includes(txt)
                    );
                    if (el) {
                        el.scrollIntoView({ behavior: 'instant', block: 'center' });
                        el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        return true;
                    }
                    return false;
                }""",
                [text],
            )
            if clicked:
                await asyncio.sleep(1.5)
                return True
        except Exception:
            pass
        print(f"click_by_text all fallbacks failed ({text!r})")
        return False

    async def click_by_selector(self, selector: str) -> bool:
        # Handle __btn_index_N pseudo-selector (buttons without id/class)
        btn_idx_match = re.match(r'__btn_index_(\d+)', selector)
        if btn_idx_match:
            idx = int(btn_idx_match.group(1))
            try:
                clicked = await self.page.evaluate(
                    """([idx]) => {
                        const btn = Array.from(document.querySelectorAll(
                            'button, [type="submit"], [role="button"]'
                        ))[idx];
                        if (btn) {
                            ['mousedown','mouseup','click'].forEach(ev =>
                                btn.dispatchEvent(new MouseEvent(ev, { bubbles: true, cancelable: true }))
                            );
                            btn.click();
                            return true;
                        }
                        return false;
                    }""",
                    [idx],
                )
                if clicked:
                    await asyncio.sleep(1.0)
                    return True
            except Exception:
                pass

        # Detect element type and href upfront — determines strategy
        try:
            el_info = await self.page.evaluate(
                """([sel]) => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    const a = el.tagName === 'A' ? el : el.closest('a');
                    return {
                        tag: el.tagName,
                        isLink: !!a,
                        href: a?.href || null,
                    };
                }""",
                [selector],
            )
        except Exception:
            el_info = None

        # If it's a link with an href → navigate directly (Angular SPA)
        if el_info and el_info.get('isLink') and el_info.get('href', '').startswith('http'):
            try:
                href = el_info['href']
                await self.page.goto(href, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(1.5)
                print(f"click_by_selector: navigated to href {href!r} (Angular SPA)")
                return True
            except Exception as e:
                print(f"click_by_selector: goto failed ({e}), falling through")

        # 1. Normal click (for buttons / non-link elements)
        try:
            await self.page.click(selector, timeout=5000)
            await asyncio.sleep(1.0)
            return True
        except Exception:
            pass
        # 2. Force click
        try:
            await self.page.click(selector, force=True, timeout=3000)
            await asyncio.sleep(1.0)
            return True
        except Exception:
            pass
        # 3. JavaScript full event dispatch
        try:
            result = await self.page.evaluate(
                """([sel]) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    ['mousedown', 'mouseup', 'click'].forEach(ev =>
                        el.dispatchEvent(new MouseEvent(ev, { bubbles: true, cancelable: true, view: window }))
                    );
                    el.click();
                    return true;
                }""",
                [selector],
            )
            if result:
                await asyncio.sleep(1.0)
                return True
        except Exception:
            pass
        print(f"click_by_selector all fallbacks failed ({selector!r})")
        return False

    async def fill_field(self, selector: str, value: str) -> bool:
        """Fill a form field. Works with standard HTML, Angular, and React forms."""

        # ── Strategy 0: <select> elements — set value by option value OR text ───
        try:
            selected = await self.page.evaluate(
                """([sel, val]) => {
                    const el = document.querySelector(sel);
                    if (!el || el.tagName !== 'SELECT') return null;
                    // Match option by value (exact), then by text (case-insensitive)
                    const opts = Array.from(el.options);
                    const match = opts.find(o => o.value === val)
                        || opts.find(o => o.value.toLowerCase() === val.toLowerCase())
                        || opts.find(o => o.text.trim().toLowerCase() === val.toLowerCase())
                        || opts.find(o => o.text.trim().toLowerCase().includes(val.toLowerCase()));
                    if (match) {
                        el.value = match.value;
                    } else if (opts.some(o => o.value === val)) {
                        el.value = val;
                    } else {
                        return false;  // value not in options
                    }
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('input',  { bubbles: true }));
                    return el.value;
                }""",
                [selector, value],
            )
            if selected is not None and selected is not False:
                await asyncio.sleep(0.3)
                print(f"fill select ({selector!r}): set to {selected!r}")
                return True
            if selected is False:
                print(f"fill select ({selector!r}): option {value!r} not found in options")
        except Exception as e:
            print(f"fill select ({selector!r}): {e}")

        # ── Strategy 1: click + keyboard type, with value verification ────────────
        # Try real Playwright click first (works for visible elements),
        # fall back to JS focus. Verifies value actually stuck.
        # For masked date inputs: retries without separators (30072004 vs 30-07-2004).
        try:
            # Focus the element
            clicked = False
            try:
                await self.page.click(selector, timeout=2000)
                clicked = True
            except Exception:
                pass
            if not clicked:
                await self.page.evaluate(
                    """([sel]) => {
                        const el = document.querySelector(sel);
                        const inp = ['INPUT','TEXTAREA'].includes(el?.tagName) ? el
                            : el?.querySelector('input, textarea') || el;
                        inp?.focus();
                    }""",
                    [selector],
                )
            await asyncio.sleep(0.15)

            # Try the value as-is, then without date separators (for masked fields)
            stripped = re.sub(r'(?<=\d)[-/.](?=\d)', '', value)  # remove separators between digits
            candidates = [value] if value == stripped else [value, stripped]
            for attempt in candidates:
                await self.page.keyboard.press("Control+a")
                await self.page.keyboard.press("Delete")
                await self.page.keyboard.type(attempt, delay=50)
                await asyncio.sleep(0.4)
                actual = await self.page.evaluate(
                    "([sel]) => document.querySelector(sel)?.value || ''",
                    [selector],
                )
                if actual:
                    await self.page.keyboard.press("Tab")
                    await asyncio.sleep(0.3)
                    print(f"fill s1 ok ({selector!r}): typed={attempt!r} → actual={actual!r}")
                    return True
                print(f"fill s1 no value ({selector!r}): tried={attempt!r}")
        except Exception as e:
            print(f"fill s1 ({selector!r}): {e}")

        # ── Strategy 2: Playwright get_by_label / get_by_placeholder ───────────
        # Works when the CSS selector attribute is absent but label/placeholder matches.
        # Extract hint text from selector, e.g. [formcontrolname="nom"] → "nom"
        hint = ""
        m = re.search(r'["\']([^"\']+)["\']', selector)
        if m:
            hint = m.group(1)

        if hint:
            # Try label-based (exact=False for partial match)
            for variant in [hint, hint.capitalize(), hint.upper()]:
                try:
                    loc = self.page.get_by_label(variant, exact=False).first
                    await loc.fill(value, timeout=2000)
                    await asyncio.sleep(0.4)
                    print(f"fill s2 label ({selector!r}): matched label={variant!r}")
                    return True
                except Exception:
                    pass
            # Try placeholder-based
            for variant in [hint, hint.capitalize()]:
                try:
                    loc = self.page.get_by_placeholder(variant, exact=False).first
                    await loc.fill(value, timeout=2000)
                    await asyncio.sleep(0.4)
                    print(f"fill s2 placeholder ({selector!r}): matched placeholder={variant!r}")
                    return True
                except Exception:
                    pass

        # ── Strategy 3: Angular native setter + event dispatch ──────────────────
        # Directly sets the DOM value and fires Angular's DefaultValueAccessor events.
        try:
            ok = await self.page.evaluate(
                """([sel, val]) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    const input = ['INPUT','TEXTAREA','SELECT'].includes(el.tagName)
                        ? el
                        : (el.querySelector('input, textarea, select') || el);
                    const desc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value');
                    if (desc?.set) desc.set.call(input, val);
                    else input.value = val;
                    ['focus','input','change','blur'].forEach(t =>
                        input.dispatchEvent(new Event(t, { bubbles: true, cancelable: true }))
                    );
                    return true;
                }""",
                [selector, value],
            )
            if ok:
                await asyncio.sleep(0.3)
                return True
        except Exception as e:
            print(f"fill s3 ({selector!r}): {e}")

        # ── Strategy 4: Playwright fill (standard last resort) ──────────────────
        try:
            await self.page.fill(selector, value, timeout=5000)
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            print(f"fill s4 ({selector!r}): {e}")

        return False

    async def current_url(self) -> str:
        try:
            return self.page.url
        except Exception:
            return ""

    async def close(self):
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
