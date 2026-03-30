"""
scrape_all.py — GitHub Actions 用的完整采集脚本
采集 Contact Database Growth 90天历史 + 全部 Segment + Leads
输出: data.json (合并历史数据)
"""
import json, os, sys, re, time, urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright

TODAY = datetime.now().strftime("%Y-%m-%d")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
DATA_JSON = os.path.join(REPO_DIR, "data.json")

LOGIN_URL = "https://login.emarsys.net/bootstrap.php?r=customer/Login"
ACCOUNT = os.environ.get("EMARSYS_ACCOUNT", "dji")
USERNAME = os.environ.get("EMARSYS_USERNAME", "")
PASSWORD = os.environ.get("EMARSYS_PASSWORD", "")

SEGMENTS = [
    ("Auto-APAC-All", "apac_sub"),
    ("Auto-NA 北美周会用", "na_sub"),
    ("Auto-EU-All", "eu_sub"),
    ("Auto-APAC-Active", "apac_active"),
    ("Auto-NA-Active", "na_active"),
    ("Auto-EU-Active", "eu_active"),
    ("Auto-PR/CA-Active", "na_ex_us_active"),
    ("13 months Auto-All", "global_active"),
    ("Inactive lead", "inactive_lead"),
]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def emarsys_login(page):
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(5000)
    page.fill("input[name='company']", ACCOUNT)
    page.click("button:has-text('Continue')")
    page.wait_for_timeout(5000)
    page.fill("input[name='username']", USERNAME)
    page.fill("input[type='password']", PASSWORD)
    page.click("button:has-text('Login')")
    page.wait_for_load_state("domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    try:
        a = page.locator("text=Already logged in").first
        if a.is_visible():
            page.click("text=Click here")
            page.wait_for_timeout(5000)
            if "Login" in page.url:
                page.fill("input[name='company']", ACCOUNT)
                page.click("button:has-text('Continue')")
                page.wait_for_timeout(5000)
                page.fill("input[name='username']", USERNAME)
                page.fill("input[type='password']", PASSWORD)
                page.click("button:has-text('Login')")
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                page.wait_for_timeout(8000)
    except:
        pass
    for _ in range(3):
        try:
            for s in ["button:has-text('Close')", "text=Close", "[aria-label='Close']"]:
                b = page.locator(s).first
                if b.is_visible(timeout=2000):
                    b.click()
                    page.wait_for_timeout(1500)
                    break
        except:
            pass
    return page.url


def go_segments(page, base_url):
    parsed = urllib.parse.urlparse(base_url)
    params = urllib.parse.parse_qs(parsed.query)
    sid = params.get('session_id', [''])[0]
    base = base_url.split('?')[0].rsplit('/', 1)[0] + '/'
    page.goto(f"{base}bootstrap.php?session_id={sid}&r=segment/list",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)


def calc_segment(page, name):
    s = page.locator("input[placeholder='Search'], input[type='search']").first
    s.click(); s.fill(""); page.wait_for_timeout(500); s.fill(name); page.wait_for_timeout(5000)
    rows = page.locator("tr").all()
    target = None
    for r in rows:
        try:
            c = r.locator("td").all()
            if c and c[0].inner_text().strip() == name:
                target = r; break
        except: continue
    if not target:
        target = page.locator(f"tr:has-text('{name}')").first
    target.hover(); page.wait_for_timeout(1500)
    try: target.locator("[title='Edit'],[aria-label='Edit']").first.click()
    except:
        try: target.locator("td:last-child a, td:last-child svg").all()[1].click()
        except: target.click()
    page.wait_for_load_state("domcontentloaded", timeout=60000); page.wait_for_timeout(5000)
    for label in ["Save and Calculate", "Calculate"]:
        try:
            btn = page.locator(f"text='{label}'").first
            if btn.is_visible(timeout=3000): btn.click(); break
        except: continue
    t0 = time.time()
    while time.time() - t0 < 300:
        page.wait_for_timeout(5000)
        try:
            if page.locator("text=Calculated at").first.is_visible():
                ll = page.locator(".e-loading,.e-spinner,[class*='loading']").all()
                if not any(x.is_visible() for x in ll if x): break
        except: pass
    txt = page.inner_text("body")
    m = re.search(r'[Cc]ontacts with [Ee]mail [Oo]pt-?in[:\s]*([\d,]+)', txt)
    if m: return int(m.group(1).replace(",", ""))
    m2 = re.search(r'[Tt]otal [Cc]ontacts in [Ss]egment[:\s]*([\d,]+)', txt)
    if m2: return int(m2.group(1).replace(",", ""))
    return None


def calc_prca(page):
    s = page.locator("input[placeholder='Search'], input[type='search']").first
    s.click(); s.fill(""); page.wait_for_timeout(500); s.fill("Auto-PR/CA"); page.wait_for_timeout(5000)
    rows = page.locator("tr").all()
    target = None
    for r in rows:
        text = r.inner_text()
        if 'Auto-PR/CA' in text and 'Active' not in text:
            target = r; break
    if not target: return None
    target.hover(); page.wait_for_timeout(1500)
    try: target.locator("[title='Edit'],[aria-label='Edit']").first.click()
    except:
        try: target.locator("td:last-child a, td:last-child svg").all()[1].click()
        except: target.click()
    page.wait_for_load_state("domcontentloaded", timeout=60000); page.wait_for_timeout(5000)
    for label in ["Save and Calculate", "Calculate"]:
        try:
            btn = page.locator(f"text='{label}'").first
            if btn.is_visible(timeout=3000): btn.click(); break
        except: continue
    t0 = time.time()
    while time.time() - t0 < 300:
        page.wait_for_timeout(5000)
        try:
            if page.locator("text=Calculated at").first.is_visible():
                ll = page.locator(".e-loading,.e-spinner,[class*='loading']").all()
                if not any(x.is_visible() for x in ll if x): break
        except: pass
    txt = page.inner_text("body")
    m = re.search(r'[Cc]ontacts with [Ee]mail [Oo]pt-?in[:\s]*([\d,]+)', txt)
    if m: return int(m.group(1).replace(",", ""))
    return None


def scrape_leads(page, base_url):
    parsed = urllib.parse.urlparse(base_url)
    params = urllib.parse.parse_qs(parsed.query)
    sid = params.get('session_id', [''])[0]
    base = base_url.split('?')[0].rsplit('/', 1)[0] + '/'
    page.goto(f"{base}bootstrap.php?session_id={sid}&r=smartinsight/CustomerLifecycle",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(20000)
    page_text = page.inner_text("body")
    m = re.search(r'Leads\s*\n\s*([\d,]+)', page_text)
    if m: return int(m.group(1).replace(",", ""))
    m = re.search(r'Leads\s+([\d,]+)', page_text)
    if m: return int(m.group(1).replace(",", ""))
    for frame in page.frames:
        try:
            ft = frame.inner_text("body", timeout=5000)
            m = re.search(r'Leads\s*\n\s*([\d,]+)', ft)
            if m: return int(m.group(1).replace(",", ""))
        except: pass
    return None


def scrape_global_history(p):
    """Scan Contact Database Growth chart for 90-day history."""
    log("  登录并扫描 Contact Database Growth...")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = ctx.new_page()
    emarsys_login(page)

    # Close popups, scroll to chart
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(3000)
    try:
        page.locator("text=Contact Database Growth").first.scroll_into_view_if_needed()
        page.wait_for_timeout(5000)
    except: pass

    # Scroll step by step
    for scroll_y in range(0, 3000, 300):
        page.evaluate(f"window.scrollTo(0, {scroll_y})")
        page.wait_for_timeout(500)
        try:
            cdg = page.locator("text=Contact Database Growth").first
            if cdg.is_visible(timeout=1000): break
        except: pass
    page.wait_for_timeout(3000)

    cdg_label = page.locator("text=Contact Database Growth").first
    cdg_label.scroll_into_view_if_needed()
    page.wait_for_timeout(5000)
    cdg_box = cdg_label.bounding_box()

    # Find chart SVG
    svgs = page.query_selector_all("svg")
    chart_svg = None
    for svg in svgs:
        box = svg.bounding_box()
        if not box or box['width'] < 300 or box['height'] < 150: continue
        y_dist = box['y'] - cdg_box['y']
        if 50 < y_dist < 500:
            chart_svg = svg; break

    if not chart_svg:
        log("  Chart SVG not found!")
        browser.close()
        return []

    box = chart_svg.bounding_box()
    log(f"  Chart: {box['width']:.0f}x{box['height']:.0f}")

    # Discover tooltip selector
    mid_x = box['x'] + box['width'] * 0.7
    mid_y = box['y'] + box['height'] * 0.4
    page.mouse.move(mid_x, mid_y)
    page.wait_for_timeout(2000)

    tooltip_info = page.evaluate("""
    () => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const text = el.innerText || '';
            if (text.includes('Total Contacts') && text.includes('Available by Email') && text.includes('No opt-in') && text.length < 500) {
                return { tag: el.tagName, className: el.className };
            }
        }
        return null;
    }
    """)

    tooltip_selector = None
    if tooltip_info:
        tooltip_selector = tooltip_info['tag']
        if tooltip_info['className']:
            tooltip_selector = f"{tooltip_info['tag']}.{tooltip_info['className'].strip().split()[0]}"

    # Scan
    plot_left = box['x'] + 75
    plot_right = box['x'] + box['width'] - 5
    plot_y = box['y'] + box['height'] * 0.4
    step = max(1.5, (plot_right - plot_left) / 500)

    daily_data = {}
    last_date = None
    x = plot_left

    while x <= plot_right:
        page.mouse.move(x, plot_y)
        page.wait_for_timeout(60)

        if tooltip_selector:
            tt = page.evaluate(f"""
            () => {{
                const els = document.querySelectorAll('{tooltip_selector}');
                for (const el of els) {{
                    const t = el.innerText || '';
                    if (t.includes('Total Contacts') && t.includes('Available by Email') && t.length < 500) return t;
                }}
                return null;
            }}
            """)
        else:
            tt = page.evaluate("""
            () => {
                const all = document.querySelectorAll('div, table');
                for (const el of all) {
                    const t = el.innerText || '';
                    if (t.includes('Total Contacts') && t.includes('Available by Email') && t.includes('No opt-in') && t.length < 500) return t;
                }
                return null;
            }
            """)

        if tt:
            dm = re.search(r'(\d{2})-(\d{2})-(\d{4})', tt)
            if dm:
                m, d, y = dm.groups()
                ds = f"{y}-{m}-{d}"
                if ds != last_date:
                    last_date = ds
                    rec = {"date": ds}

                    def pv(text, label, min_v=0):
                        nums = re.findall(r'[\d,]+', text.split(label)[-1])
                        for n in nums:
                            v = int(n.replace(",", ""))
                            if v > min_v: return v
                        return None

                    for line in tt.replace('\t', '  ').split("\n"):
                        line = line.strip()
                        if "Total Contacts" in line: rec["total_contacts"] = pv(line, "Total Contacts", 10000)
                        elif "Available by Email" in line: rec["available_by_email"] = pv(line, "Available by Email", 10000)
                        elif "Invalid email address" in line: rec["invalid_email"] = pv(line, "Invalid email address", 0)
                        elif "Missing email" in line: rec["missing_email"] = pv(line, "Missing email", 0)
                        elif "No opt-in" in line: rec["no_opt_in"] = pv(line, "No opt-in", 0)

                    if rec.get("total_contacts") and rec.get("available_by_email"):
                        rec["unavailable_by_email"] = rec["total_contacts"] - rec["available_by_email"]

                    if rec.get("available_by_email"):
                        daily_data[ds] = rec
        x += step

    browser.close()
    result = sorted(daily_data.values(), key=lambda d: d['date'])
    log(f"  Scanned {len(result)} days: {result[0]['date']}~{result[-1]['date']}" if result else "  No data!")
    return result


def main():
    if not USERNAME or not PASSWORD:
        log("ERROR: EMARSYS_USERNAME / EMARSYS_PASSWORD not set!")
        sys.exit(1)

    log("=" * 60)
    log(f"  Emarsys Dashboard Auto Update — {TODAY}")
    log("=" * 60)

    # === Step 1: Global subscriber history ===
    log("\n[Step 1] Contact Database Growth (90 days)...")
    with sync_playwright() as p:
        global_history = scrape_global_history(p)

    # === Step 2: Segments (each with independent login) ===
    log(f"\n[Step 2] Segments ({len(SEGMENTS) + 2} items, independent logins)...")
    segment_data = {"date": TODAY}

    with sync_playwright() as p:
        for name, key in SEGMENTS:
            log(f"  [{name}]")
            try:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
                page = ctx.new_page()
                t0 = time.time()
                url = emarsys_login(page)
                go_segments(page, url)
                v = calc_segment(page, name)
                if v:
                    segment_data[key] = v
                    log(f"    -> {v:,} ({int(time.time()-t0)}s)")
                else:
                    log(f"    -> FAILED ({int(time.time()-t0)}s)")
                browser.close()
            except Exception as e:
                log(f"    -> ERROR: {e}")
                try: browser.close()
                except: pass

        # Auto-PR/CA
        log(f"  [Auto-PR/CA] (dedicated)")
        try:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = ctx.new_page()
            t0 = time.time()
            url = emarsys_login(page)
            go_segments(page, url)
            v = calc_prca(page)
            if v:
                segment_data["na_ex_us_sub"] = v
                log(f"    -> {v:,} ({int(time.time()-t0)}s)")
            else:
                log(f"    -> FAILED ({int(time.time()-t0)}s)")
            browser.close()
        except Exception as e:
            log(f"    -> ERROR: {e}")
            try: browser.close()
            except: pass

        # Leads
        log(f"  [Leads]")
        try:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = ctx.new_page()
            t0 = time.time()
            url = emarsys_login(page)
            v = scrape_leads(page, url)
            if v:
                segment_data["leads"] = v
                log(f"    -> {v:,} ({int(time.time()-t0)}s)")
            else:
                log(f"    -> FAILED ({int(time.time()-t0)}s)")
            browser.close()
        except Exception as e:
            log(f"    -> ERROR: {e}")
            try: browser.close()
            except: pass

    collected = len([k for k in segment_data if k != "date"])
    log(f"  Collected {collected}/12 fields")

    # === Step 3: Build data.json ===
    log("\n[Step 3] Building data.json...")

    # Load existing data to preserve history
    segs = {}
    if os.path.exists(DATA_JSON):
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            old = json.load(f)
        for d in old:
            if d.get("apac_sub") is not None:
                segs[d["date"]] = {k: d[k] for k in [
                    "apac_sub", "na_sub", "eu_sub", "na_ex_us_sub", "leads", "inactive_lead",
                    "apac_active", "na_active", "eu_active", "na_ex_us_active", "global_active"
                ] if d.get(k) is not None}

    # Add today
    if collected > 5:
        segs[TODAY] = {k: v for k, v in segment_data.items() if k != "date"}

    # Build
    nf = {k: None for k in ["apac_sub", "na_sub", "eu_sub", "na_ex_us_sub", "leads",
                              "inactive_lead", "apac_active", "na_active", "eu_active",
                              "na_ex_us_active", "global_active"]}
    data = []
    for r in global_history:
        e = {"date": r["date"], "total_contacts": r.get("total_contacts"),
             "available_by_email": r.get("available_by_email"),
             "unavailable_by_email": r.get("unavailable_by_email"),
             "no_opt_in": r.get("no_opt_in"), "invalid_email": r.get("invalid_email"),
             "missing_email": r.get("missing_email"), **nf}
        if r["date"] in segs:
            e.update(segs[r["date"]])
        data.append(e)

    dates = {d["date"] for d in data}
    for sd, sv in segs.items():
        if sd not in dates:
            e = {"date": sd, "total_contacts": None, "available_by_email": None,
                 "unavailable_by_email": None, "no_opt_in": None, "invalid_email": None,
                 "missing_email": None, **nf}
            e.update(sv)
            data.append(e)

    data.sort(key=lambda d: d["date"])

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    sc = sum(1 for d in data if d.get("apac_sub") is not None)
    log(f"  data.json: {len(data)} records, {sc} with segment, {data[0]['date']}~{data[-1]['date']}")
    log("\nDone!")


if __name__ == "__main__":
    main()
