'use strict';
/*
 * Between — Opus homepage.
 * Centrepiece: "The Between Slider". A native range input moves an illustrated
 * scene between an online moment (phone, feed, chat bubbles) and an offline one
 * (sun, friends, music). It is a visual metaphor only: browser memory, no
 * network, no storage, nothing recorded, no claimed effect. Both ends are
 * presented as normal parts of life.
 */
(function () {
  var STOPS = [
    { at: 0,   key: 'online',  label: 'Online',  line: 'Group chats. Feeds. One more video.' },
    { at: 50,  key: 'between', label: 'Between', line: 'Most days are a bit of both.' },
    { at: 100, key: 'offline', label: 'Offline', line: 'Friends. Music. Fresh air. Sleep.' }
  ];

  function stopFor(value) {
    return value < 34 ? STOPS[0] : value > 66 ? STOPS[2] : STOPS[1];
  }

  function scene() {
    /* Decorative SVG. All meaning is carried by the slider's label and live caption. */
    var feed = '';
    var palette = ['#FFC93C', '#FF8AC9', '#3DDBB0', '#7CC8FF', '#FF6B5B', '#B9A8FF'];
    for (var i = 0; i < 12; i++) {
      var y = i * 70;
      var c = palette[i % palette.length];
      feed += '<g transform="translate(0 ' + y + ')">' +
        '<circle cx="14" cy="14" r="9" fill="' + c + '"/>' +
        '<rect x="30" y="8" width="' + (52 + (i * 13) % 40) + '" height="6" rx="3" fill="#ffffff" opacity=".85"/>' +
        '<rect x="30" y="18" width="' + (30 + (i * 7) % 30) + '" height="4" rx="2" fill="#ffffff" opacity=".45"/>' +
        '<rect x="4" y="30" width="128" height="32" rx="8" fill="' + palette[(i + 2) % palette.length] + '" opacity=".9"/>' +
      '</g>';
    }
    return '' +
    '<svg class="opus-scene-svg" viewBox="0 0 520 520" aria-hidden="true" focusable="false">' +
      '<defs>' +
        '<clipPath id="opus-screen-clip"><rect x="-70" y="-128" width="140" height="256" rx="16"/></clipPath>' +
        '<clipPath id="opus-stage-clip"><rect x="0" y="0" width="520" height="520" rx="40"/></clipPath>' +
      '</defs>' +
      '<g clip-path="url(#opus-stage-clip)">' +
        '<rect id="opus-sky" width="520" height="520" fill="#5B3DF5"/>' +
        /* online pattern: dotted grid */
        '<g id="opus-grid" fill="#ffffff">' + gridDots() + '</g>' +
        /* offline: sun + hills */
        /* Halo is drawn first and in a pale yellow so it reads as glow, not a grey ring over the sky. */
        '<g id="opus-sun"><circle cx="390" cy="150" r="90" fill="#FFF1B8" opacity=".55"/><circle cx="390" cy="150" r="62" fill="#FFC93C"/></g>' +
        /* offline: two soft clouds fill the empty upper-left sky */
        '<g id="opus-clouds" fill="#ffffff" opacity="0">' +
          '<g transform="translate(70 120)"><rect x="0" y="14" width="120" height="30" rx="15"/><circle cx="42" cy="18" r="20"/><circle cx="74" cy="14" r="24"/></g>' +
          '<g transform="translate(180 220) scale(.7)" opacity=".85"><rect x="0" y="14" width="120" height="30" rx="15"/><circle cx="42" cy="18" r="20"/><circle cx="74" cy="14" r="24"/></g>' +
        '</g>' +
        '<path id="opus-hill-back" d="M-20 430 C 90 360, 210 380, 300 420 S 470 380, 560 410 L 560 560 L -20 560 Z" fill="#3DDBB0"/>' +
        '<path id="opus-hill-front" d="M-20 470 C 120 430, 260 460, 360 450 S 500 440, 560 460 L 560 560 L -20 560 Z" fill="#1FB98F"/>' +
        /* friends: three abstract figures */
        '<g id="opus-friends">' +
          figure(118, 430, '#FF6B5B', '#FFD9C7') +
          figure(196, 438, '#7CC8FF', '#8A5A3C') +
          figure(426, 436, '#FF8AC9', '#C98B5E') +
          '<circle id="opus-ball" cx="384" cy="490" r="14" fill="#ffffff" stroke="#16123A" stroke-width="3"/>' +
          '<g id="opus-note" fill="#16123A"><path d="M332 300 v-46 l26 -8 v44" stroke="#16123A" stroke-width="5" fill="none" stroke-linecap="round"/><circle cx="326" cy="302" r="9"/><circle cx="352" cy="292" r="9"/></g>' +
        '</g>' +
        /* chat bubbles around the phone */
        '<g id="opus-bubbles">' +
          bubble(70, 120, 92, '#FFFFFF', '#16123A', 'lol!!', -6) +
          bubble(360, 96, 104, '#FFC93C', '#16123A', '3 new', 5) +
          bubble(352, 300, 96, '#FF8AC9', '#16123A', '♥ 24', -4) +
          bubble(54, 330, 104, '#3DDBB0', '#16123A', 'u up?', 4) +
        '</g>' +
        /* the phone */
        '<g id="opus-phone" transform="translate(260 250)">' +
          '<rect x="-84" y="-150" width="168" height="300" rx="30" fill="#16123A"/>' +
          '<g clip-path="url(#opus-screen-clip)">' +
            '<rect x="-70" y="-128" width="140" height="256" fill="#2A1F7A"/>' +
            '<g transform="translate(-68 -124)"><g class="opus-feed">' + feed + '</g></g>' +
            '<rect id="opus-screen-dim" x="-70" y="-128" width="140" height="256" fill="#16123A" opacity="0"/>' +
          '</g>' +
          '<rect x="-24" y="-142" width="48" height="8" rx="4" fill="#2E2670"/>' +
        '</g>' +
      '</g>' +
    '</svg>';
  }

  function gridDots() {
    var out = '';
    for (var x = 30; x < 520; x += 40) for (var y = 30; y < 520; y += 40) out += '<circle cx="' + x + '" cy="' + y + '" r="2" opacity=".22"/>';
    return out;
  }
  function figure(x, y, body, head) {
    return '<g class="opus-figure" transform="translate(' + x + ' ' + y + ')">' +
      '<rect x="-26" y="-70" width="52" height="86" rx="26" fill="' + body + '"/>' +
      '<circle cx="0" cy="-92" r="22" fill="' + head + '"/>' +
      '<path d="M-9 -88 q9 8 18 0" stroke="#16123A" stroke-width="3" fill="none" stroke-linecap="round"/>' +
    '</g>';
  }
  function bubble(x, y, w, fill, ink, text, rot) {
    /* Outer group receives the CSS transform; inner keeps the SVG position. */
    return '<g class="opus-bubble"><g transform="translate(' + x + ' ' + y + ') rotate(' + rot + ')">' +
      '<rect x="0" y="0" width="' + w + '" height="44" rx="22" fill="' + fill + '" stroke="#16123A" stroke-width="3"/>' +
      '<path d="M18 42 l-6 14 l18 -12" fill="' + fill + '" stroke="#16123A" stroke-width="3" stroke-linejoin="round"/>' +
      '<rect x="14" y="38" width="20" height="5" fill="' + fill + '"/>' +
      '<text x="' + (w / 2) + '" y="29" text-anchor="middle" font-family="Source Sans 3, Arial, sans-serif" font-weight="700" font-size="19" fill="' + ink + '">' + text + '</text>' +
    '</g></g>';
  }

  function statusChip(ctx) {
    var e = ctx.esc;
    if (ctx.submission) {
      return '<p class="opus-status opus-status-done">' + ctx.icon('check') +
        '<span><strong>Submitted</strong> ' + e(ctx.fmt(ctx.submission.submitted_at)) + '</span></p>';
    }
    if (ctx.draft) {
      var where = Number(ctx.draft.step) === 4 ? 'Ready to review' : 'Section ' + e(ctx.draft.step) + ' of 3';
      return '<p class="opus-status">' + ctx.icon('clock') +
        '<span><strong>Saved</strong> ' + e(ctx.fmt(ctx.draft.updated)) + ' · ' + where + '</span></p>';
    }
    return '';
  }

  window.renderOpusHome = function (ctx) {
    var icon = ctx.icon;
    var e = ctx.esc;
    return '' +
    '<div class="opus-home">' +

      /* ---------- HERO ---------- */
      '<section class="home-main opus-hero" aria-labelledby="home-heading">' +
        '<div class="opus-hero-copy">' +
          '<p class="opus-kicker">Youth mental health · Ages 13–24</p>' +
          /* Three deliberate lines; spaces between spans keep the sentence intact for screen readers and copy/paste. */
          '<h1 id="home-heading"><span class="opus-line">Understand.</span> <span class="opus-line"><span class="opus-mark">Connect.</span></span> <span class="opus-line">Follow up.</span></h1>' +
          '<p class="opus-lede">A shared workspace to review youth assessments, understand context and plan follow-up.</p>' +
          '<div class="opus-actions">' +
            '<a href="#access/staff" class="button opus-cta">Open clinician workspace' + icon('arrow') + '</a>' +
            '<a href="#assessment" class="button secondary opus-ghost">' + e(ctx.ctaLabel) + '</a>' +
          '</div>' +
          statusChip(ctx) +
          '<ul class="opus-facts" aria-label="At a glance">' +
            '<li>' + icon('file') + 'Assessment review</li>' +
            '<li>' + icon('heart') + 'Shared conversations</li>' +
            '<li>' + icon('clock') + 'Follow-up</li>' +
          '</ul>' +
        '</div>' +

        '<div class="opus-stage" data-opus-stage data-opus-mode="online">' +
          '<div class="opus-scene">' + scene() + '</div>' +
          '<div class="opus-control">' +
            '<label class="opus-control-label" for="opus-slider">Slide between online and offline</label>' +
            '<input id="opus-slider" class="opus-slider" type="range" min="0" max="100" step="1" value="0" aria-describedby="opus-caption" data-opus-slider>' +
            '<div class="opus-stops" role="group" aria-label="Jump to">' +
              STOPS.map(function (s) {
                return '<button type="button" class="opus-stop" data-opus-stop="' + s.at + '" aria-pressed="' + (s.at === 0) + '">' + s.label + '</button>';
              }).join('') +
            '</div>' +
            '<p id="opus-caption" class="opus-caption" aria-live="polite">' + STOPS[0].line + '</p>' +
            '<p class="opus-toy-note">Illustration only. Nothing is saved or sent.</p>' +
          '</div>' +
        '</div>' +
      '</section>' +

      /* ---------- HOW IT WORKS ---------- */
      '<section class="opus-how" id="opus-how" aria-labelledby="opus-how-heading">' +
        '<div class="opus-section-head">' +
          '<h2 id="opus-how-heading" tabindex="-1">How it works</h2>' +
          '<a href="#opus-never" class="opus-jump" data-opus-jump="opus-never">What we never do <span aria-hidden="true">↓</span></a>' +
        '</div>' +
        '<ol class="opus-steps">' +
          '<li class="opus-step opus-step-1"><span class="opus-step-num" aria-hidden="true">1</span><h3>Young person shares</h3><p>Routines, time online, how things feel.</p></li>' +
          '<li class="opus-step opus-step-2"><span class="opus-step-num" aria-hidden="true">2</span><h3>Clinician reviews</h3><p>Self-reported answers, in context.</p></li>' +
          '<li class="opus-step opus-step-3"><span class="opus-step-num" aria-hidden="true">3</span><h3>Talk &amp; follow up</h3><p>Agree next steps together.</p></li>' +
        '</ol>' +
        '<p class="opus-footnote">Research prototype. Model estimates require clinical validation. PHQ-9, GAD-7 and WEMWBS are not administered.</p>' +
      '</section>' +

      /* ---------- NEVER ---------- */
      '<section class="opus-never" id="opus-never" aria-labelledby="opus-never-heading">' +
        '<h2 id="opus-never-heading" tabindex="-1">We never</h2>' +
        '<ul class="opus-never-list">' +
          '<li><span class="opus-x" aria-hidden="true">' + icon('lock') + '</span>log into your accounts</li>' +
          '<li><span class="opus-x" aria-hidden="true">' + icon('file') + '</span>read your messages</li>' +
          '<li><span class="opus-x" aria-hidden="true">' + icon('chart') + '</span>track your phone</li>' +
        '</ul>' +
        '<a href="#privacy" class="opus-never-link">Privacy choices ' + icon('arrow') + '</a>' +
      '</section>' +

      /* ---------- SUPPORT + ABOUT ---------- */
      '<section class="opus-duo" aria-label="Support and about Between">' +
        '<div class="opus-card opus-card-support">' +
          '<h2>Want to talk to someone?</h2>' +
          '<p>Open to everyone. No assessment needed.</p>' +
          '<a href="#support" class="button opus-on-color">Get support ' + icon('arrow') + '</a>' +
          '<p class="opus-small">Requests are not monitored. In an emergency, contact local emergency services.</p>' +
        '</div>' +
        '<div class="opus-card opus-card-study">' +
          '<h2>What is Between?</h2>' +
          '<p>How clinicians and young people use it together.</p>' +
          '<a href="#about" class="opus-text-link">About Between ' + icon('arrow') + '</a>' +
        '</div>' +
      '</section>' +
    '</div>';
  };

  /* ---------- interaction ---------- */

  var NIGHT = [91, 61, 245];   /* #5B3DF5 online violet */
  var DAY = [124, 200, 255];   /* #7CC8FF offline sky   */

  function mix(a, b, t) { return a + (b - a) * t; }
  function clamp(t) { return Math.max(0, Math.min(1, t)); }
  /* ramp(t, start, end): 0 before start, 1 after end */
  function ramp(t, s, e) { return clamp((t - s) / (e - s)); }

  function paint(root, value) {
    var t = value / 100;
    var $ = function (id) { return root.querySelector('#' + id); };

    var sky = $('opus-sky');
    if (sky) sky.setAttribute('fill', 'rgb(' + NIGHT.map(function (c, i) { return Math.round(mix(c, DAY[i], t)); }).join(',') + ')');
    var grid = $('opus-grid');
    if (grid) grid.setAttribute('opacity', String(1 - ramp(t, 0.1, 0.6)));

    var sunT = ramp(t, 0.25, 1);
    var sun = $('opus-sun');
    if (sun) { sun.setAttribute('transform', 'translate(0 ' + mix(300, 0, sunT) + ')'); sun.setAttribute('opacity', String(sunT)); }
    var cloudT = ramp(t, 0.55, 1);
    var clouds = $('opus-clouds');
    if (clouds) { clouds.setAttribute('opacity', String(cloudT * 0.9)); clouds.setAttribute('transform', 'translate(' + mix(-40, 0, cloudT) + ' 0)'); }

    var hillT = ramp(t, 0.15, 0.8);
    var hb = $('opus-hill-back'), hf = $('opus-hill-front');
    if (hb) hb.setAttribute('transform', 'translate(0 ' + mix(160, 0, hillT) + ')');
    if (hf) hf.setAttribute('transform', 'translate(0 ' + mix(120, 0, hillT) + ')');

    var friendsT = ramp(t, 0.45, 1);
    var friends = $('opus-friends');
    if (friends) { friends.setAttribute('transform', 'translate(0 ' + mix(200, 0, friendsT) + ')'); friends.setAttribute('opacity', String(friendsT)); }

    var bubT = 1 - ramp(t, 0, 0.55);
    root.querySelectorAll('.opus-bubble').forEach(function (b, i) {
      b.style.opacity = String(bubT);
      b.style.transform = 'translate(' + ((i % 2 ? 1 : -1) * (1 - bubT) * 30) + 'px,' + ((1 - bubT) * -20) + 'px)';
    });

    /* Phone: shrinks, tilts and slides down to rest on the grass. */
    var pT = ramp(t, 0.1, 0.95);
    var phone = $('opus-phone');
    if (phone) {
      var x = mix(260, 300, pT), y = mix(250, 474, pT), s = mix(1, 0.34, pT), r = mix(0, 78, pT);
      phone.setAttribute('transform', 'translate(' + x + ' ' + y + ') rotate(' + r + ') scale(' + s + ')');
    }
    var dim = $('opus-screen-dim');
    if (dim) dim.setAttribute('opacity', String(ramp(t, 0.3, 0.9) * 0.85));

    var stop = stopFor(value);
    root.setAttribute('data-opus-mode', stop.key);
    var slider = root.querySelector('[data-opus-slider]');
    if (slider) {
      slider.setAttribute('aria-valuetext', stop.label + ', ' + value + ' percent offline');
      slider.style.setProperty('--opus-fill', value + '%');
    }
    var caption = root.querySelector('#opus-caption');
    if (caption && caption.textContent !== stop.line) caption.textContent = stop.line;
    root.querySelectorAll('[data-opus-stop]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(stopFor(Number(btn.getAttribute('data-opus-stop'))).key === stop.key));
    });
  }

  function reducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function glide(root, slider, target) {
    var from = Number(slider.value);
    if (reducedMotion() || from === target) { slider.value = target; paint(root, target); return; }
    var start = null, dur = 520;
    if (root._opusFrame) cancelAnimationFrame(root._opusFrame);
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      var v = Math.round(mix(from, target, eased));
      slider.value = v; paint(root, v);
      if (p < 1) root._opusFrame = requestAnimationFrame(step);
    }
    root._opusFrame = requestAnimationFrame(step);
  }

  window.initOpusHome = function () {
    var root = document.querySelector('[data-opus-stage]');
    if (root) {
      var slider = root.querySelector('[data-opus-slider]');
      paint(root, Number(slider.value));
      slider.addEventListener('input', function () {
        if (root._opusFrame) cancelAnimationFrame(root._opusFrame);
        paint(root, Number(slider.value));
      });
      root.querySelectorAll('[data-opus-stop]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          glide(root, slider, Number(btn.getAttribute('data-opus-stop')));
        });
      });
    }

    /* In-page jumps: stop hash routing, scroll and move focus instead. */
    document.querySelectorAll('[data-opus-jump]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopPropagation();
        var section = document.getElementById(link.getAttribute('data-opus-jump'));
        if (!section) return;
        section.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
        var target = section.querySelector('h2[tabindex]') || section;
        target.focus({ preventScroll: true });
      });
    });
  };
})();
