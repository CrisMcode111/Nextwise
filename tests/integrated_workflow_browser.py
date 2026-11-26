"""Exercise the local offline integrated demo using real browser interactions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_nextwise_browser import Browser
from test_project_selection import BRIEF

def wait(browser, expression, timeout=180):
    end=time.time()+timeout
    while time.time()<end:
        if browser.evaluate(expression): return
        time.sleep(.3)
    raise AssertionError('Timed out: '+expression+'; status='+str(browser.evaluate('document.querySelector("#status").textContent')))

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
    chrome=subprocess.Popen(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu',
        '--no-first-run','--remote-debugging-port=9231','--user-data-dir='+profile,'about:blank'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try: pages=json.load(urllib.request.urlopen('http://127.0.0.1:9231/json',timeout=1)); break
            except OSError: time.sleep(.2)
        browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
        browser.call('Page.enable'); browser.call('Runtime.enable'); browser.call('Fetch.enable',{'patterns':[{'urlPattern':'*'}]})
        browser.allowed_origin='http://127.0.0.1:'+os.environ.get('NEXTWISE_DEMO_PORT','8771')
        result_path=Path(os.environ.get('NEXTWISE_DEMO_RESULT',str(ROOT/'reports'/'integrated_demo'/'browser-result.json')))
        previous = json.loads(result_path.read_text(encoding='utf-8')) if ('--reopen' in sys.argv or '--second' in sys.argv) else None
        browser.call('Page.navigate',{'url':browser.allowed_origin+'/projects'+('?project='+previous['id'] if previous else '')})
        wait(browser,'typeof busy !== "undefined" && !busy')
        if previous:
            wait(browser,'project && !busy')
            assert browser.evaluate('project.decisions[0].id') == previous['decision']['id']
            assert browser.evaluate('project.selected_opportunities[0].id') == previous['selection']['id']
            assert browser.evaluate('document.querySelectorAll(".selected-opportunity").length') == 1
            if '--reopen' in sys.argv:
                print('PASS: reopened selected opportunity and human decision after server restart')
                sys.exit(0)
            browser.evaluate('document.querySelector("#research-focus").value="marketing"; document.querySelector("#research-form").requestSubmit(); true')
            wait(browser,'!busy && researchPreview !== null')
            if browser.evaluate('!!document.querySelector("#clarify-audience")'):
                browser.evaluate('document.querySelector("#clarify-audience").value="Local families"; true')
            if browser.evaluate('!!document.querySelector("#clarify-outcome")'):
                browser.evaluate('document.querySelector("#clarify-outcome").value="Increase customer visits"; true')
            if browser.evaluate('!!document.querySelector("#research-output form")'):
                browser.evaluate('document.querySelector("#research-output form").requestSubmit(); true')
                wait(browser,'!busy && researchPreview.queries.length>0')
            old = browser.evaluate('Object.values(project.adaptive_discovery_runs)[0].strategy.reservations[0].query')
            assert browser.evaluate('researchPreview.queries[0].query') != old
            browser.evaluate('window.confirm=()=>true; document.querySelector("#research-output button.button").click(); true')
            wait(browser,'!busy && Object.keys(project.adaptive_discovery_runs).length===2')
            assert browser.evaluate('project.decisions[0].id') == previous['decision']['id']
            assert browser.evaluate('project.provider_availability.search_remaining') == 0
            assert browser.evaluate('Object.values(project.adaptive_discovery_runs).reduce((n,r)=>n+r.strategy.reservations.length,0)') == 2
            print('PASS: second reviewed browser session preserves both reservations and the human decision')
            sys.exit(0)
        browser.evaluate('''document.querySelector('#create-panel').open=true;
          document.querySelector('#project-input-name').value='''+json.dumps('Clinic rejected' if '--rejected' in sys.argv else 'Clinic')+''';
          document.querySelector('#project-input-brief').value='''+json.dumps('I have a small business and want help.' if '--clarify' in sys.argv else BRIEF)+''';
          document.querySelector('#create-project input[name=reviewed]').checked=true;
          document.querySelector('#create-project').requestSubmit(); true''')
        wait(browser,'typeof project !== "undefined" && project && !busy')
        if '--clarify' in sys.argv:
            browser.evaluate('document.querySelector("#research-focus").value="marketing"; document.querySelector("#research-form").requestSubmit(); true')
            wait(browser,'!busy && researchPreview !== null')
            assert browser.evaluate('!!document.querySelector("#clarify-subject") && !!document.querySelector("#clarify-outcome")')
            browser.evaluate('''document.querySelector('#clarify-subject').value='A bakery serving local families.';
              document.querySelector('#clarify-outcome').value='Increase visits from local customers.';
              document.querySelector('#clarify-subject').form.requestSubmit(); true''')
            wait(browser,'!busy && researchPreview.queries.length>0')
            assert browser.evaluate('Object.keys(project.adaptive_discovery_runs || {}).length===0')
            print('PASS: targeted clarification produces a local reviewed plan without a provider dispatch')
            sys.exit(0)
        browser.evaluate('''document.querySelector('#context-editor').open=true;
          document.querySelector('#context-priorities').value='Priority: operations';
          document.querySelector('#context-capabilities').value='We already answer questions about clinic hours.';
          document.querySelector('#context-form').requestSubmit(); document.querySelector('#context-save').click(); true''')
        wait(browser,'!busy && project.context_revisions?.length===1')
        browser.evaluate('document.querySelector("#research-form").requestSubmit(); true')
        wait(browser,'!busy && typeof researchPreview !== "undefined" && researchPreview !== null')
        assert browser.evaluate('researchPreview.understanding.confirmed_facts.some(f=>f.text.includes("already answer"))')
        assert browser.evaluate('researchPreview.queries.length>0')
        browser.evaluate('window.confirm=()=>false; document.querySelector("#research-output button.button").click(); true')
        wait(browser,'!busy')
        assert browser.evaluate('Object.keys(project.adaptive_discovery_runs || {}).length===0')
        browser.evaluate('window.confirm=()=>true; document.querySelector("#research-output button.button").click(); true')
        wait(browser,'!busy && Object.keys(project.items).length>0')
        browser.evaluate('document.querySelector("#assessment-controls button").click(); true')
        if '--rejected' in sys.argv:
            wait(browser,'!busy && Object.keys(project.opportunity_assessment_runs || {}).length>0')
            assert browser.evaluate('project.selected_opportunities.length===0')
            assert browser.evaluate('document.querySelector("#status").textContent.includes("does not establish irrelevance")')
            print('PASS: rejected assessment is not presented as an opportunity or as irrelevance')
            sys.exit(0)
        wait(browser,'!busy && project.selected_opportunities?.length===1')
        browser.evaluate('''document.querySelector('.project-decision-form select').value='Test';
          document.querySelector('.project-decision-form textarea').value='Review a synthetic question before a trial.';
          document.querySelector('.project-decision-form').requestSubmit(); true''')
        wait(browser,'!busy && project.decisions.length===1')
        result=browser.evaluate('({id:project.project.id, decision:project.decisions[0], selection:project.selected_opportunities[0]})')
        assert not browser.blocked_requests
        result_path.parent.mkdir(parents=True,exist_ok=True)
        result_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('PASS: reviewed plan, declined search, authorized search, assessment, selected opportunity and human decision')
    finally:
        chrome.terminate(); chrome.wait(timeout=10)
