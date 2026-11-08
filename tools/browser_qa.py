"""Exercise real participant and staff journeys against an isolated demo database."""
import json
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.test-deps'))
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server, WSGIRequestHandler
from app import create_app

OUT = ROOT / 'test-results'
OUT.mkdir(exist_ok=True)
database = OUT / 'browser.sqlite3'
if database.exists():
    database.unlink()
app = create_app({'DATABASE': str(database), 'SECRET_KEY': 'isolated-browser-test', 'TESTING': True})
class QuietHandler(WSGIRequestHandler):
    def log(self, _type, _message, *args):
        pass


server = make_server('127.0.0.1', 5055, app, threaded=True, request_handler=QuietHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:5055/'
errors = []
checks = []


def check(condition, message):
    assert condition, message
    checks.append(message)


def no_overflow(page, label):
    check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), label + ' has no page-level horizontal overflow')


def login(page, role):
    page.goto(BASE + '#access/' + ('staff' if role != 'participant' else ''))
    page.locator('[data-demo-account="' + role + '"]').click()
    page.get_by_role('button', name='Sign in', exact=True).click()
    page.wait_for_selector('.staff-content' if role != 'participant' else '.home-main')


def logout(page):
    page.get_by_role('button', name='Sign out', exact=True).click()
    page.locator('#dialog').get_by_role('button', name='Sign out', exact=True).click()
    page.wait_for_selector('.home-main')


