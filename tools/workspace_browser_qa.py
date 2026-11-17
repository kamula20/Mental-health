"""Exercise the complete expanded workflow against an isolated local database."""
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / '.test-deps'))
sys.path.insert(0,str(ROOT))
from app import create_app
from playwright.sync_api import sync_playwright
from werkzeug.serving import WSGIRequestHandler, make_server

OUT=ROOT / 'test-results'
OUT.mkdir(exist_ok=True)
database=OUT / 'expanded-browser.sqlite3'
if database.exists():
    database.unlink()
app=create_app({'TESTING':True,'SECRET_KEY':'expanded-browser-fixture','DATABASE':str(database)})


class Quiet(WSGIRequestHandler):
    def log(self,*args):
        pass


server=make_server('127.0.0.1',5056,app,threaded=True,request_handler=Quiet)
threading.Thread(target=server.serve_forever,daemon=True).start()
BASE='http://127.0.0.1:5056/'
checks=[]
errors=[]


def check(value,message):
    assert value,message
    checks.append(message)


def login(page,role):
    page.goto(BASE+'#access/'+('staff' if role!='participant' else ''))
    page.locator('[data-demo-account="'+role+'"]').click()
    page.get_by_role('button',name='Sign in',exact=True).click()
    page.wait_for_selector('.staff-content' if role!='participant' else '.home-main')


def logout(page):
    page.get_by_role('button',name='Sign out',exact=True).click()
    page.locator('#dialog').get_by_role('button',name='Sign out',exact=True).click()
    page.wait_for_selector('.home-main')


def complete_form(page,followup=False):
    page.locator('#field-age').fill('19')
    page.locator('#field-consent').check(); page.locator('#field-privacy').check()
    page.get_by_role('button',name='Continue',exact=False).click()
    page.locator('input[name=gender][value=prefer_not]').check()
    page.locator('input[name=education][value=university]').check()
    page.get_by_role('button',name='Continue',exact=False).click()
    choices={'platforms':'instagram','daily_time':'under1' if followup else '5plus','passive':'rarely' if followup else 'often','active':'sometimes','night':'never' if followup else 'often','cyberbullying':'never','regular_count':'1'}
    for key,value in choices.items():
        page.locator(f'input[name="{key}"][value="{value}"]').check()
    page.get_by_role('button',name='Continue',exact=False).click()
    page.locator('input[name=wellbeing_opt_in]').check()
    page.locator('#phq9-0').wait_for()
    page.get_by_role('button',name='Review my answers',exact=False).click()
    check(page.locator('.error-summary').is_visible(),'Incomplete optional questionnaires cannot produce invented scores')
    for key,count in [('phq9',9),('gad7',7)]:
        for i in range(count):
            value='0' if followup or key=='phq9' and i==8 else '1'
            page.locator(f'#{key}-{i}').select_option(value)
        page.locator(f'#field-{key}_difficulty').select_option('0' if followup else '1')
    page.get_by_role('button',name='Review my answers',exact=False).click()
    page.get_by_role('button',name='Submit demo assessment',exact=False).click()
    page.get_by_role('heading',name='Thank you for sharing.',exact=True).wait_for()


