'use strict';

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const icons = {
  arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>', back:'<path d="M20 12H5m6-6-6 6 6 6"/>',
  check:'<path d="m5 12 4 4L19 6"/>', shield:'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', heart:'<path d="M20 5c-3-3-7-1-8 1-1-2-5-4-8-1s0 8 8 14c8-6 11-11 8-14Z"/>',
  queue:'<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>', people:'<circle cx="9" cy="8" r="3"/><path d="M3 20v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 4v2"/>',
  chart:'<path d="M4 4v16h17M9 15V9m5 6V5m5 10v-4"/>', file:'<path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8m-8 4h8"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/>', menu:'<path d="M4 6h16M4 12h16M4 18h16"/>', external:'<path d="M14 4h6v6m0-6L10 14M10 4H4v16h16v-6"/>', refresh:'<path d="M20 11a8 8 0 1 0-2 7M20 4v7h-7"/>'
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
const fmt = value => value ? new Intl.DateTimeFormat('en-GB', {day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit'}).format(new Date(value)) : 'Not available';
const shortDate = value => value ? new Intl.DateTimeFormat('en-GB', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(value)) : '—';
const cls = value => ({Low:'low',Moderate:'moderate',High:'high'}[value] || 'unavailable');
const estimateTag = value => `<span class="tag ${cls(value)}">${esc(value || 'No estimate')}</span>`;
const reviewTag = value => `<span class="tag review">${esc(value)}</span>`;
const roleName = role => ({counsellor:'Clinician',researcher:'Insights',administrator:'Administrator',participant:'Young person'})[role] || role;
const state = {user:null,csrf:'',expires:null,answers:{},step:0,assessment:null,case:null,cases:[],queue:{search:'',status:'',estimate:'',missing:false,date:'',sort:'newest',page:1},retry:null,submissionId:crypto.randomUUID(),saveTime:null};
let routeSerial = 0;

async function api(path, method = 'GET', body) {
  let response;
  try {
    response = await fetch('/api' + path, {method, credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  } catch (_) {
    throw new Error('Connection lost. This change has not been saved. Your answers are still on this page; reconnect and try again.');
  }
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || 'The request could not be completed.');
    error.fields = data.fields;
    error.status = response.status;
    if (response.status === 401 && path !== '/login') {
      state.user = null;
      $('#session-warning').hidden = false;
      $('#session-warning').innerHTML = 'Your session has ended. Only server-saved answers can be recovered. <a href="#access">Sign in again</a>';
    }
    throw error;
  }
  return data;
}
function announce(message) { $('#announcer').textContent = message; }
function button(text, type = 'submit', extra = '') { return `<button class="button ${extra.includes('full-width') ? 'full-width' : ''}" type="${type}">${text}${icon('arrow')}</button>`; }
function errorBox(error, root = $('#main')) {
  const target = $('.error-slot', root) || root;
  target.innerHTML = `<div class="error-summary" tabindex="-1" role="alert"><h2>${esc(error.message)}</h2>${error.fields ? `<ul>${Object.entries(error.fields).map(([key,message]) => `<li><a href="#field-${esc(key)}" data-error-focus="${esc(key)}">${esc(message)}</a></li>`).join('')}</ul>` : ''}<button type="button" class="link-button" data-action="retry">Try again</button></div>`;
  if (error.fields) Object.entries(error.fields).forEach(([key,message]) => {
    const group = $(`[data-field="${key}"]`, root) || $(`#field-${key}`, root)?.closest('.field');
    if (group) {
      if (!$('.error-inline', group)) group.insertAdjacentHTML('beforeend', `<p class="error-inline">${esc(message)}</p>`);
      $$('input,select', group).forEach(input => input.setAttribute('aria-invalid','true'));
    }
  });
  $('.error-summary', target)?.focus();
}
async function pending(form, work) {
  const buttons = $$('button[type=submit]', form);
  const old = buttons.map(b => b.innerHTML);
  buttons.forEach(b => { b.disabled = true; b.textContent = 'Saving…'; });
  try { await work(); } finally { buttons.forEach((b,i) => { b.disabled = false; b.innerHTML = old[i]; }); }
}
function cleanMarkup(content) { return content.replace(/style="margin-(top|bottom):(\d+)(?:px)?"/g, (_,edge,size) => `data-m${edge[0]}="${size}"`); }
function main(content, className = 'container') {
  $('#app').innerHTML = cleanMarkup(`<main id="main" class="${className}" tabindex="-1">${content}</main>`);
}
function heading(eyebrow, title, sub = '') { return `<div class="page-heading"><p class="eyebrow"><span class="rule"></span>${eyebrow}</p><h1>${title}</h1>${sub ? `<p>${sub}</p>` : ''}</div>`; }
function infoDetails(title, content) { return `<details class="info-details"><summary>${esc(title)}</summary><div class="info-details-body">${content}</div></details>`; }
function brand() { return '<a class="brand" href="#home" aria-label="Between home"><svg class="brand-symbol" viewBox="0 0 32 36" fill="none" aria-hidden="true"><path d="M10 4H4v28h6M22 4h6v28h-6M10 14c4-4 8 4 12 0m-12 7c4-4 8 4 12 0" stroke="currentColor" stroke-width="1.8"/></svg><span class="wordmark">between<span class="brand-period">.</span></span><span class="brand-caption">YOUTH MENTAL<br>HEALTH WORKSPACE</span></a>'; }
function shell(staff = false, active = '') {
  const name = state.user ? `<span class="user-name muted">${esc(state.user.name)}</span><button class="link-button" data-action="logout">Sign out</button>` : '<a href="#access/staff">Sign in '+icon('arrow')+'</a>';
  $('#header').className = staff ? 'staff-header' : '';
  $('#header').innerHTML = `<div class="container"><div class="brand-row">${brand()}<div class="header-actions">${staff ? '<button class="icon-button staff-menu-toggle" data-action="staff-menu" aria-expanded="false" aria-controls="staff-navigation">'+icon('menu')+'Menu</button>' : ''}<a href="#support">${icon('heart')}Get support</a>${name}</div></div>${staff ? '' : `<nav class="participant-nav" aria-label="Participant navigation">${[['home','Home'],['assessment','My assessment'],['support','Support'],['privacy','Privacy']].map(([path,label]) => `<a href="#${path}" class="${active === path ? 'active' : ''}" ${active === path ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`}</div>`;
  $('#footer').className = staff ? 'no-print' : 'container';
  $('#footer').innerHTML = staff ? '' : `<div class="footer-inner"><div><span class="footer-wordmark">between</span><span>A little space for your wellbeing.</span></div><div class="footer-links"><a href="#about">About Between</a><a href="#privacy">Privacy</a><a href="#access/staff">Clinicians ${icon('arrow')}</a></div></div>`;
}
function staffShell(content, active) {
  const role = state.user.role;
  const links = role === 'counsellor' ? [['queue','Review queue','queue'],['participants','Young people','people'],['reports','Reports','file']] : role === 'researcher' ? [['research','Overview','chart'],['dataset','Data quality','file'],['model','Model status','queue']] : [['admin','Accounts & roles','people'],['assignments','Assignments','queue'],['configuration','Workspace settings','file'],['audit','Access history','lock']];
  shell(true);
  main(`<div class="staff-shell"><aside class="staff-nav" id="staff-navigation"><p class="staff-role">${esc(({counsellor:'Clinician',researcher:'Insights',administrator:'Administrator'})[role] || role)}</p><nav aria-label="Staff navigation">${links.map(([path,label,ic]) => `<a href="#staff/${path}" class="${active === path ? 'active' : ''}" ${active === path ? 'aria-current="page"' : ''}>${icon(ic)}${label}</a>`).join('')}</nav><div class="staff-nav-bottom">${esc(state.user.name)}<span>EXAMPLE RECORDS</span></div></aside><section class="staff-content">${content}</section></div>`, '');
}

async function home() {
  shell(false,'home');
  if (state.user?.role === 'participant') state.assessment = await api('/assessment');
  const data = state.assessment;
  const submitted = state.user?.role === 'participant' && data?.submission;
  const draft = state.user?.role === 'participant' && data?.draft;
  const label = submitted ? 'View my summary' : draft ? 'Continue my assessment' : 'Start my assessment';
  if (typeof window.renderOpusHome !== 'function') throw new Error('The homepage did not load. Refresh this page to try again.');
  main(window.renderOpusHome({ctaLabel:label,icon,esc,fmt,draft,submission:submitted,user:state.user}));
  window.initOpusHome?.();
}

function about() {
  shell(false);
  main(`<div class="page-grid"><article>
  ${heading('ABOUT BETWEEN','Understand more.<br>Support better.','Assessments, clinician review and follow-up for young people aged 13–24.')}
  <section class="section-block"><h2>For clinicians and young people</h2><ul class="essentials"><li>Young people describe their experiences and digital habits.</li><li>Clinicians review assigned assessments and record follow-up.</li><li>Insights and administration have separate access permissions.</li></ul></section>
  ${infoDetails('How assessments work','<p>Read the information, check age eligibility and give consent. Complete background and digital-habit questions, review your answers and submit. You can go back and correct an answer before submission.</p><p>Save and resume a draft, view a summary, request a conversation or manage participation. Authorised clinicians can review assigned records, produce reports and record follow-up.</p>')}
  ${infoDetails('Current tools and availability','<p>This version uses example accounts and fictional records. Use example details only. No validated model has been released.</p><p>PHQ-9, GAD-7 and WEMWBS are not administered or scored. Approved instrument versions and a staffed safeguarding process are required; WEMWBS also needs the appropriate licence.</p><p>Source questionnaire wording, time categories, consent and assent, the under-18 pathway and retention rules still need approval before live collection.</p><p>Model outputs, questionnaire results and clinician judgement are separate. Self-reported social media habits do not establish causation or predict future illness.</p>')}
  <div class="compact-actions"><a class="button" href="#access/staff">Open clinician workspace ${icon('arrow')}</a><a class="button secondary" href="#assessment">Start an assessment ${icon('arrow')}</a></div>
</article><aside class="guidance"><p class="guide-label">YOUR INFORMATION</p><h2>Your experience.<br>Your choice.</h2><p>Taking part and requesting contact are separate choices. You can stop or seek support at any time.</p><hr><p>No social media login, message access or phone monitoring.</p><a href="#privacy">Privacy and choices ${icon('arrow')}</a></aside></div>`);
}

function access(staff = false) {
  shell(false);
  main(`<div class="auth-wrap"><section>
  <p class="eyebrow"><span class="rule"></span>${staff ? 'CLINICIAN WORKSPACE' : 'ASSESSMENT ACCESS'}</p><h1>${staff ? 'Understand.<br>Review. Follow up.' : 'Your assessment,<br>at your pace.'}</h1>
  <p class="muted">${staff ? 'Review assigned assessments and plan the next conversation.' : 'Use an access code to begin, or sign in to resume saved work.'}</p>
  <div class="notice warning">Use example details only. Requests are not monitored.</div>
  ${infoDetails(staff ? 'About staff access' : 'Saving and returning',staff ? '<p>Choose an example account to explore its workspace. Clinicians see assigned cases; analysts see aggregate information; administrators manage access. Permissions are enforced by the server.</p>' : '<p>An access code creates a temporary session that cannot be recovered after sign-out. Use the participant example account to save, sign out and resume the same assessment later.</p>')}
  <p class="small"><a href="#${staff ? 'access' : 'access/staff'}">${staff ? 'Here to complete an assessment?' : 'Clinician sign in'} ${icon('arrow')}</a></p>
</section><section class="panel"><div class="error-slot"></div>
  ${!staff ? `<h2>Begin with an access code</h2><form id="code-form"><div class="field"><label for="study-code">Access code</label><input id="study-code" name="code" value="BETWEEN-DEMO" required maxlength="40" autocomplete="off"><small>Temporary session. No registration needed.</small></div>${button('Enter the demo','submit','class="button full-width"')}</form><div class="divider">or sign in</div>` : '<h2>Sign in</h2>'}
  <p class="small muted">Choose an example account to fill your details.</p><div class="demo-account-options">${(staff ? [['counsellor','Clinician'],['researcher','Insights'],['admin','Administrator']] : [['participant','Young person']]).map(([role,label]) => `<button type="button" data-demo-account="${role}">${label}</button>`).join('')}</div>
  <form id="login-form"><div class="field"><label for="email">Email address</label><input type="email" name="email" id="email" required autocomplete="username" placeholder="${staff ? 'counsellor' : 'participant'}@between.demo"></div><div class="field"><label for="password">Password</label><div class="password-wrap"><input type="password" name="password" id="password" required autocomplete="current-password"><button type="button" data-action="password" aria-controls="password" aria-pressed="false">Show</button></div></div>${button('Sign in','submit','class="button full-width"')}</form>
  ${infoDetails('Account help','<p>Example password: <strong>BetweenDemo!26</strong>. The buttons above fill it automatically. Account recovery is not connected in this version.</p>')}
</section></div>`);
  $('#login-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const run = () => pending(form, async () => {
      try {
        const data = await api('/login','POST',Object.fromEntries(new FormData(form)));
        Object.assign(state, data, {assessment:null,answers:{},step:0,submissionId:crypto.randomUUID()});
        $('#session-warning').hidden = true;
        location.hash = data.user.role === 'participant' ? '#home' : '#staff/' + ({counsellor:'queue',researcher:'research',administrator:'admin'}[data.user.role]);
      } catch (error) { errorBox(error); }
    });
    state.retry = run; await run();
  });
  $('#code-form')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget;
    const run = () => pending(form, async () => {
      try { const data = await api('/study-access','POST',Object.fromEntries(new FormData(form))); Object.assign(state,data,{answers:{},step:0,assessment:null,submissionId:crypto.randomUUID()}); $('#session-warning').hidden=true; location.hash='#assessment'; }
      catch (error) { errorBox(error); }
    });
    state.retry=run; await run();
  });
}

const labels = {
  gender:{woman:'Woman',man:'Man',nonbinary:'Non-binary',other:'Other',prefer_not:'Prefer not to say'},
  education:{secondary:'Secondary school',college:'College / vocational training',university:'University',other:'Other'},
  platforms:{instagram:'Instagram',tiktok:'TikTok',whatsapp:'WhatsApp',youtube:'YouTube',snapchat:'Snapchat',facebook:'Facebook',x:'X',other:'Other'},
  daily_time:{under1:'Less than 1 hour', '1to3':'1 to less than 3 hours','3to5':'3 to less than 5 hours', '5plus':'5 hours or more'},
  passive:{never:'Never',rarely:'Rarely',sometimes:'Sometimes',often:'Often',always:'Always'},
  active:{never:'Never',rarely:'Rarely',sometimes:'Sometimes',often:'Often',always:'Always'},
  night:{never:'Never',rarely:'Rarely',sometimes:'Sometimes',often:'Often',always:'Always'},
  cyberbullying:{never:'Never',once:'Once',sometimes:'Sometimes',often:'Often'},
  regular_count:{'1':'1','2':'2','3':'3','4plus':'4 or more'}
};
const questions = {age:'Your age',gender:'Gender',education:'Education',platforms:'Platforms currently used',daily_time:'Average daily social media use',passive:'Scrolling without interacting',active:'Active engagement',night:'Social media use after 11 pm',cyberbullying:'Lifetime cyberbullying exposure',regular_count:'Platforms used regularly'};
function choiceGroup(key, title, help = '', opts = {}) {
  const value = state.answers[key];
  return `<fieldset data-field="${key}" id="field-${key}"><legend>${opts.number ? `<span class="section-number">${opts.number}</span>` : ''}${title}</legend>${help ? `<p class="field-help">${help}</p>` : ''}<div class="choices ${opts.compact ? 'compact' : ''}">${Object.entries(labels[key]).map(([code,label]) => `<label class="choice"><input type="${opts.multi ? 'checkbox' : 'radio'}" name="${key}" value="${code}" ${opts.multi ? value?.includes(code) ? 'checked' : '' : value === code ? 'checked' : ''}><span>${label}</span></label>`).join('')}</div>${['gender','education','platforms'].includes(key) ? `<div class="field other-field" ${value === 'other' || Array.isArray(value) && value.includes('other') ? '' : 'hidden'}><label for="field-${key}_other">Please specify</label><input type="text" id="field-${key}_other" name="${key}_other" maxlength="150" value="${esc(state.answers[key+'_other'])}"></div>` : ''}${key === 'platforms' ? `<p class="small muted platform-count" style="margin-top:12px">${value?.length || 0} selected</p>` : ''}</fieldset>`;
}
function readAnswers() {
  const form = $('#assessment-form'); if (!form) return;
  const data = new FormData(form);
  if (state.step === 0) {
    const ageValue = data.get('age');
    state.answers.age = ageValue === '' ? undefined : Number(ageValue);
    ['consent','privacy','guardian','assent','contact_opt_in'].forEach(key => state.answers[key] = data.get(key) === 'on');
  } else {
    for (const [key,value] of data.entries()) if (key !== 'platforms') state.answers[key] = value;
    if (state.step === 2) state.answers.platforms = data.getAll('platforms');
    ['gender','education','platforms'].forEach(key => {
      const value = state.answers[key];
      if (!(value === 'other' || Array.isArray(value) && value.includes('other'))) delete state.answers[key+'_other'];
    });
  }
}
function validateStep() {
  const errors = {};
  const a = state.answers;
  if (state.step === 0) {
    if (!Number.isInteger(a.age) || a.age < 13 || a.age > 24) errors.age = 'Assessments are for ages 13–24. Enter a whole-number age.';
    if (!a.consent) errors.consent = 'Choose whether to take part before continuing.';
    if (!a.privacy) errors.privacy = 'Please acknowledge the participation information.';
    if (a.age < 18) { if (!a.guardian) errors.guardian = 'Complete the guardian authorisation demo choice.'; if (!a.assent) errors.assent = 'Your own assent is also required.'; }
  }
  const required = state.step === 1 ? ['gender','education'] : state.step === 2 ? ['platforms','daily_time','passive','active','night','cyberbullying','regular_count'] : [];
  required.forEach(key => { if (!a[key] || Array.isArray(a[key]) && !a[key].length) errors[key] = `Choose an answer for ${questions[key].toLowerCase()}.`; });
  for (const key of ['gender','education','platforms']) if ((a[key] === 'other' || Array.isArray(a[key]) && a[key].includes('other')) && !a[key+'_other']?.trim()) errors[key+'_other'] = 'Please specify your other answer.';
  return errors;
}
async function saveDraft(nextStep = state.step) {
  const data = await api('/assessment/draft','PUT',{answers:state.answers,step:Math.max(1,nextStep)});
  state.saveTime=data.updated;
  if ($('#save-status')) $('#save-status').textContent = 'Saved to your session · ' + fmt(data.updated);
  announce('Your answers have been saved to the server.');
}
async function assessment() {
  if (!state.user) { location.hash='#access'; return; }
  if (state.user.role !== 'participant') { restricted('Participant assessment','Use an assessment account to try the questions.'); return; }
  shell(false,'assessment');
  state.assessment = await api('/assessment');
  if (state.assessment.submission) { summary(); return; }
  if (state.assessment.withdrawn) { main(`<div class="assessment-wrap">${heading('PARTICIPATION','You have withdrawn.','Your demo participation is closed. Submitted records are retained until a separate removal request is reviewed.')}<a href="#privacy" class="button">View participation choices ${icon('arrow')}</a></div>`); return; }
  if (!Object.keys(state.answers).length && state.assessment.draft) {
    state.answers=state.assessment.draft.answers; state.step=state.assessment.draft.step; state.saveTime=state.assessment.draft.updated;
  }
  assessmentPage();
}
function assessmentPage() {
  const a = state.answers;
  const step = state.step;
  const titles = ['Before you take part.','A little about you.','Your usual habits online.','A note on wellbeing.','Take a moment to review.'];
  const subtitles = ['Read the essentials, then choose.','A few questions. Your record uses an ID.','Think about your usual experience. No right or wrong answers.','These tools are not connected yet.','Check or edit your answers before submitting.'];
  let content='';
  if (step === 0) content = `<div class="notice warning"><strong>Use example details only.</strong> Live assessment access is not enabled.</div><div class="section-block"><h2>Before you begin</h2><ul class="essentials"><li>Taking part is voluntary. Stop before submitting if you wish.</li><li>We ask about your background, digital habits and wellbeing.</li><li>No account access, message reading or phone monitoring.</li><li>Authorised clinicians may review ID-based records; contact details are separate.</li></ul>${infoDetails('Participation details','<p>Consent, the under-18 pathway, questionnaire wording, retention rules and staffed safeguarding arrangements need approval before live use. This assessment demonstrates those choices; it does not enrol you in a live clinical service.</p>')}<a class="small" href="#privacy">Read how your information is used</a></div><div class="field" data-field="age"><label for="field-age">Your age</label><input type="number" min="13" max="24" step="1" id="field-age" name="age" value="${esc(a.age)}" inputmode="numeric" autocomplete="off" aria-describedby="age-help"><small id="age-help">Ages 13–24. No date of birth needed.</small></div><div class="choice-group"><h3>Participation</h3><label class="check-line" data-field="consent"><input id="field-consent" type="checkbox" name="consent" ${a.consent ? 'checked' : ''}><span>I choose to complete this example assessment.</span></label><label class="check-line" data-field="privacy"><input id="field-privacy" type="checkbox" name="privacy" ${a.privacy ? 'checked' : ''}><span>I have read how my information is used and understand this is a demo.</span></label></div><div id="minor-path" ${a.age && a.age < 18 ? '' : 'hidden'}><div class="notice warning"><strong>Under 18?</strong><p>Live use needs approved guardian authorisation and your assent. These example choices do not verify a real guardian.</p></div><label class="check-line" data-field="guardian"><input id="field-guardian" type="checkbox" name="guardian" ${a.guardian ? 'checked' : ''}><span>Simulate guardian authorisation for the demo.</span></label><label class="check-line" data-field="assent"><input id="field-assent" type="checkbox" name="assent" ${a.assent ? 'checked' : ''}><span>I also choose to take part in the demo myself.</span></label></div><hr><div class="choice-group"><h3>Optional follow-up</h3><label class="check-line"><input type="checkbox" name="contact_opt_in" ${a.contact_opt_in ? 'checked' : ''}><span>I’d like the option to request a conversation after the assessment. <span class="muted">Optional.</span></span></label></div>`;
  if (step === 1) content = choiceGroup('gender','How do you describe your gender?','You can choose not to say.',{compact:true,number:'01'}) + choiceGroup('education','What is your current level of education?','Example categories; final wording awaits approval.',{number:'02'});
  if (step === 2) content = `<div class="notice warning">Example questions — not approved for live collection.</div>${infoDetails('Questionnaire status','<p>Appendix A has been reviewed. This demo combines its 1 to 2 and 2 to 3 hour bands into 1 to 3 hours. Live collection still needs an approved questionnaire and protocol.</p>')}` + choiceGroup('platforms','Which social media platforms do you currently use?','Choose all that apply. Do not enter usernames or account details.',{multi:true,compact:true,number:'01'}) + choiceGroup('daily_time','How much time do you usually spend on social media each day?','Example time bands, not yet approved for live use.',{number:'02'}) + choiceGroup('passive','How often do you scroll without interacting?','For example, watching, reading or scrolling without liking, commenting or posting.',{number:'03'}) + choiceGroup('active','How often do you actively engage with others online?','For example, posting, commenting or having a conversation.',{number:'04'}) + choiceGroup('night','How often do you use social media after 11 pm?','Think about your usual habits.',{number:'05'}) + choiceGroup('cyberbullying','How often have you experienced cyberbullying in your lifetime?','No account names or incident details. Response choices await verification.',{number:'06'}) + choiceGroup('regular_count','How many platforms do you use regularly?','This may be fewer than the platforms you selected above.',{compact:true,number:'07'});
  if (step === 3) content = `<div class="notice"><strong>Wellbeing questionnaires are not enabled.</strong><p>Continue with the behaviour-only assessment. Your summary will show these tools as not administered.</p></div>${[['PHQ-9','Depression screening questionnaire','Approved protocol and response arrangements required'],['GAD-7','Anxiety screening questionnaire','Approved instrument version required'],['WEMWBS','Mental wellbeing scale','Appropriate licence and approved version required']].map(([name,desc,reason]) => `<div class="instrument-row"><div><h3>${name}</h3><p>${desc}<br>${reason}</p></div><span class="tag unavailable">Not administered</span></div>`).join('')}<p class="small muted" style="margin-top:24px">No questionnaire scores are created. Submitting can produce a research model estimate for review. You can <a href="#support">explore support</a> at any time.</p>`;
  if (step === 4) content = `<div class="review-heading"><h2>Your answers</h2><button type="button" class="link-button" data-edit-step="1">Edit answers</button></div>${answersTable(a)}<div class="section-block"><h2>Your choices</h2><p class="small">Demo participation confirmed. Optional contact: <strong>${a.contact_opt_in ? 'Interested in follow-up' : 'Not requested'}</strong>.</p><button type="button" class="link-button" data-edit-step="0">Edit participation choices</button></div><div class="notice warning"><strong>Before submitting:</strong> PHQ-9, GAD-7 and WEMWBS were not administered. If available, the research model will provide an estimate. Model information is included with your results. One submission is allowed.</div>`;
  main(`<div class="assessment-wrap"><div class="progress" aria-label="Assessment progress">${[['About you',1],['Digital habits',2],['Wellbeing',3]].map(([label,num]) => `<div class="progress-item ${step === num ? 'active' : step > num ? 'done' : ''}" ${step === num ? 'aria-current="step"' : ''}><b>0${num}</b>${label}</div>`).join('')}</div>${heading(step === 0 ? 'YOUR CHOICE' : step === 4 ? 'REVIEW / BEFORE YOU SUBMIT' : `SECTION 0${step} / 03`,titles[step],subtitles[step])}<form id="assessment-form" novalidate><div class="error-slot"></div>${content}<div class="form-actions"><div class="left">${step ? '<button type="button" class="link-button" data-action="assessment-back">'+icon('back')+' Back</button>' : '<a class="small" href="#home">I choose not to take part</a>'}${step ? '<button type="button" class="link-button" data-action="save-exit">Save and exit</button>' : ''}</div>${button(step === 4 ? 'Submit demo assessment' : step === 3 ? 'Review my answers' : 'Continue')}</div><p id="save-status" class="save-status" role="status">${state.saveTime ? 'Last saved to your session · '+fmt(state.saveTime) : 'Your choices are not yet saved.'}</p></form></div>`,'');
  $('#assessment-form').addEventListener('input', () => {
    readAnswers();
    if (step === 0) $('#minor-path').hidden = !(a.age && a.age < 18);
    ['gender','education','platforms'].forEach(key => { const group=$(`[data-field="${key}"]`); if (group) { const other=$('.other-field',group); const v=a[key]; if(other) other.hidden=!(v==='other'||Array.isArray(v)&&v.includes('other')); } });
    const count=$('.platform-count'); if(count) count.textContent=(a.platforms?.length||0)+' selected';
    $('#save-status').textContent='Unsaved changes · Your answers are kept on this page until you save.';
  });
  $('#assessment-form').addEventListener('submit', async event => {
    event.preventDefault(); readAnswers();
    const errors=validateStep();
    if(Object.keys(errors).length) { const error=new Error('Please check these answers.'); error.fields=errors; errorBox(error); return; }
    const form=event.currentTarget;
    const run=()=>pending(form,async()=>{
      try {
        if(step===4) { const data=await api('/assessment/submit','POST',{answers:state.answers,submission_id:state.submissionId}); state.assessment.submission=data.submission; state.answers={}; state.step=0; announce('Assessment submitted.'); summary(); }
        else { await saveDraft(step+1); state.step++; assessmentPage(); $('#main').focus(); window.scrollTo(0,0); }
      } catch(error) { errorBox(error); }
    });
    state.retry=run; await run();
  });
}
function answerLabel(key,value,a) {
  if(value === undefined || value === null) return 'Missing answer';
  if(Array.isArray(value)) return value.map(v => labels[key]?.[v] || v).join(', ') + (a[key+'_other'] ? ' — '+a[key+'_other'] : '');
  return (labels[key]?.[value] || String(value)) + (value==='other' && a[key+'_other'] ? ' — '+a[key+'_other'] : '');
}
function answersTable(a, plain=false) {
  const titles=plain?{...questions,platforms:'Social media apps you use',daily_time:'Time on social media each day',passive:'Scrolling without liking, commenting or posting',active:'Posting, commenting or messaging',night:'Using social media after 11 pm',cyberbullying:'Being bullied online',regular_count:'How many apps you use regularly'}:questions;
  return `<table class="summary-table"><caption class="sr-only">Your answers</caption><tbody>${Object.entries(titles).map(([key,label])=>`<tr><th scope="row">${esc(label)}</th><td>${esc(answerLabel(key,a[key],a))}</td></tr>`).join('')}</tbody></table>`;
}
function modelOutput(r) {
  const p=r.prediction;
  const trained=p?.source==='synthetic_model';
  const provenance=trained
    ? `<p>Training data: synthetic records generated for this project. Clinical validation has not been performed.</p><p>Model version: ${esc(r.model_version)}. These probabilities describe the model output; they are not calibrated probabilities of a mental-health condition.</p>`
    : `<p>${esc(p?.reason||r.model_reason||'No saved model prediction is available.')}</p>`;
  return `<h2>${trained?'Research model estimate':r.estimate?'Illustrative model estimate':'No model estimate available'}</h2>
    ${r.estimate?`<p class="estimate-title">${estimateTag(r.estimate)}</p>`:''}
    <p class="small muted">Research prototype · not clinically validated.</p>
    <p class="small">Interpret alongside the assessment and professional review. This estimate does not determine diagnosis or urgency.</p>
    ${r.answers&&r.estimate?`<div class="section-block">${resultExplanation(r)}</div>`:''}
    ${infoDetails('Model information',provenance)}
    ${trained&&p.probabilities?infoDetails('Class probabilities',`<p>Research model outputs; not calibrated clinical probabilities.</p><table class="summary-table"><thead><tr><th>Class</th><th>Model probability</th></tr></thead><tbody>${['Low','Moderate','High'].map(label=>`<tr><th scope="row">${label}</th><td>${(p.probabilities[label]*100).toFixed(1)}%</td></tr>`).join('')}</tbody></table>`):''}`;
}
function resultExplanation(r) {
  const explanation=r.explanation||r.prediction?.explanation;
  const wording={daily_time:'Time on social media each day',passive:'Scrolling without liking, commenting or posting',active:'Posting, commenting or messaging',night:'Using social media after 11 pm',cyberbullying:'Being bullied online',regular_count:'How many apps you use regularly'};
  if(!explanation)return `<h3>About this result</h3><p>A detailed explanation is not available for this saved result. A counsellor can review your answers with you.</p>`;
  const changed=explanation.factors.filter(f=>wording[f.feature]&&Math.abs(f.contribution)>0.000001&&r.answers[f.feature]===f.answer);
  const toward=changed.filter(f=>f.direction==='toward');
  const factors=(toward.length?toward:changed.sort((a,b)=>Math.abs(b.contribution)-Math.abs(a.contribution))).slice(0,3);
  const lead=toward.length?`These answers helped the model choose the ${esc(r.estimate)} group:`:factors.length?`Your answers overall matched the ${esc(r.estimate)} group. These answers also moved the estimate toward ${esc(explanation.compared_class)}, but the overall result stayed ${esc(r.estimate)}:`:`No single reported habit stood out. Your habits were similar to the model's usual starting pattern, and it chose ${esc(r.estimate)} from your answers together.`;
  return `<h3>What influenced this result?</h3><p>${lead}</p>${factors.length?`<ul>${factors.map(f=>`<li><strong>${esc(wording[f.feature])}</strong>: ${esc(answerLabel(f.feature,f.answer,r.answers))}.</li>`).join('')}</ul>`:''}<p class="small muted">Other answers were considered too. These explain the model's estimate; they do not show what caused a health problem.</p>`;
}
function participantResult(r) {
  if(!r.estimate)return `<p class="eyebrow">YOUR RESULT</p><h2>Result not available</h2><p>Your answers are saved, but an estimate could not be produced. You can still seek support or discuss your answers with a counsellor.</p>`;
  return `<p class="eyebrow">YOUR RESULT</p><h2>Assessment result: ${esc(r.estimate)}</h2><p>Your answers matched the ${esc(r.estimate)} group most closely.</p><p class="small muted">This project's estimate is not a diagnosis. A counsellor can help you understand it.</p><div class="section-block">${resultExplanation(r)}</div>${r.estimate==='Low'?'<p>A Low result does not mean you cannot be struggling. You can ask for support whatever your result.</p>':'<p>If anything in your answers is worrying you, consider discussing it with a counsellor or someone you trust.</p>'}`;
}
function summary() {
  shell(false,'assessment'); const r=state.assessment.submission;
  const review={
    'Needs review':['Waiting for review','Your answers are saved and are waiting to be reviewed.'],
    'In progress':['Review started','A clinician has started reviewing your answers.'],
    'Follow-up arranged':['Follow-up recorded','A clinician has recorded a follow-up plan. Ask your clinician about the next steps.'],
    'Closed':['Review completed','A clinician has marked this review as complete.'],
  }[r.review_state]||['Answers received','Your answers have been saved.'];
  const habits=[['daily_time','Time on social media each day'],['night','Using social media after 11 pm'],['cyberbullying','Being bullied online']];
  main(`<div class="page-grid"><article>
  ${heading('YOUR ASSESSMENT','Thank you for sharing.',fmt(r.submitted_at))}
  <div class="receipt"><strong>${icon('check')} Your answers have been saved.</strong><p class="small">Your reference: ${esc(r.participant_id)}</p></div>
  <section class="section-block panel" id="assessment-result">${participantResult(r)}</section>
  <section class="section-block"><p class="eyebrow">CLINICIAN REVIEW</p><h2>${esc(review[0])}</h2><p>${esc(review[1])}</p></section>
  <section class="section-block"><h2>What you shared</h2><p>A quick look at the online habits you told us about.</p><table class="summary-table"><caption class="sr-only">Your answers about online habits</caption><tbody>${habits.map(([key,label])=>`<tr><th scope="row">${label}</th><td>${esc(answerLabel(key,r.answers[key],r.answers))}</td></tr>`).join('')}</tbody></table><p class="small muted">Online habits are only one part of your life. These answers alone cannot tell us how you are feeling.</p></section>
  <details class="section-block"><summary>View all my answers</summary>${answersTable(r.answers,true)}</details>
  ${infoDetails('About this assessment','<p>You answered questions about your online habits. A full mental-health assessment has not been completed.</p><p>This project is not a live counselling service. No one is monitoring these answers or support requests. If you need support, contact someone directly.</p>')}
</article><aside class="guidance"><p class="guide-label">SUPPORT</p><h2>Want to talk?</h2><p>If something is worrying you, you can talk with someone you trust or a qualified counsellor.</p><a href="#support" class="button small">Explore support ${icon('arrow')}</a><hr><p class="small">This app is not a live counselling or emergency service. Contact someone directly if you need help.</p></aside></div>`);
}

async function support(requestForm=false) {
  shell(false,'support');
  main(`<div class="page-grid"><article>
  ${heading('SUPPORT','Talk to someone.','You can seek support without an assessment or a particular result.')}
  <div class="notice warning"><strong>Need help now?</strong><p>In immediate danger, contact local emergency services or the nearest emergency department. Ask someone you trust to stay with you if possible. This app cannot provide emergency help.</p></div>
  <section class="section-block"><h2>Local services</h2><p>No verified local directory is connected yet.</p>${infoDetails('What the directory will include','<p>Each verified service will show its name, eligibility, hours, contact method and last verification date. Contacts appear only after the operator checks them.</p>')}</section>
  <section class="section-block"><h2>Request a conversation</h2><p class="small muted"><strong>Requests are not monitored.</strong> Use example contact details. No response time is promised.</p><div class="error-slot"></div><div id="support-receipt"></div>
  ${state.user?.role==='participant' ? `<form id="support-form"><div class="field"><label for="contact-method">Preferred contact method</label><select id="contact-method" name="method" required><option value="">Choose a method</option><option value="email">Email</option><option value="phone">Phone</option></select></div><div class="field"><label id="contact-details-label" for="contact-details">Example contact details</label><input id="contact-details" name="details" maxlength="200" autocomplete="off" required placeholder="alex@example.com"></div><div class="field"><label for="contact-times">Suitable contact times</label><input id="contact-times" name="times" required maxlength="300" placeholder="For example, weekday afternoons"></div><label class="check-line"><input type="checkbox" name="permission" required><span>I allow my assigned clinician to see this request and its example contact details.</span></label>${button('Record demo request')}</form>` : `<a href="#access" class="button">${state.user ? 'Use assessment access' : 'Sign in to request contact'} ${icon('arrow')}</a>`}
  </section>
</article><aside class="guidance"><p class="guide-label">YOUR CHOICE</p>${icon('heart')}<h2>Share what<br>you choose.</h2><p>Contact is optional and separate from your assessment.</p>${infoDetails('Confidentiality','<p>Live services must explain confidentiality limits and safeguarding responsibilities before collecting information. Declining contact does not affect your assessment.</p>')}<a href="#privacy">Privacy and choices ${icon('arrow')}</a></aside></div>`);
  $('#contact-method')?.addEventListener('change',event=>{ const email=event.target.value==='email'; $('#contact-details').type=email?'email':'tel'; $('#contact-details').placeholder=email?'alex@example.com':'Example phone number'; $('#contact-details-label').textContent=email?'Demo email address':'Demo phone number'; });
  $('#support-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget;
    const run=()=>pending(form,async()=>{try{const data=Object.fromEntries(new FormData(form));data.permission=data.permission==='on';const result=await api('/support','POST',data);$('#support-receipt').innerHTML=`<div class="receipt" tabindex="-1"><strong>${esc(result.status)}</strong><p>Reference: ${esc(result.reference)}</p><p class="small">${fmt(result.created)}<br>No one is monitoring this demo request.</p></div>`;form.hidden=true;$('#support-receipt .receipt').focus();announce('Demo request recorded.');}catch(error){errorBox(error);}});
    state.retry=run;await run();
  });
  if(requestForm) $('#support-form')?.scrollIntoView();
}

async function privacy() {
  shell(false,'privacy');
  const requests=state.user?.role==='participant' ? (await api('/privacy/requests')).requests : [];
  main(`<div class="page-grid"><article>
  ${heading('PRIVACY','Your information.<br>Your choice.','What is stored, who sees it and what you can change.')}
  <section class="section-block"><p class="eyebrow">01 / INFORMATION</p><h2>What we collect</h2><p>Your assessment answers and participation choices. Optional contact details are kept separately.</p>${infoDetails('Collection and storage details','<p>Answers include age, background and social media habits. Wellbeing questionnaires are disabled. Drafts are saved on the server, not in browser storage.</p><p>We do not connect to social media accounts, read messages or monitor your phone. Sensitive answers are not put in URLs, analytics, localStorage or offline caches.</p>')}</section>
  <section class="section-block"><p class="eyebrow">02 / ACCESS</p><h2>Who can see it</h2><p>You see your own answers. Clinicians see assigned cases; insights users see aggregates. Optional follow-up can link your identity to your record.</p>${infoDetails('Roles and confidentiality','<p>Administrators manage accounts and assignments. Sensitive access and review changes are logged.</p><p>Records use participant IDs. This is pseudonymous, not fully anonymous when a permitted identity link exists. Live confidentiality limits and safeguarding responsibilities require approved wording before collection.</p>')}</section>
  <section class="section-block"><p class="eyebrow">03 / RETENTION</p><h2>How long it is kept</h2><p>Local records remain until reset. A live retention policy is not configured.</p>${infoDetails('Sessions and saved work','<p>Use example details only. Sessions expire after 30 minutes. Signing out clears unsaved answers from this page.</p><p>Signing back into the same account recovers only server-saved work. Temporary access-code sessions cannot be recovered after sign-out.</p>')}</section>
  <section class="section-block"><p class="eyebrow">04 / YOUR CHOICES</p><h2>Manage participation</h2><p><strong>Stop participating:</strong> closes assessment access and deletes an unsubmitted draft. Submitted records remain.</p><p><strong>Request removal:</strong> asks the operator to review deletion; it does not erase information immediately.</p>${infoDetails('Removal and retention limits','<p>Any exceptions or retention obligations for live use must be explained in the approved policy. A request receives a reference and progress state.</p>')}<div class="error-slot"></div>
  ${state.user?.role==='participant' ? '<div class="form-actions"><button class="button secondary" data-privacy="withdraw">Stop participating</button><button class="button secondary" data-privacy="removal">Request removal of my information</button></div>' : '<p class="small"><a href="#access">Sign in</a> to manage your participation.</p>'}
  <div id="privacy-receipts" style="margin-top:24px">${requests.map(r=>`<div class="receipt" style="margin-top:12px"><strong>${esc(r.status)}</strong><p class="small">${esc(r.reference)} · ${fmt(r.created)}</p></div>`).join('')}</div></section>
</article><aside class="guidance"><p class="guide-label">SHARED DEVICE?</p>${icon('lock')}<h2>Save. Sign out.</h2><p>Save your answers before leaving. Sign out when you finish.</p><hr><p>You can stop, decline follow-up or seek support without completing an assessment.</p><a href="#support">Explore support ${icon('arrow')}</a></aside></div>`);
}

function restricted(title='Access restricted',message='Your account does not have permission to view this workspace.') {
  shell(false);main(`<div class="assessment-wrap">${heading('ACCESS RESTRICTED',esc(title),esc(message))}<a href="#home" class="button">Return home ${icon('arrow')}</a><p class="small" style="margin-top:24px">To use another demo role, sign out and select an appropriate account on the staff sign-in page.</p></div>`);
}
function staffAllowed(roles) {
  if(!state.user){location.hash='#access/staff';return false;}
  if(!roles.includes(state.user.role)){restricted();return false;}
  return true;
}

async function queue(mode='queue') {
  if(!staffAllowed(['counsellor']))return;
  state.cases=(await api('/cases')).cases;
  const q=state.queue;
  const counts=status=>state.cases.filter(r=>r.review_state===status).length;
  staffShell(`<div class="staff-topline">${heading('CLINICIAN WORKSPACE / ASSIGNED CASES',mode==='participants'?'Young people':mode==='reports'?'Reports':'Review queue',mode==='reports'?'Open a case to create an assessment summary.':'Review assigned assessments and plan follow-up.')}<button class="icon-button" data-action="refresh-queue">${icon('refresh')}Refresh</button></div><div class="staff-stats">${['Needs review','In progress','Follow-up arranged','Closed'].map(status=>`<a href="#" data-count-filter="${status}">${status}<strong>${String(counts(status)).padStart(2,'0')}</strong></a>`).join('')}</div><div class="queue-filters"><div><label for="queue-search">Search by person ID</label><input id="queue-search" type="search" value="${esc(q.search)}" placeholder="e.g. P-0142"></div><div><label for="queue-status">Review state</label><select id="queue-status"><option value="">All review states</option>${['Needs review','In progress','Follow-up arranged','Closed'].map(s=>`<option ${q.status===s?'selected':''}>${s}</option>`).join('')}</select></div><div><label for="queue-estimate">Model estimate</label><select id="queue-estimate"><option value="">All estimates</option>${['Low','Moderate','High','No estimate'].map(s=>`<option ${q.estimate===s?'selected':''}>${s}</option>`).join('')}</select></div></div><div class="filter-more"><label class="check-line"><input type="checkbox" id="queue-missing" ${q.missing?'checked':''}>Missing information</label><label for="queue-date">Submitted from <input id="queue-date" type="date" value="${esc(q.date)}"></label><label for="queue-sort">Sort <select id="queue-sort"><option value="newest" ${q.sort==='newest'?'selected':''}>Updated: newest</option><option value="oldest" ${q.sort==='oldest'?'selected':''}>Updated: oldest</option><option value="id" ${q.sort==='id'?'selected':''}>Person ID</option></select></label><button class="link-button" data-action="clear-filters">Clear filters</button></div><div id="active-filters" class="active-filters" aria-live="polite"></div><div id="queue-results"></div><p class="tiny muted" style="margin-top:28px">Research prototype. Model estimates do not determine clinical urgency; wellbeing questionnaires were not administered.</p>`,mode);
  ['search','status','estimate','missing','date','sort'].forEach(key=>{
    const el=$('#queue-'+key);el.addEventListener(key==='search'?'input':'change',()=>{q[key]=key==='missing'?el.checked:el.value;q.page=1;queueResults();});
  });
  queueResults();
}
function queueResults() {
  const q=state.queue;
  let rows=state.cases.filter(r=>(!q.search||r.participant_id.toLowerCase().includes(q.search.toLowerCase()))&&(!q.status||r.review_state===q.status)&&(!q.estimate||(r.estimate||'No estimate')===q.estimate)&&(!q.missing||!r.complete)&&(!q.date||r.submitted_at.slice(0,10)>=q.date));
  rows.sort((a,b)=>q.sort==='id'?a.participant_id.localeCompare(b.participant_id):q.sort==='oldest'?a.updated.localeCompare(b.updated):b.updated.localeCompare(a.updated));
  const total=rows.length;const max=Math.max(1,Math.ceil(total/6));q.page=Math.min(q.page,max);rows=rows.slice((q.page-1)*6,q.page*6);
  $('#active-filters').textContent=[q.search&&'ID: '+q.search,q.status,q.estimate,q.missing&&'Missing information',q.date&&'From '+q.date].filter(Boolean).join(' · ')||'Showing all assigned assessments';
  $('#queue-results').innerHTML=total?`<table class="queue-table"><caption class="sr-only">Assigned review queue</caption><thead><tr><th>Person ID</th><th>Model estimate</th><th>Review state</th><th>Updated</th><th><span class="sr-only">Open</span></th></tr></thead><tbody>${rows.map(r=>`<tr><td data-label="Person"><a class="pid" href="#staff/case/${r.participant_id}/overview">${r.participant_id}</a></td><td data-label="Model estimate">${estimateTag(r.estimate)}<span class="condition">${r.prediction?.source==='synthetic_model'?'Research model':r.estimate?'Illustrative record':'No saved prediction'}</span></td><td data-label="Review state">${reviewTag(r.review_state)}<span class="condition">${!r.complete?'Wellbeing not administered':''}</span></td><td data-label="Updated">${shortDate(r.updated)}</td><td class="row-arrow" aria-hidden="true">→</td></tr>`).join('')}</tbody></table><div class="table-end"><span>${(q.page-1)*6+1}–${Math.min(q.page*6,total)} of ${total} participants</span><div class="pagination"><button data-page="${q.page-1}" ${q.page===1?'disabled':''}>← Previous</button><button data-page="${q.page+1}" ${q.page===max?'disabled':''}>Next →</button></div></div>`:`<div class="empty-state"><h2>${state.cases.length?'No assigned assessments match these filters':'No assigned assessments need review'}</h2><p>${state.cases.length?'Try another participant ID or clear your filters.':'Your administrator assigns participants to your workspace. Refresh to check for new assignments.'}</p><button class="button secondary" data-action="${state.cases.length?'clear-filters':'refresh-queue'}">${state.cases.length?'Clear filters':'Refresh'}</button></div>`;
}

async function caseDetail(pid,tab='overview') {
  if(!staffAllowed(['counsellor']))return;
  const r=(await api('/cases/'+encodeURIComponent(pid))).case;state.case=r;
  let content='';
  if(tab==='overview')content=`<section class="record-section">${modelOutput(r)}<p class="tiny muted">Created ${fmt(r.submitted_at)}</p></section><section class="record-section"><h2>What the participant reported</h2><table class="summary-table"><tbody>${['passive','night','active'].map(key=>`<tr><th scope="row">${questions[key]}</th><td>${esc(answerLabel(key,r.answers[key],r.answers))}</td></tr>`).join('')}</tbody></table><p class="small muted">Self-reported habits are observations, not explanations or evidence of causation.</p></section><section class="record-section"><h2>Questionnaire results</h2>${r.instruments.map(i=>`<div class="instrument-row"><h3>${i.name}</h3><span class="tag unavailable">Not administered · no score</span></div>`).join('')}</section><section class="record-section"><h2>Data quality</h2><p>Questionnaire version: ${esc(r.questionnaire_version)}. Behavioural answers ${Object.keys(questions).some(k=>r.answers[k]===undefined)?'have missing information':'are available'}. Wellbeing questionnaires were not administered.</p></section><section class="record-section"><h2>Optional contact</h2>${r.contact?`<p><strong>${esc(r.contact.method)}</strong>: ${esc(r.contact.details)}</p><p>Suitable times: ${esc(r.contact.times)}</p>`:'<p>No authorised contact details.</p>'}</section>`;
  else if(tab==='responses')content=`<section class="record-section"><h2>Submitted responses</h2><p class="small muted">${esc(r.questionnaire_version)} · Demo question wording<br>Assessment: ${fmt(r.submitted_at)}</p>${answersTable(r.answers)}</section>`;
  else content=`<section class="record-section"><h2>Review and follow-up history</h2><p class="small muted" style="margin-bottom:24px">Staff-only notes; not automatically shared with the young person.</p>${r.events.length?`<ol class="timeline">${r.events.map(e=>`<li><time>${fmt(e.created)}</time><h3>${esc(e.status)}</h3><p>${esc(e.actor)}</p>${e.note?`<p>${esc(e.note)}</p>`:''}${e.owner?`<p>Owner: ${esc(e.owner)} · Due: ${esc(e.due_date||'Not set')}</p>`:''}${e.outcome?`<p>Outcome / next action: ${esc(e.outcome)}</p>`:''}</li>`).join('')}</ol>`:'<p>No review events have been recorded yet.</p>'}</section>`;
  staffShell(`<a class="back-link" href="#staff/queue">${icon('back')}Back to review queue</a><div class="staff-topline">${heading('ASSESSMENT RECORD / EXAMPLE','Record '+esc(pid),'Assigned to you · Assessment '+fmt(r.submitted_at))}<a class="icon-button" href="#staff/report/${esc(pid)}">${icon('file')}Print report</a></div><nav class="record-tabs" aria-label="Assessment record">${['overview','responses','follow-up'].map(t=>`<a href="#staff/case/${esc(pid)}/${t}" class="${t===tab?'active':''}" ${t===tab?'aria-current="page"':''}>${t==='follow-up'?'Follow-up':t[0].toUpperCase()+t.slice(1)}</a>`).join('')}</nav><div class="record-grid"><article>${content}</article><aside class="panel review-panel"><h2>Review and follow-up</h2><p class="tiny muted">Confidential · assigned staff only<br>Record version ${r.version}</p><form id="review-form"><div class="error-slot"></div><div class="field"><label for="review-status">Review status</label><select id="review-status" name="status">${['Needs review','In progress','Follow-up arranged','Closed'].map(s=>`<option ${r.review_state===s?'selected':''}>${s}</option>`).join('')}</select></div><div class="field"><label for="review-note">Confidential note</label><textarea id="review-note" name="note" maxlength="2000" placeholder="Add a confidential note…"></textarea></div><div class="field"><label for="review-owner">Follow-up owner</label><input id="review-owner" name="owner" maxlength="100" value="${esc(state.user.name)}"></div><div class="field"><label for="review-due">Follow-up due date</label><input id="review-due" name="due_date" type="date"></div><div class="field"><label for="review-outcome">Next action or closure reason</label><textarea id="review-outcome" name="outcome" maxlength="500"></textarea><small>Required for follow-up, closure or reopening.</small></div>${button('Save review')}<p class="save-status" id="review-saved" role="status"></p></form><p class="tiny muted">Review status does not change the model output.</p></aside></div>`,'participants');
  $('#review-form').addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget;
    const run=()=>pending(form,async()=>{try{const data=Object.fromEntries(new FormData(form));data.version=r.version;const saved=await api('/cases/'+pid+'/review','POST',data);r.version=saved.version;r.review_state=data.status;$('#review-saved').textContent='Saved · '+fmt(saved.updated);$('.error-slot',form).innerHTML='';announce('Review saved.');}catch(error){errorBox(error,form);if(error.status===409)$('.error-slot',form).insertAdjacentHTML('beforeend','<button class="button secondary small" type="button" data-action="reload-case">Reload record</button>');}});
    state.retry=run;await run();
  });
}

async function report(pid) {
  if(!staffAllowed(['counsellor']))return;
  const data=await api('/cases/'+encodeURIComponent(pid)+'/report');const r=data.report;const last=r.events.at(-1);
  staffShell(`<div class="no-print"><a class="back-link" href="#staff/case/${esc(pid)}/overview">${icon('back')}Back to participant</a><button class="button small" data-action="print">Print / save as PDF ${icon('file')}</button></div><article class="report"><p class="eyebrow">BETWEEN / ASSESSMENT REPORT</p><h1>Assessment summary</h1><div class="report-meta">Participant ID: <strong>${esc(pid)}</strong><br>Assessment: ${fmt(r.submitted_at)}<br>Report generated: ${fmt(data.generated_at)}</div><div class="notice warning">For professional review. Model estimates are research outputs and do not determine diagnosis or clinical urgency.</div><section class="record-section">${modelOutput(r)}</section><section class="record-section"><h2>Questionnaire results</h2>${r.instruments.map(i=>`<p>${i.name}: ${i.status}; no score.</p>`).join('')}</section><section class="record-section"><h2>Human review</h2><p>Review status: ${esc(r.review_state)}<br>Agreed next action: ${esc(last?.outcome||'No next action recorded')}<br>Owner: ${esc(last?.owner||'Not recorded')}<br>Due date: ${esc(last?.due_date||'Not recorded')}</p></section><p class="tiny muted">Questionnaire version: ${esc(r.questionnaire_version)}. Model output, questionnaire scores and clinician judgement are separate. Example service; not monitored.</p></article>`,'reports');
}

function metric(value) { return typeof value==='number' ? (value*100).toFixed(1)+'%' : 'Unavailable'; }
function datasetQuality(m) {
  const c=m.cleaning;
  return `<section class="section-block"><h2>Training data quality</h2><p>Fictional participants generated for this project. Training rows are separate from app submissions; no contact details or clinical records are used.</p><table class="summary-table"><tbody>${[
    ['Dataset',m.dataset||'Unavailable'],['Behaviour questionnaire','Appendix A reviewed; current app merges the 1–2 and 2–3 hour bands'],
    ['Raw rows',c?.raw_rows??'Unavailable'],['Invalid rows removed',c?.invalid_rows_removed??'Unavailable'],
    ['Duplicate participants removed',c?.duplicates_removed??'Unavailable'],['Clean synthetic participants',c?.clean_rows??'Unavailable'],
    ['Missing values','Imputed within training folds; incomplete app input receives no prediction'],
    ['Wellbeing instruments','Not administered in the app; simulated totals are training labels only'],
  ].map(([label,value])=>`<tr><th scope="row">${esc(label)}</th><td>${esc(value)}</td></tr>`).join('')}</tbody></table></section>`;
}
function modelEvaluation(m) {
  if(!m.available)return `${heading('INSIGHTS','Model evaluation','Research model unavailable.')}<div class="notice warning">${esc(m.reason)}</div><div class="empty-state"><h2>No stored evaluation results</h2><p>Assessment answers can still be saved without a model estimate.</p></div>`;
  const stats=m.metrics, labels=m.label_order;
  return `${heading('INSIGHTS / MODEL DEVELOPMENT','Model evaluation','Performance, validation and training information.')}
    <div class="notice"><strong>Research prototype · not clinically validated.</strong><p>Evaluation uses synthetic data. These metrics measure development performance and do not establish clinical accuracy.</p></div>
    <section class="panel"><h2>Training record</h2><table class="summary-table"><tbody>${[
      ['Model version',m.version],['Selected algorithm',m.algorithm],['Training dataset',m.dataset],['Target definition',m.target],
      ['Evaluation date',fmt(m.evaluation_date)],['Split',`${m.split.train} train / ${m.split.validation} validation / ${m.split.test} test`],
      ['Selection',m.split.method],['Clinical validation','Not released for clinical use'],
    ].map(([label,value])=>`<tr><th scope="row">${esc(label)}</th><td>${esc(value)}</td></tr>`).join('')}</tbody></table></section>
    <section class="section-block"><h2>Test-set performance</h2><p class="small muted">${m.test_sample_size} synthetic participants. Precision, recall and F1 use macro averaging; AUC uses one-vs-rest macro averaging. Recall is sensitivity.</p>
    <table class="summary-table"><thead><tr><th>Metric</th><th>Selected model</th><th>Majority baseline</th></tr></thead><tbody>${[
      ['Accuracy','accuracy'],['Precision (macro)','precision_macro'],['Recall / sensitivity (macro)','recall_macro'],
      ['F1 (macro)','f1_macro'],['ROC AUC (OvR macro)','roc_auc_ovr_macro'],
    ].map(([label,key])=>`<tr><th scope="row">${label}</th><td>${metric(stats[key])}</td><td>${metric(m.baseline[key])}</td></tr>`).join('')}</tbody></table></section>
    <section class="section-block"><h2>Per-class performance</h2><div class="data-scroll" role="region" aria-label="Per-class model metrics" tabindex="0"><table class="summary-table"><thead><tr><th>Class</th><th>Test count</th><th>Precision</th><th>Sensitivity</th><th>Specificity (OvR)</th><th>F1</th></tr></thead><tbody>${labels.map(label=>`<tr><th scope="row">${label}</th><td>${stats.class_counts[label]}</td><td>${metric(stats.per_class[label].precision)}</td><td>${metric(stats.per_class[label].recall)}</td><td>${metric(stats.specificity_ovr[label])}</td><td>${metric(stats.per_class[label]['f1-score'])}</td></tr>`).join('')}</tbody></table></div></section>
    <section class="section-block"><h2>Confusion matrix</h2><p class="small muted">Rows = actual simulated class. Columns = predicted class.</p><div class="data-scroll" role="region" aria-label="Confusion matrix" tabindex="0"><table class="summary-table"><caption class="sr-only">Synthetic test confusion matrix, actual rows and predicted columns</caption><thead><tr><th>Actual / predicted</th>${labels.map(label=>`<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>${labels.map((label,i)=>`<tr><th scope="row">${label}</th>${m.confusion_matrix[i].map(count=>`<td>${count}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>
    <section class="section-block"><h2>Algorithm comparison</h2><p class="small muted">Hyperparameters tuned using three training folds. Validation macro-F1 selects the algorithm before final refitting. Test data is excluded from fitting and selection.</p><div class="data-scroll" role="region" aria-label="Algorithm comparison" tabindex="0"><table class="summary-table"><thead><tr><th>Algorithm</th><th>Training CV F1</th><th>Validation accuracy</th><th>Validation F1</th><th>Validation AUC</th></tr></thead><tbody>${m.comparisons.map(c=>`<tr><th scope="row">${esc(c.algorithm)}${c.algorithm===m.algorithm?' (selected)':''}</th><td>${metric(c.cv_f1_macro)}</td><td>${metric(c.validation.accuracy)}</td><td>${metric(c.validation.f1_macro)}</td><td>${metric(c.validation.roc_auc_ovr_macro)}</td></tr>`).join('')}</tbody></table></div></section>
    <section class="section-block"><h2>Feature importance in the simulation</h2><p class="small muted">Validation permutation importance: mean decrease in macro-F1 over five shuffles. Correlated features can share importance. These are simulator associations, not clinical explanations or causes.</p><table class="summary-table"><thead><tr><th>Input</th><th>Mean F1 decrease</th></tr></thead><tbody>${m.feature_importance.map(f=>`<tr><th scope="row">${esc(questions[f.feature]||f.feature)}</th><td>${f.mean_f1_decrease.toFixed(4)}</td></tr>`).join('')}</tbody></table></section>${datasetQuality(m)}`;
}
async function research(mode='research') {
  if(!staffAllowed(['researcher']))return;
  const r=await api('/research');
  let content='';
  if(mode==='model')content=modelEvaluation(r.model);
  else content=`<div class="staff-topline">${heading('INSIGHTS / AGGREGATE DEMO DATA',mode==='dataset'?'Data quality':'Insights overview','Aggregate information only. No individual records or contact details.')}<a class="icon-button" href="/api/research/export" download>${icon('file')}Export totals</a></div><div class="research-metrics"><div><strong>${r.total}</strong><span>Demo submissions</span></div><div><strong>${r.complete} / ${r.total}</strong><span>All instruments complete</span></div><div><strong>${r.model.available?'Research prototype':'Unavailable'}</strong><span>Model status</span></div></div><div class="research-grid"><section class="panel"><h2>Model output distribution</h2><p class="small muted">All assessment records; includes illustrative records</p>${r.distribution.map(d=>`<div class="bar-row"><span>${d.label}</span><div class="bar-track"><div class="bar-fill ${cls(d.label)}" data-width="${r.total?d.count/r.total*100:0}"></div></div><output>${d.count} / ${r.total}</output></div>`).join('')}<details><summary class="small">View the same data as a table</summary><table class="summary-table"><thead><tr><th>Class</th><th>Count / all submissions</th></tr></thead><tbody>${r.distribution.map(d=>`<tr><th scope="row">${d.label}</th><td>${d.count} / ${r.total}</td></tr>`).join('')}</tbody></table></details></section><aside><div class="notice warning" style="margin-top:0"><strong>Completeness is separate from class.</strong><p>PHQ-9, GAD-7 and WEMWBS were not administered. “No estimate” is separate from Low.</p></div><section class="panel"><h2>Protecting small groups</h2><p class="small muted">${esc(r.suppression)}</p><p class="small muted">This demo shows the whole demo cohort only.</p><a href="#staff/model">View model evaluation ${icon('arrow')}</a></section></aside></div>${mode==='dataset'?datasetQuality(r.model):''}<p class="tiny muted" style="margin-top:24px">Research estimates require professional review and clinical validation.</p>`;
  staffShell(content,mode);$$('[data-width]').forEach(bar=>bar.style.width=bar.dataset.width+'%');
}

let adminData=null;
async function administration(mode='admin') {
  if(!staffAllowed(['administrator']))return;
  const r=await api('/admin');adminData=r;
  let content='';
  if(mode==='admin') content=`<div class="staff-topline">${heading('RESTRICTED ADMINISTRATION','Accounts & roles','Manage staff access. Assessment answers are restricted.')}<button class="button small" data-action="invite">Create demo staff account ${icon('arrow')}</button></div><div class="error-slot"></div><div class="data-scroll" role="region" aria-label="Staff accounts" tabindex="0"><table class="summary-table"><thead><tr><th>Name</th><th>Role</th><th>Access</th><th>Action</th></tr></thead><tbody>${r.accounts.map(a=>`<tr><th scope="row">${esc(a.name)}<br><span class="tiny muted">${esc(a.email)}</span></th><td>${esc(roleName(a.role))}</td><td>${a.active?'Active':'Inactive'}</td><td>${a.id!==state.user.id?`<button class="link-button" data-account-edit="${esc(a.id)}">Edit access</button>`:'Your account'}</td></tr>`).join('')}</tbody></table></div>`;
  if(mode==='assignments')content=`${heading('RESTRICTED ADMINISTRATION','Assignments','Assign active clinicians. Changes are recorded in access history.')}<div class="error-slot"></div><div class="data-scroll" role="region" aria-label="Participant assignments" tabindex="0"><table class="summary-table"><thead><tr><th>Person ID</th><th>Current owner</th><th>Action</th></tr></thead><tbody>${r.assignments.map(a=>`<tr><th scope="row">${esc(a.participant_id)}</th><td>${esc(r.accounts.find(u=>u.id===a.assigned_to)?.name||'Unassigned')}</td><td><button class="link-button" data-assignment="${esc(a.participant_id)}">Change owner</button></td></tr>`).join('')}</tbody></table></div>`;
  if(mode==='configuration')content=`${heading('RESTRICTED ADMINISTRATION','Workspace settings','Versioned settings. Live collection remains disabled.')}<div class="error-slot"></div>${r.config.map(c=>`<section class="admin-card"><p class="version">VERSION ${c.version}</p><h3>${({consent:'Consent and assent',questionnaire:'Questionnaire configuration',support_directory:'Support directory',enrolment:'Enrolment status'})[c.key]}</h3>${infoDetails('Configuration details',`<p class="break-word">${esc(c.value)}</p>`)}${c.key==='enrolment'?'<span class="tag unavailable">Live enrolment locked</span>':`<button class="link-button" data-config="${esc(c.key)}">Edit demo configuration</button>`}</section>`).join('')}<section class="admin-card"><h3>Research model</h3><p>${r.model.available?esc(r.model.algorithm)+' / '+esc(r.model.version)+' / research prototype.':esc(r.model.reason)}</p><span class="tag unavailable">Not clinically validated</span></section><p class="tiny muted">Settings notes do not activate questionnaires, change consent or verify services.</p>`;
  if(mode==='audit')content=`${heading('RESTRICTED ADMINISTRATION','Access history','Latest 100 access and change events.')}<div class="audit-tools"><input type="search" id="audit-search" placeholder="Filter by actor, action or record" aria-label="Search access history"><select id="audit-action" aria-label="Filter by action"><option value="">All actions</option>${[...new Set(r.audit.map(e=>e.action))].map(a=>`<option>${esc(a)}</option>`).join('')}</select></div><div id="audit-results"></div>`;
  staffShell(content,mode);
  if(mode==='audit'){
    const draw=()=>{const search=$('#audit-search').value.toLowerCase(),action=$('#audit-action').value;const rows=r.audit.filter(e=>(!search||[e.actor,e.action,e.target].join(' ').toLowerCase().includes(search))&&(!action||e.action===action));$('#audit-results').innerHTML=`<div class="data-scroll" role="region" aria-label="Audit events" tabindex="0"><table class="summary-table"><thead><tr><th>When</th><th>Actor</th><th>Action / target</th></tr></thead><tbody>${rows.map(e=>`<tr><th scope="row">${fmt(e.created)}</th><td>${esc(e.actor)}</td><td>${esc(e.action)}<br><span class="tiny muted">${esc(e.target)}</span></td></tr>`).join('')}</tbody></table></div>${!rows.length?'<p class="small muted">No events match these filters.</p>':''}`;};$('#audit-search').addEventListener('input',draw);$('#audit-action').addEventListener('change',draw);draw();
  }
}

function openDialog(title,body,onSubmit,submitLabel='Confirm',danger=false) {
  const dialog=$('#dialog');
  dialog.innerHTML=cleanMarkup(`<h2 id="dialog-title">${title}</h2><div class="error-slot"></div><form id="dialog-form">${body}<div class="form-actions"><button class="button secondary" type="button" data-action="cancel-dialog">Cancel</button><button class="button ${danger?'danger':''}" type="submit">${submitLabel}</button></div></form>`);
  dialog.showModal();
  $('#dialog-form').addEventListener('submit',async event=>{event.preventDefault();await pending(event.currentTarget,async()=>{try{await onSubmit(Object.fromEntries(new FormData(event.currentTarget)));}catch(error){errorBox(error,dialog);}});});
}
function roleOptions(role){return ['counsellor','researcher','administrator'].map(r=>`<option value="${r}" ${r===role?'selected':''}>${roleName(r)}</option>`).join('');}

document.addEventListener('click',async event=>{
  const el=event.target.closest('button,a');if(!el)return;
  if(el.classList.contains('skip-link')){event.preventDefault();$('#main')?.focus();$('#main')?.scrollIntoView();return;}
  if(el.dataset.errorFocus){event.preventDefault();const key=el.dataset.errorFocus;const target=$('#field-'+key);(target?.matches('input')?target:$('input',target||document))?.focus();return;}
  if(el.dataset.demoAccount){const role=el.dataset.demoAccount;$('#email').value=role+'@between.demo';$('#password').value='BetweenDemo!26';$$('[data-demo-account]').forEach(b=>b.classList.toggle('selected',b===el));announce('Demo credentials filled in. Choose Sign in to continue.');return;}
  if(el.dataset.editStep!==undefined){readAnswers();state.step=Number(el.dataset.editStep);assessmentPage();$('#main').focus();window.scrollTo(0,0);return;}
  if(el.dataset.page){state.queue.page=Number(el.dataset.page);queueResults();return;}
  if(el.dataset.countFilter){event.preventDefault();state.queue.status=el.dataset.countFilter;state.queue.page=1;$('#queue-status').value=state.queue.status;queueResults();return;}
  if(el.dataset.privacy){const kind=el.dataset.privacy;openDialog(kind==='withdraw'?'Stop participating?':'Request removal of your information?',`<p>${kind==='withdraw'?'This closes assessment access and deletes an unsubmitted draft. Submitted records remain.':'This requests an operator review of removal. Information is not erased immediately; live retention terms are not configured.'}</p>`,async()=>{await api('/privacy/requests','POST',{kind,confirmed:true});if(kind==='withdraw'){state.answers={};state.step=0;}$('#dialog').close();await privacy();},kind==='withdraw'?'Stop participating':'Record removal request',true);return;}
  if(el.dataset.accountEdit){const a=adminData.accounts.find(x=>x.id===el.dataset.accountEdit);openDialog('Change access for '+esc(a.name),`<p>${esc(a.email)}</p><div class="field"><label for="account-role">Role</label><select id="account-role" name="role">${roleOptions(a.role)}</select></div><label class="check-line"><input type="checkbox" name="active" ${a.active?'checked':''}>Account is active</label><p class="small">Confirm the affected account before saving. Open cases must be reassigned before deactivating a clinician.</p>`,async data=>{await api('/admin/account','POST',{id:a.id,role:data.role,active:data.active==='on',confirmed:true});$('#dialog').close();await administration();},'Confirm access change');return;}
  if(el.dataset.assignment){const pid=el.dataset.assignment;openDialog('Assign record '+esc(pid),`<div class="field"><label for="assignment-owner">Clinician</label><select id="assignment-owner" name="owner">${adminData.accounts.filter(a=>a.role==='counsellor'&&a.active).map(a=>`<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select></div><p>The previous reviewer will lose access when the assignment changes.</p>`,async data=>{await api('/admin/assignment','POST',{participant_id:pid,owner:data.owner});$('#dialog').close();await administration('assignments');},'Confirm assignment');return;}
  if(el.dataset.config){const c=adminData.config.find(x=>x.key===el.dataset.config);openDialog('Edit demo configuration',`<p>Save a new version of this configuration note. This does not approve a protocol or enable live collection.</p><div class="field"><label for="config-value">${esc(c.key.replace('_',' '))} · current version ${c.version}</label><textarea id="config-value" name="value" maxlength="4000" required>${esc(c.value)}</textarea></div>`,async data=>{await api('/admin/config','POST',{key:c.key,version:c.version,value:data.value});$('#dialog').close();await administration('configuration');},'Save new version');return;}
  const action=el.dataset.action;
  if(!action)return;
  if(action==='cancel-dialog'){$('#dialog').close();return;}
  if(action==='retry'){if(state.retry)await state.retry();else $('#assessment-form')?.requestSubmit();return;}
  if(action==='password'){const input=$('#password');const shown=input.type==='password';input.type=shown?'text':'password';el.textContent=shown?'Hide':'Show';el.setAttribute('aria-pressed',String(shown));return;}
  if(action==='staff-menu'){const nav=$('#staff-navigation');const open=nav.classList.toggle('open');el.setAttribute('aria-expanded',String(open));return;}
  if(action==='clear-filters'){state.queue={search:'',status:'',estimate:'',missing:false,date:'',sort:'newest',page:1};await queue();return;}
  if(action==='refresh-queue'){await queue();announce('Assigned queue refreshed.');return;}
  if(action==='reload-case'){await route();return;}
  if(action==='print'){window.print();return;}
  if(action==='assessment-back'){readAnswers();state.step=Math.max(0,state.step-1);assessmentPage();$('#main').focus();window.scrollTo(0,0);return;}
  if(action==='save-exit'){
    readAnswers();const run=async()=>{el.disabled=true;try{await saveDraft();location.hash='#home';}catch(error){errorBox(error);}finally{el.disabled=false;}};state.retry=run;await run();return;
  }
  if(action==='continue-session'){try{const data=await api('/session/extend','POST',{});state.expires=data.expires;$('#session-warning').hidden=true;announce('Session extended for 30 minutes.');}catch(error){announce(error.message);}return;}
  if(action==='logout'){
    const leave=async()=>{try{await api('/logout','POST',{});state.user=null;state.answers={};state.assessment=null;state.step=0;state.case=null;state.cases=[];state.retry=null;adminData=null;$('#dialog').close();$('#session-warning').hidden=true;const data=await api('/session');state.csrf=data.csrf;location.hash='#home';await route();}catch(error){errorBox(error);}};
    openDialog('Sign out of this session?',`<p>Unsaved answers will be cleared. Saved work is recoverable with the same account; access-code sessions cannot be recovered after sign-out.</p>`,leave,'Sign out');return;
  }
  if(action==='invite'){
    openDialog('Create a demo staff account',`<p>No email will be sent. A temporary demo password will be shown once after creation.</p><div class="field"><label for="invite-name">Name</label><input id="invite-name" name="name" required maxlength="100"></div><div class="field"><label for="invite-email">Demo email</label><input id="invite-email" name="email" type="email" required maxlength="254"></div><div class="field"><label for="invite-role">Role</label><select id="invite-role" name="role">${roleOptions('counsellor')}</select></div>`,async data=>{const result=await api('/admin/invite','POST',{...data,confirmed:true});$('#dialog').close();await administration();openDialog('Demo account created',`<p>${esc(result.message)}</p><p class="small" style="margin-top:16px">Temporary password:</p><p class="break-word"><strong>${esc(result.temporary_password)}</strong></p>`,async()=>$('#dialog').close(),'Done');},'Confirm account creation');
  }
});

async function route() {
  const serial=++routeSerial;state.retry=null;
  const parts=(location.hash.slice(1)||'home').split('/');
  try {
    if(parts[0]==='home')await home();
    else if(parts[0]==='about')about();
    else if(parts[0]==='access')access(parts[1]==='staff');
    else if(parts[0]==='assessment')await assessment();
    else if(parts[0]==='support')await support(parts[1]==='request');
    else if(parts[0]==='privacy')await privacy();
    else if(parts[0]==='staff'){
      const section=parts[1]||'queue';
      if(['queue','participants','reports'].includes(section))await queue(section);
      else if(section==='case')await caseDetail(parts[2],parts[3]||'overview');
      else if(section==='report')await report(parts[2]);
      else if(['research','dataset','model'].includes(section))await research(section);
      else if(['admin','assignments','configuration','audit'].includes(section))await administration(section);
      else restricted('Page not found','Choose a destination in your workspace navigation.');
    }else restricted('Page not found','Return home to continue.');
    if(serial===routeSerial){$('#main')?.focus({preventScroll:true});window.scrollTo(0,0);}
  }catch(error){shell(false);main(`<div class="assessment-wrap">${heading(error.status===403?'ACCESS RESTRICTED':'UNABLE TO LOAD',error.status===403?'This record is restricted.':'We couldn’t load this page.',esc(error.message))}<button class="button" data-action="retry">Try again ${icon('refresh')}</button><p style="margin-top:24px"><a href="#home">Return home</a></p></div>`);state.retry=route;}
}
window.addEventListener('hashchange',route);
window.addEventListener('beforeunload',event=>{if($('#save-status')?.textContent.startsWith('Unsaved changes')){event.preventDefault();event.returnValue='';}});
setInterval(()=>{
  if(!state.user||!state.expires)return;
  const remaining=state.expires-Date.now()/1000;
  if(remaining<120){$('#session-warning').hidden=false;$('#session-warning').innerHTML=remaining>0?'Your session expires soon. Save your work or extend the session. <button data-action="continue-session">Continue session</button>':'Your session has expired. Server-saved work can be recovered after signing in. <a href="#access">Sign in again</a>';}
},15000);
(async()=>{try{const data=await api('/session');Object.assign(state,data);await route();}catch(error){main(`<div class="assessment-wrap"><h1>Unable to connect.</h1><p>${esc(error.message)}</p><p>Start the Flask server and reload this page.</p></div>`);}})();