try:
    with sync_playwright() as p:
        configured = os.environ.get('BETWEEN_BROWSER')
        installed = Path(os.environ.get('LOCALAPPDATA', '')) / 'ms-playwright' / 'chromium-1243' / 'chrome-win64' / 'chrome.exe'
        options = {'headless': True}
        if configured or installed.exists():
            options['executable_path'] = configured or str(installed)
        browser = p.chromium.launch(**options)
        context = browser.new_context(viewport={'width':1440,'height':1050}, reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.goto(BASE)
        page.wait_for_selector('.home-main')
        page.evaluate('document.fonts.ready')
        page.locator('.skip-link').focus()
        page.keyboard.press('Enter')
        check(page.locator('#main').evaluate('(element) => element === document.activeElement'), 'Keyboard skip link focuses content without changing the page')
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(OUT / 'home-desktop.png'), full_page=True)
        check(page.get_by_role('heading', name='Understand. Connect. Follow up.').is_visible(), 'Clinician-focused home renders')
        check(page.locator('.demo-strip').count()==0,'Top workspace bar is removed')
        page.get_by_role('link',name='Open clinician workspace',exact=True).click()
        page.wait_for_selector('#login-form')
        check(page.locator('[data-demo-account="counsellor"]').is_visible(),'Primary home action opens clinician access')
        page.goto(BASE+'#privacy')
        page.wait_for_selector('.info-details')
        privacy_detail=page.locator('.info-details').filter(has=page.get_by_text('Roles and confidentiality',exact=True))
        check(not privacy_detail.locator('.info-details-body').is_visible(),'Privacy explanations are collapsed by default')
        privacy_detail.locator('summary').focus()
        page.keyboard.press('Enter')
        check(privacy_detail.locator('.info-details-body').is_visible(),'Full privacy information remains keyboard accessible')
        check('pseudonymous' in privacy_detail.inner_text(),'Privacy detail retains identity and confidentiality limits')
        page.goto(BASE+'#about')
        page.wait_for_selector('.info-details')
        page.get_by_text('Current tools and availability',exact=True).click()
        check(page.get_by_text('PHQ-9, GAD-7 and WEMWBS are not administered or scored.',exact=False).is_visible(),'Tool availability and permissions remain accessible')
        page.goto(BASE)
        page.wait_for_selector('.home-main')
        visual_requests=[]
        page.on('request',lambda req: visual_requests.append(req.url) if '/api/' in req.url else None)
        page.get_by_role('button',name='Offline',exact=True).click()
        check(page.locator('[data-opus-stage]').get_attribute('data-opus-mode')=='offline','Interactive scene changes to offline')
        page.screenshot(path=str(OUT/'home-offline.png'),full_page=True)
        page.locator('[data-opus-slider]').focus()
        page.keyboard.press('Home')
        check(page.locator('[data-opus-stage]').get_attribute('data-opus-mode')=='online','Interactive scene supports keyboard range navigation')
        page.get_by_role('button',name='Between',exact=True).click()
        check(page.locator('[data-opus-stage]').get_attribute('data-opus-mode')=='between','Interactive scene provides an intermediate state')
        check(not visual_requests,'Interactive scene sends no assessment data')
        page.get_by_role('button',name='Online',exact=True).click()
        page.evaluate('window.scrollTo(0, 0)')
        no_overflow(page, 'Desktop home')
        page.set_viewport_size({'width':320,'height':850})
        no_overflow(page, '320px home')
        nav_bounds=page.locator('.participant-nav').bounding_box()
        for destination in ('home','assessment','support','privacy'):
            nav_link=page.locator('.participant-nav a[href="#'+destination+'"]').bounding_box()
            check(nav_link['x']>=nav_bounds['x'] and nav_link['x']+nav_link['width']<=nav_bounds['x']+nav_bounds['width']+1,'320px '+destination+' navigation is fully visible')
        page.get_by_role('button',name='Offline',exact=True).click()
        check(page.locator('[data-opus-stage]').get_attribute('data-opus-mode')=='offline','320px interactive scene remains operable')
        page.get_by_role('button',name='Online',exact=True).click()
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(OUT / 'home-mobile.png'), full_page=True)
        for width in (768, 1024):
            page.set_viewport_size({'width':width,'height':900})
            no_overflow(page, f'{width}px home and navigation')
        page.set_viewport_size({'width':390,'height':844})
        page.get_by_role('link', name='Start my assessment', exact=False).click()
        page.get_by_role('button', name='Enter the demo', exact=False).click()
        page.wait_for_selector('#assessment-form')
        page.get_by_role('button', name='Continue', exact=False).click()
        check(page.locator('.error-summary').is_visible(), 'Invalid assessment shows an error summary')
        page.locator('#field-age').fill('16')
        page.locator('#field-consent').check()
        page.locator('#field-privacy').check()
        check(page.locator('#minor-path').is_visible(), 'Minor pathway becomes visible')
        page.locator('#field-guardian').check()
        page.locator('#field-assent').check()
        page.get_by_role('button', name='Continue', exact=False).click()
        page.wait_for_selector('#field-gender')
        check(page.get_by_text('Optional follow-up', exact=True).count() == 0, 'Optional follow-up can be declined without blocking progress')
        page.locator('input[name=gender][value=prefer_not]').check()
        page.locator('input[name=education][value=university]').check()
        page.get_by_role('button', name='Continue', exact=False).click()
        page.wait_for_selector('#field-platforms')
        for key, values in {'platforms':['instagram','youtube'],'daily_time':['1to3'],'passive':['often'],'active':['rarely'],'night':['sometimes'],'cyberbullying':['never'],'regular_count':['2']}.items():
            for value in values:
                page.locator(f'input[name="{key}"][value="{value}"]').check()
        no_overflow(page, '390px assessment')
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(OUT / 'assessment-mobile.png'), full_page=True)
        page.get_by_role('button', name='Save and exit', exact=True).click()
        page.wait_for_selector('.home-main')
        check(page.get_by_role('link', name='Continue my assessment', exact=False).is_visible(), 'Save and exit acknowledged by the server')
        page.get_by_role('link', name='Continue my assessment', exact=False).click()
        page.wait_for_selector('#field-platforms')
        check(page.locator('input[name=night][value=sometimes]').is_checked(), 'Back and resume preserve answers')
        page.get_by_role('button', name='Continue', exact=False).click()
        page.wait_for_selector('.instrument-row')
        check(page.get_by_text('Wellbeing questionnaires are not enabled.', exact=True).is_visible(), 'Unapproved wellbeing instruments remain disabled')
        page.get_by_role('button', name='Review my answers', exact=False).click()
        page.wait_for_selector('.review-heading')
        page.get_by_role('button', name='Submit demo assessment', exact=False).click()
        page.wait_for_selector('.receipt')
        check(page.get_by_role('heading', name='Thank you for sharing.', exact=True).is_visible(), 'Participant receives a plain-language completion summary')
        check(page.get_by_role('heading', name='Waiting for review', exact=True).is_visible(), 'Participant sees their actual review status in plain language')
        check(page.get_by_role('heading', name='What you shared', exact=True).is_visible(), 'Participant sees a summary of their reported habits')
        check(page.get_by_role('heading',name='Assessment result:',exact=False).is_visible(), 'Participant sees the actual model result separately from review status')
        check(page.get_by_role('heading',name='What influenced this result?',exact=True).is_visible(), 'Participant receives a model-derived explanation in plain language')
        check(page.get_by_text("This project's estimate is not a diagnosis.", exact=False).is_visible(), 'Summary explains its limits in plain language')
        check(page.get_by_text('Class probabilities', exact=True).count()==0 and page.get_by_text('Model information', exact=True).count()==0, 'Technical model details stay outside the participant summary')
        check(page.get_by_text('PHQ-9', exact=True).count()==0, 'Uncompleted questionnaires do not clutter the participant summary')
        page.get_by_text('About this assessment', exact=True).click()
        check(page.get_by_text('No one is monitoring these answers or support requests.', exact=False).is_visible(), 'Service availability is accurately explained')
        page.get_by_text('About this assessment', exact=True).click()
        no_overflow(page, '390px prediction summary')
        page.screenshot(path=str(OUT / 'synthetic-prediction-mobile.png'), full_page=True)
        check(page.get_by_text('Your answers have been saved.', exact=True).is_visible(), 'Submission acknowledged by server')
        submitted_pid = page.request.get(BASE+'api/assessment').json()['participant_id']
        page.goto(BASE + '#support/request')
        page.wait_for_selector('#support-form')
        page.locator('#contact-method').select_option('email')
        page.locator('#contact-details').fill('alex@example.com')
        page.locator('#contact-times').fill('Weekday afternoons')
        page.locator('[name=permission]').check()
        page.get_by_role('button', name='Record demo request', exact=False).click()
        page.wait_for_selector('#support-receipt .receipt')
        check('SUP-' in page.locator('#support-receipt').inner_text(), 'Support receipt has a server reference')
        page.goto(BASE + '#privacy')
        page.get_by_role('button', name='Request removal of my information', exact=True).click()
        page.locator('#dialog').get_by_role('button', name='Record removal request', exact=True).click()
        page.wait_for_selector('#privacy-receipts .receipt')
        check('PRV-' in page.locator('#privacy-receipts').inner_text(), 'Privacy request has a server receipt')
        logout(page)

        page.set_viewport_size({'width':1440,'height':1050})
        login(page,'counsellor')
        page.goto(BASE+'#staff/case/'+submitted_pid+'/overview')
        page.wait_for_selector('#review-form')
        check(page.get_by_role('heading', name='Research model estimate', exact=True).is_visible(), 'Assigned clinician sees the saved model prediction')
        page.get_by_text('Model information',exact=True).click()
        check(page.get_by_text('Training data: synthetic records generated for this project.',exact=False).is_visible(), 'Clinician can access accurate model provenance')
        page.get_by_text('Class probabilities',exact=True).click()
        check(page.get_by_role('columnheader',name='Model probability',exact=True).is_visible(), 'Clinician can inspect saved model probabilities')
        page.get_by_role('link',name='Print report',exact=False).click()
        page.wait_for_selector('.report')
        check(page.get_by_role('heading',name='Research model estimate',exact=True).is_visible(), 'Printable report includes research prediction status')
        page.goto(BASE+'#staff/queue')
        page.wait_for_selector('#queue-search')
        page.screenshot(path=str(OUT/'queue-desktop.png'),full_page=True)
        check(page.get_by_role('link',name='P-0999',exact=True).count()==0, 'Unassigned case absent from counsellor queue')
        page.locator('#queue-search').fill('P-0142')
        page.get_by_role('link',name='P-0142',exact=True).click()
        page.wait_for_selector('#review-form')
        page.locator('#review-status').select_option(label='In progress')
        page.locator('#review-note').fill('Fictional browser QA review note.')
        page.get_by_role('button',name='Save review',exact=False).click()
        page.locator('#review-saved').filter(has_text='Saved ·').wait_for()
        check(True,'Confidential review saved with acknowledgement')
        page.screenshot(path=str(OUT/'record-desktop.png'),full_page=True)
        page.get_by_role('link',name='Back to review queue',exact=False).click()
        check(page.locator('#queue-search').input_value()=='P-0142','Queue filters preserved after record navigation')
        page.set_viewport_size({'width':320,'height':850})
        no_overflow(page,'320px staff queue')
        page.screenshot(path=str(OUT/'queue-mobile.png'),full_page=True)
        page.get_by_role('link',name='P-0142',exact=True).click()
        page.wait_for_selector('#review-form')
        no_overflow(page,'320px participant record')
        page.get_by_role('link',name='Print report',exact=False).click()
        page.wait_for_selector('.report')
        page.emulate_media(media='print')
        check(page.locator('#header').is_hidden(),'Print output hides application header')
        check('Fictional browser QA review note.' not in page.locator('.report').inner_text(),'Print report excludes confidential notes')
        page.pdf(path=str(OUT/'research-screening-summary.pdf'),format='A4',print_background=True)
        page.emulate_media(media='screen')
        logout(page)

        page.set_viewport_size({'width':1440,'height':1050})
        login(page,'researcher')
        page.wait_for_selector('.bar-row')
        check(page.get_by_role('heading',name='Model output distribution',exact=True).is_visible(),'Aggregate insights overview renders')
        page.screenshot(path=str(OUT/'research-desktop.png'),full_page=True)
        page.goto(BASE+'#staff/model')
        page.get_by_role('heading',name='Test-set performance',exact=True).wait_for()
        check(page.get_by_role('heading',name='Confusion matrix',exact=True).is_visible(),'Stored evaluation includes a confusion matrix')
        check(page.get_by_role('heading',name='Algorithm comparison',exact=True).is_visible(),'Stored model comparison renders')
        page.screenshot(path=str(OUT/'model-evaluation-desktop.png'),full_page=True)
        page.set_viewport_size({'width':320,'height':850})
        no_overflow(page,'320px model evaluation')
        logout(page)

        page.set_viewport_size({'width':1440,'height':1050})
        login(page,'admin')
        page.wait_for_selector('[data-account-edit]')
        check(page.get_by_role('heading',name='Accounts & roles',exact=True).is_visible(),'Administration workspace renders')
        page.goto(BASE+'#staff/configuration')
        page.wait_for_selector('.admin-card')
        page.locator('[data-config=consent]').click()
        page.locator('#config-value').fill('Updated demonstration consent configuration note.')
        page.locator('#dialog').get_by_role('button',name='Save new version',exact=True).click()
        page.wait_for_selector('#dialog:not([open])',state='attached')
        page.get_by_text('VERSION 2',exact=True).wait_for()
        check(page.get_by_text('VERSION 2',exact=True).is_visible(),'Workspace settings save a new version')
        page.goto(BASE+'#staff/audit')
        page.wait_for_selector('#audit-search')
        page.locator('#audit-search').fill('Versioned demo configuration')
        check(page.get_by_text('Versioned demo configuration',exact=True).count()>0,'Administration changes appear in audit history')
        check(not errors,'No browser JavaScript or console errors: '+json.dumps(errors))
        browser.close()
finally:
    server.shutdown()
    (OUT/'browser-checks.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
print(f'{len(checks)} browser checks passed. Screenshots and a print PDF are in test-results/.')
