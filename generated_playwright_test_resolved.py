from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        page.goto(r'https://www.google.com/')
        page.fill(r'input[name=q]', r'biggest cities in the USA')
        try:
            page.locator(r'input[name=q]').press('Enter')
        except Exception:
            page.keyboard.press('Enter')
        assert 'Wikipedia' in (page.locator(r'text=Wikipedia').inner_text() if page.locator(r'text=Wikipedia').count()>0 else page.text_content('body')), 'Assertion failed: Wikipedia'
        assert 'World population review' in (page.locator(r'text=World population review').inner_text() if page.locator(r'text=World population review').count()>0 else page.text_content('body')), 'Assertion failed: World population review'
        assert 'Britannica' in (page.locator(r'text=Britannica').inner_text() if page.locator(r'text=Britannica').count()>0 else page.text_content('body')), 'Assertion failed: Britannica'
        assert 'NYC.gov' in (page.locator(r'text=NYC.gov').inner_text() if page.locator(r'text=NYC.gov').count()>0 else page.text_content('body')), 'Assertion failed: NYC.gov'
        page.click(r'text=Wikipedia')
        # TODO: replace DESCRIBE_TARGET for step 9 with a real selector
        # step 9: assert DESCRIBE_TARGET

if __name__ == '__main__':
    run()