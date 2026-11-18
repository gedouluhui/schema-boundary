"""Optional report browser audit using installed Edge and Playwright.

Run with PYTHONPATH=src using a Python that has Playwright; it is not a runtime dependency.
"""
import json
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright
from schema_boundary.report import render_html

ROOT=Path(__file__).resolve().parents[1]


def main():
    checks=[]
    def check(name,actual):
        if not actual: raise AssertionError(name)
        checks.append(name)
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as temp:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        version=browser.version
        ctx=browser.new_context(viewport={'width':1280,'height':1000})
        page=ctx.new_page(); errors=[]; external=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http://','https://')) else None)
        page.goto((ROOT/'docs/demo/report.html').as_uri())
        check('actual counterexample displayed','"query": "a"' in page.locator('.witness').inner_text() or '"query":"a"' in page.locator('.witness').inner_text())
        check('synthetic example explicit','Synthetic search-tool contract' in page.locator('body').inner_text())
        check('finite scope visible',page.get_by_role('heading',name='Finite domain').is_visible())
        check('independent validation visible','Source accepts' in page.locator('.flow').inner_text() and 'Target rejects' in page.locator('.flow').inner_text())
        page.locator('summary').first.focus(); page.keyboard.press('Enter')
        check('keyboard expands domain details',page.locator('details').first.get_attribute('open') is not None)
        page.keyboard.press('Enter')
        for width in (1280,768,360):
            page.set_viewport_size({'width':width,'height':1000})
            check(f'no horizontal document overflow {width}',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        page.screenshot(path=str(ROOT/'artifacts/browser-mobile.png'),full_page=True)
        page.set_viewport_size({'width':1280,'height':1000}); page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ROOT/'docs/demo/preview.png'),full_page=True)
        for status in ('bounded-compatible','empty-source','unknown','error'):
            f=Path(temp)/(status+'.html')
            f.write_text(render_html({'status':status,'reason':'fixture error or bound','domain':None}),encoding='utf8')
            page.goto(f.as_uri())
            check(status+' does not show verified witness',page.locator('.flow').count()==0)
        attack='<img src=x onerror="window.injected=1">'
        f=Path(temp)/'hostile.html'
        f.write_text(render_html({'status':'unknown','reason':attack,'domain':{'alphabet':attack}}),encoding='utf8')
        page.goto(f.as_uri())
        check('malicious text remains text',attack in page.locator('body').inner_text() and page.locator('img').count()==0)
        check('no injected script effect',page.evaluate('window.injected === undefined'))
        check('no external network',not external)
        check('no page exceptions',not errors)
        browser.close()
    result={'browser':version,'checks':checks,'passed':len(checks),'scope':'isolated headless Edge; synthetic report data; not screen-reader or real mobile certification'}
    (ROOT/'artifacts/browser-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