try:
    with sync_playwright() as p:
        options={'headless':True}
        configured=os.environ.get('BETWEEN_BROWSER')
        cached=Path(os.environ.get('LOCALAPPDATA','')) / 'ms-playwright/chromium-1243/chrome-win64/chrome.exe'
        if configured or cached.exists():
            options['executable_path']=configured or str(cached)
        browser=p.chromium.launch(**options)
        context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
        login(page,'participant')
        page.get_by_role('link',name='Start my assessment',exact=False).click()
        complete_form(page)
        check(page.get_by_text('8 / 27',exact=True).is_visible(),'Participant sees the actual PHQ-9 total')
        check(page.get_by_text('7 / 21',exact=True).is_visible(),'Participant sees the actual GAD-7 total separately from the model')
        own=page.request.get(BASE+'api/assessment').json()
        pid=own['participant_id']
        check(own['submission']['instruments'][2]['score'] is None,'WEMWBS is not fabricated or administered without a licence')
        page.set_viewport_size({'width':390,'height':844})
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'390px completed questionnaire summary fits the page')
        page.screenshot(path=str(OUT / 'expanded-assessment-mobile.png'),full_page=True)
        page.get_by_role('button',name='Start a follow-up assessment',exact=False).click()
        page.locator('#dialog').get_by_role('button',name='Start new assessment',exact=True).click()
        page.locator('#field-age').wait_for()
        check(page.locator('#field-age').input_value()=='','Repeat assessment starts with fresh participation choices')
        complete_form(page,True)
        page.goto(BASE+'#history')
        page.get_by_role('heading',name='Your progress over time',exact=True).wait_for()
        history=page.request.get(BASE+'api/assessment/history').json()['visits']
        check(len(history)==2 and history[0]['instruments'][0]['score']==8 and history[1]['instruments'][0]['score']==0,'Repeat submission preserves the previous scored visit')
        check(page.locator('.history-chart').is_visible(),'Actual questionnaire history renders as a chart with a data table')
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'390px history has no page-level overflow')
        page.screenshot(path=str(OUT / 'assessment-history-mobile.png'),full_page=True)
        logout(page)
        page.set_viewport_size({'width':1440,'height':1000})
        login(page,'counsellor')
        page.goto(BASE+'#staff/case/'+pid+'/overview')
        page.locator('#conclusion-form').wait_for()
        page.locator('#clinical-conclusion').select_option(label='Follow-up planned')
        page.locator('#clinical-agreement').select_option(label='Disagree')
        page.locator('#clinical-rationale').fill('Independent fictional clinician assessment differs from the model.')
        page.locator('#clinical-private').fill('PRIVATE STAFF NOTE MUST NOT LEAK')
        page.locator('#clinical-shared').fill('Let us discuss your routines at your next appointment.')
        page.locator('#conclusion-form [name=published]').check()
        page.get_by_role('button',name='Save clinician conclusion',exact=False).click()
        page.locator('#conclusion-saved').filter(has_text='Saved').wait_for()
        check(True,'Clinician can record independent disagreement and explicitly share a participant message')
        page.get_by_role('button',name='Schedule appointment',exact=False).click()
        page.locator('#appointment-location').fill('Example campus student services office')
        page.locator('#dialog').get_by_role('button',name='Schedule appointment',exact=True).click()
        page.get_by_role('heading',name='Follow-up dashboard',exact=True).wait_for()
        check(page.get_by_text('Example campus student services office',exact=True).is_visible(),'Scheduled appointment appears in the clinician follow-up dashboard')
        page.screenshot(path=str(OUT / 'followup-dashboard-desktop.png'),full_page=True)
        page.goto(BASE+'#staff/case/'+pid+'/overview')
        page.get_by_role('link',name='Print report',exact=False).click()
        page.locator('.report').wait_for()
        check('PRIVATE STAFF NOTE MUST NOT LEAK' not in page.locator('.report').inner_text(),'Printable report excludes the private clinician note')
        check(page.get_by_role('heading',name='Clinician conclusion',exact=True).is_visible(),'Printable report includes clinician sign-off separately from the model')
        logout(page)
        login(page,'participant')
        page.goto(BASE+'#assessment')
        page.get_by_role('heading',name="Your clinician's feedback",exact=True).wait_for()
        check(page.get_by_text('Let us discuss your routines at your next appointment.',exact=True).is_visible(),'Participant receives only the explicitly shared feedback')
        check('PRIVATE STAFF NOTE MUST NOT LEAK' not in page.locator('#main').inner_text(),'Private clinical notes stay outside participant pages')
        page.goto(BASE+'#appointments')
        page.get_by_role('heading',name='Your appointments',exact=True).wait_for()
        check(page.get_by_text('Example campus student services office',exact=True).is_visible(),'Participant can see the agreed appointment details')
        page.goto(BASE+'#notifications')
        page.get_by_role('heading',name='Your messages',exact=True).wait_for()
        check(page.locator('[data-read-notification]').count()==2,'Feedback and appointments create in-app notifications')
        logout(page)
        login(page,'admin')
        page.goto(BASE+'#staff/services')
        page.get_by_role('button',name='Add checked service',exact=False).click()
        for key,value in {'name':'Example campus desk','contact':'Example student services office','hours':'Weekdays 09:00-17:00','eligibility':'Fictional campus members','source_url':'https://example.org/services','checked_on':datetime.now(timezone.utc).date().isoformat()}.items():
            page.locator('#service-'+key).fill(value)
        page.locator('#dialog [name=confirmed_checked]').check()
        page.locator('#dialog').get_by_role('button',name='Save service',exact=True).click()
        page.locator('#dialog:not([open])').wait_for(state='attached')
        page.get_by_role('heading',name='Example campus desk',exact=True).wait_for()
        check(True,'Administrator can record and publish a staff-checked support contact')
        page.goto(BASE+'#support')
        page.get_by_role('heading',name='Example campus desk',exact=True).wait_for()
        check(True,'Published support contacts appear in the participant support page')
        page.goto(BASE+'#staff/invitations')
        page.locator('#invite-name').fill('Invited clinician fixture')
        page.locator('#invite-email').fill('browser-invite@example.test')
        page.locator('#invitation-form [name=confirmed]').check()
        page.get_by_role('button',name='Create invitation',exact=False).click()
        page.locator('#invitation-saved').filter(has_text='Invitation created').wait_for()
        page.goto(BASE+'#staff/mail')
        page.get_by_role('heading',name='Account mail',exact=True).wait_for()
        check(page.get_by_text('No email is sent in this mode.',exact=False).is_visible(),'Mail preview never claims to send a real email')
        message=page.request.get(BASE+'api/admin/mail').json()['messages'][0]['body']
        token=re.search(r'set-password/([A-Za-z0-9_-]+)',message).group(1)
        invited_context=browser.new_context(viewport={'width':390,'height':844})
        invited=invited_context.new_page()
        invited.goto(BASE+'#account/set-password/'+token)
        invited.locator('#new-password').fill('Browser-long-password!')
        invited.locator('#confirm-password').fill('Browser-long-password!')
        invited.get_by_role('button',name='Set password',exact=False).click()
        invited.locator('#login-form').wait_for()
        invited.locator('#email').fill('browser-invite@example.test')
        invited.locator('#password').fill('Browser-long-password!')
        invited.get_by_role('button',name='Sign in',exact=True).click()
        invited.locator('.staff-content').wait_for()
        check(True,'An invited clinician can set a password and sign in using the single-use link')
        check(invited.evaluate('document.documentElement.scrollWidth<=innerWidth'),'390px invited account workspace fits the page')
        invited_context.close()
        logout(page)
        login(page,'researcher')
        page.goto(BASE+'#staff/validation')
        page.get_by_role('heading',name='Clinical evaluation readiness',exact=True).wait_for()
        check(page.get_by_text('No external participant study has been connected.',exact=False).is_visible(),'Evaluation readiness does not claim a real study was conducted')
        check(not errors,'Expanded workflow has no JavaScript or browser console errors: '+json.dumps(errors))
        browser.close()
finally:
    server.shutdown()
    (OUT / 'workspace-browser-checks.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
print(f'{len(checks)} expanded-workflow browser checks passed.')
