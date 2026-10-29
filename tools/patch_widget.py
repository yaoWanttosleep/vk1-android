#!/usr/bin/env python3
"""Turn the upstream web widget into the Android overlay build (exact-anchor patches)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "vendor/widget.js")
OUT = os.path.join(ROOT, "app/src/assets/vk1/widget.js")

BRIDGE = r'''
  // ---- Android overlay host (added by the APK build, everything else is upstream) ----
  var ANDROID = (typeof VK1 !== 'undefined' && VK1) ? VK1 : null
  var vk1Expanded = false
  var vk1CollapseTimer = null
  var vk1Frozen = false
  var vk1FreezeTimer = null
  function vk1Freeze() {
    vk1Frozen = true
    if (vk1FreezeTimer) clearTimeout(vk1FreezeTimer)
    vk1FreezeTimer = setTimeout(function () { vk1Frozen = false; vk1FreezeTimer = null }, 600)
  }
  function vk1Shift(pair) {
    if (!pair) return
    var parts = String(pair).split(',')
    var dx = parseFloat(parts[0]), dy = parseFloat(parts[1])
    if (!isFinite(dx) || !isFinite(dy) || (!dx && !dy)) return
    state.left += dx
    state.top += dy
    express()
    layout()
  }
  window.__vk1ApplyShift = function (pair) { vk1Shift(pair) }
  window.__vk1Settle = function () {
    vk1Frozen = false
    if (vk1FreezeTimer) { clearTimeout(vk1FreezeTimer); vk1FreezeTimer = null }
    settle()
  }
  var VK1_INSET = ANDROID ? 26 : 0
  var vk1Region = { x0: -1, y0: -1, x1: -1, y1: -1, t: 0 }
  function vk1ReportRegion(now) {
    if (!ANDROID) return
    var x0 = state.left, y0 = state.top
    var x1 = state.left + state.size, y1 = state.top + state.size
    for (var i = 0; i < state.bowls.length; i++) {
      var b = state.bowls[i]
      if (!b.el || b.fed) continue
      if (b.X - b.artW / 2 < x0) x0 = b.X - b.artW / 2
      if (b.Y - b.artH / 2 < y0) y0 = b.Y - b.artH / 2
      if (b.X + b.artW / 2 > x1) x1 = b.X + b.artW / 2
      if (b.Y + b.artH / 2 > y1) y1 = b.Y + b.artH / 2
    }
    x0 -= 8; y0 -= 8; x1 += 8; y1 += 8
    x0 = Math.max(0, x0); y0 = Math.max(0, y0)
    x1 = Math.min(innerWidth, x1); y1 = Math.min(innerHeight, y1)
    var r = vk1Region
    if (Math.abs(x0 - r.x0) + Math.abs(y0 - r.y0) + Math.abs(x1 - r.x1) + Math.abs(y1 - r.y1) < 3 &&
        now - r.t < 500) return
    r.x0 = x0; r.y0 = y0; r.x1 = x1; r.y1 = y1; r.t = now
    ANDROID.touchRegion(x0, y0, x1, y1)
  }
  var PAT_NEED = ANDROID ? 0.28 : 0.5
  var PAT_IDLE = ANDROID ? 0.32 : 0.15
  function vk1Expand(on) {
    if (!ANDROID) return
    if (on) {
      if (vk1CollapseTimer) { clearTimeout(vk1CollapseTimer); vk1CollapseTimer = null }
      if (vk1Expanded) return
      vk1Expanded = true
      vk1Freeze()
      vk1Shift(ANDROID.setExpanded(true))
      return
    }
    if (!vk1Expanded || vk1CollapseTimer) return
    vk1CollapseTimer = setTimeout(function () {
      vk1CollapseTimer = null
      if (!vk1Expanded) return
      vk1Expanded = false
      vk1Freeze()
      vk1Shift(ANDROID.setExpanded(false))
    }, 80)
  }
'''

PATCHES = [
    ("android-asset-base",
     "  var BASE = '/dsh-vk1'",
     "  var BASE = 'file:///android_asset/vk1'"),
    ("android-default-size",
     "  var DEFAULT_SIZE = 454",
     "  var DEFAULT_SIZE = 150"),
    ("android-bridge",
     "  var BALANCE_URL = BASE + '/balance.json'",
     "  var BALANCE_URL = BASE + '/balance.json'\n" + BRIDGE),
    ("android-poll",
     """  var busy = false
  function poll(snap) {
    if (busy) return
    busy = true
    fetch(BALANCE_URL, { cache: 'no-store' })
      .then(function (r) { return r.json() })
      .then(function (d) {""",
     """  var busy = false
  function poll(snap) {
    if (busy) return
    busy = true
    var source
    if (ANDROID) {
      // The native poller owns the API key; JSON comes back synchronously from the cache.
      source = Promise.resolve().then(function () {
        try { return JSON.parse(ANDROID.balanceJson()) } catch (err) { return null }
      })
    } else {
      source = fetch(BALANCE_URL, { cache: 'no-store' }).then(function (r) { return r.json() })
    }
    source
      .then(function (d) {"""),
    ("android-vibrate",
     """    playPool(hitPool)
  }""",
     """    playPool(hitPool)
    if (ANDROID) ANDROID.buzz()
  }"""),
    ("android-rice-inside-window",
     """      X: vs.right - R * 1.2 - state.bowls.length * R * 0.5,
      Y: vs.top - R * 1.2,""",
     """      X: vs.left + R * 1.35 + state.bowls.length * R * 0.5,
      Y: vs.top - R * 1.2,"""),
    ("android-native-drag",
     """    try { e.preventDefault(); e.stopPropagation() } catch (err) {}
    state.dragWidget = { x: e.clientX, y: e.clientY, left: state.left, top: state.top, moved: false }
    root.classList.add('dshvk1-dragging')
    addDragListeners()""",
     """    try { e.preventDefault(); e.stopPropagation() } catch (err) {}
    if (ANDROID) return   // two fingers move her; one finger strokes and taps
    state.dragWidget = { x: e.clientX, y: e.clientY, left: state.left, top: state.top, moved: false }
    root.classList.add('dshvk1-dragging')
    addDragListeners()"""),
    ("android-menu-hooks",
     """  document.addEventListener('pointerdown', onDocMenuClose, true)""",
     """  document.addEventListener('pointerdown', onDocMenuClose, true)
  window.__vk1OpenMenu = function () {
    var r = root.getBoundingClientRect()
    openMenu(r.left + r.width / 2, r.top + r.height / 2)
  }
  function vk1ReleaseStuck() {
    if (!state.grab) return
    var b = state.grab.bowl
    state.grab = null
    b.dragging = false
    b.VX = 0
    b.VY = 0
    b.grounded = false
    if (!b.iron && riceOnGirl(b)) onRiceFed(b)
    removeDragListeners()
  }
  window.__vk1LongPress = function (x, y) {
    // A long press that started on a prop belongs to that prop's drag, not to the menu.
    if (state.grab) return
    if (state.dragWidget && state.dragWidget.moved) return
    if (bowlAt(x, y)) return
    if (!isHit({ clientX: x, clientY: y })) return
    if (state.dragWidget) {
      state.dragWidget = null
      root.classList.remove('dshvk1-dragging')
      removeDragListeners()
    }
    openMenu(x, y)
  }
  window.__vk1MovePet = function (dx, dy) {
    var vp = viewport()
    state.left = clamp(state.left + dx, 0, Math.max(0, vp.w - state.size - rightGap()))
    state.top = clamp(state.top + dy, 0, Math.max(0, vp.h - state.size))
    express()
  }
  window.__vk1DropPet = function () {
    var vp = viewport()
    var w = state.size, h = state.size
    var centerX = state.left + w / 2
    var centerY = state.top + h / 2
    if (centerX < vp.w / 4) { state.h = 'left'; state.hOff = 0 }
    else if (centerX > vp.w * 3 / 4) { state.h = 'right'; state.hOff = 0 }
    else { state.h = null; state.hOff = state.left }
    if (centerY < vp.h / 4) { state.v = 'top'; state.vOff = 0 }
    else if (centerY > vp.h * 3 / 4) { state.v = 'bottom'; state.vOff = 0 }
    else { state.v = null; state.vOff = state.top }
    settle()
    saveAnchor()
  }
  window.__vk1NoPat = function (on) {
    window.__vk1PatOff = !!on
    if (on) {
      pat.active = false
      pat.distance = 0
      pat.moveTime = 0
      pat.waiting = false
    }
  }
  window.__vk1CancelGesture = function () {
    vk1ReleaseStuck()
    state.dragWidget = null
    state.grab = null
    root.classList.remove('dshvk1-dragging')
    removeDragListeners()
    blockPat()
  }
  window.__vk1Probe = function (x, y) {
    var r = root.getBoundingClientRect()
    return JSON.stringify({
      hitReady: hitReady,
      hit: isHit({ clientX: x, clientY: y }),
      rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
      vp: [innerWidth, innerHeight],
      size: state.size,
    })
  }"""),
    ("android-tap-log",
     """  function onDown(e) {
    blockPat()""",
     """  function onDown(e) {
    if (state.grab && !state.dragWidget) vk1ReleaseStuck()
    if (ANDROID) ANDROID.log('down ' + Math.round(e.clientX) + ',' + Math.round(e.clientY) +
      ' hit=' + isHit(e) + ' ready=' + hitReady)
    blockPat()"""),
    ("android-freeze-settle",
     """  function settle() {
    var vp = viewport()""",
     """  function settle() {
    if (vk1Frozen) { express(); layout(); return }
    var vp = viewport()"""),
    ("android-touch-pat",
     """  function onCursor(e) {
    pat.pointer = { x: e.clientX, y: e.clientY, buttons: e.buttons || 0 }""",
     """  function onCursor(e) {
    // Touch has no hover state: a finger moving over her is the stroking gesture, so the
    // "mouse button held down" guard must not see the touch's implicit primary button.
    pat.pointer = { x: e.clientX, y: e.clientY,
      buttons: (ANDROID && e.pointerType === 'touch') ? 0 : (e.buttons || 0) }"""),
    ("android-menu-expand",
     """  function openMenu(clientX, clientY) {
    buildMenu()""",
     """  function openMenu(clientX, clientY) {
    buildMenu()
    vk1Expand(true)"""),
    ("android-menu-reposition",
     """    buildMenu()
    vk1Expand(true)
    state.menuOpen = true""",
     """    buildMenu()
    vk1Expand(true)
    if (ANDROID) {
      // The click coordinates belong to the pet-sized viewport; once the window is
      // full screen, place the menu beside her again in the new coordinate space.
      setTimeout(function () {
        var mw = menu.offsetWidth || 220
        var mh = menu.offsetHeight || 300
        var vp = viewport()
        var r = root.getBoundingClientRect()
        var x = r.left + r.width * 0.72
        var y = r.top + r.height * 0.55
        menu.style.left = clamp(x, 4, Math.max(4, vp.w - mw - 4)) + 'px'
        menu.style.top = clamp(y, 4, Math.max(4, vp.h - mh - 4)) + 'px'
      }, 120)
    }
    state.menuOpen = true"""),
    ("android-menu-collapse",
     """  function closeMenu() {
    state.menuOpen = false""",
     """  function closeMenu() {
    if (state.menuOpen) vk1Expand(false)
    state.menuOpen = false"""),
    ("android-settings-expand",
     """  function showSettings(page) {
    blockPat(); closeMenu()""",
     """  function showSettings(page) {
    blockPat(); closeMenu()
    vk1Expand(true)"""),
    ("android-settings-collapse",
     """  settings.addEventListener('cancel', stopPreview)""",
     """  settings.addEventListener('cancel', stopPreview)
  settings.addEventListener('close', function () { vk1Expand(false) })"""),
    ("android-size-key",
     """  var SIZE_KEY = 'dsh-vk1-size'""",
     """  var SIZE_KEY = 'vk1-android-size'"""),
    ("android-size-cap",
     """  updateScreen()
  setupHitTest()
  initSoundLibrary()

  rafId = requestAnimationFrame(frame)""",
     """  if (ANDROID) {
    // The overlay window is 1.6x her width, so a pet wider than a third of the screen
    // would push the floor (where rice lands) off-screen.
    var screenCss = (window.screen && screen.width) || 320
    MAX_SIZE = Math.min(MAX_SIZE, Math.max(MIN_SIZE, Math.floor(screenCss * 0.8)))
    if (state.size > MAX_SIZE) {
      state.size = MAX_SIZE
      try { localStorage.setItem(SIZE_KEY, String(state.size)) } catch (err) {}
    }
    ANDROID.resize(state.size)
  }
  updateScreen()
  setupHitTest()
  initSoundLibrary()

  rafId = requestAnimationFrame(frame)"""),
    ("android-resize-hook",
     """    state.size = clamp(Math.round(v) || DEFAULT_SIZE, MIN_SIZE, MAX_SIZE)
    try { localStorage.setItem(SIZE_KEY, String(state.size)) } catch (err) {}""",
     """    state.size = clamp(Math.round(v) || DEFAULT_SIZE, MIN_SIZE, MAX_SIZE)
    try { localStorage.setItem(SIZE_KEY, String(state.size)) } catch (err) {}
    if (ANDROID) ANDROID.resize(state.size)"""),
    ("android-boot-resize",
     """  // ----------------------------------------------------------------- start ---""",
     """  if (ANDROID) ANDROID.resize(state.size)

  // ----------------------------------------------------------------- start ---"""),
    ("android-pat-need",
     """      if (pat.distance >= 24) pat.moveTime += dt
      if (!pat.active && !pat.waiting && pat.moveTime >= 0.5) {""",
     """      if (pat.distance >= 24) pat.moveTime += dt
      if (!pat.active && !pat.waiting && pat.moveTime >= PAT_NEED) {"""),
    ("android-pat-idle",
     """      if (!pat.active && pat.idle >= 0.15) { pat.distance = 0; pat.moveTime = 0 }
      if (pat.idle >= 0.15) { pat.active = false; pat.distance = 0; pat.moveTime = 0 }""",
     """      if (!pat.active && pat.idle >= PAT_IDLE) { pat.distance = 0; pat.moveTime = 0 }
      if (pat.idle >= PAT_IDLE) { pat.active = false; pat.distance = 0; pat.moveTime = 0 }"""),
    ("android-pot-log-attach",
     """  function attachIronPot(p) {""",
     """  function attachIronPot(p) {
    if (ANDROID) ANDROID.log('pot attach x=' + Math.round(p.X) + ' y=' + Math.round(p.Y) +
      ' size=' + state.size + ' vp=' + innerWidth + 'x' + innerHeight)"""),
    ("android-pot-log-knock",
     """    if (!top) return false
    top.fadeT = 0.001""",
     """    if (!top) return false
    if (ANDROID) ANDROID.log('pot knockOff by=' + (pat.active ? 'pat' : 'other'))
    top.fadeT = 0.001"""),
    ("android-pot-knock-threshold",
     """        if (state.bowls.some(function (b) { return b.onHead })) { knockPotOff(); pat.waiting = true }""",
     """        if (state.bowls.some(function (b) { return b.onHead })) {
          if (pat.moveTime >= (ANDROID ? 0.7 : 0.5)) { knockPotOff(); pat.waiting = true }
        }"""),
    ("android-pat-log",
     """    var can = onHer && !p.buttons && !state.menuOpen && !settings.open && !state.dragWidget && !state.grab && state.fxPat""",
     """    var can = onHer && !p.buttons && !state.menuOpen && !settings.open && !state.dragWidget &&
      !state.grab && state.fxPat && !window.__vk1PatOff
    if (ANDROID && p) {
      pat.logT = (pat.logT || 0) + dt
      if (pat.logT > 0.4) {
        pat.logT = 0
        ANDROID.log('pat on=' + (onHer ? 1 : 0) + ' btn=' + (p.buttons || 0) +
          ' d=' + Math.round(pat.distance) + ' m=' + (Math.round(pat.moveTime * 100) / 100) +
          ' blk=' + (Math.round(pat.blocked * 100) / 100) + ' act=' + (pat.active ? 1 : 0) +
          ' fx=' + (state.fxPat ? 1 : 0))
      }
    }"""),
    ("android-up-log",
     """  function onUp(e) {""",
     """  function onUp(e) {
    if (ANDROID) ANDROID.log('up act=' + (pat.active ? 1 : 0) + ' d=' + Math.round(pat.distance) +
      ' m=' + (Math.round(pat.moveTime * 100) / 100) + ' on=' +
      (pat.pointer ? (charHitAt(pat.pointer.x, pat.pointer.y) ? 1 : 0) : -1))"""),

    ("android-viewport-inset",
     """      right: window.innerWidth || document.documentElement.clientWidth || 1280,
      bottom: window.innerHeight || document.documentElement.clientHeight || 800,""",
     """      right: window.innerWidth || document.documentElement.clientWidth || 1280,
      bottom: (window.innerHeight || document.documentElement.clientHeight || 800) - VK1_INSET,"""),
    ("android-viewport-h",
     """      w: window.innerWidth || document.documentElement.clientWidth || 1280,
      h: window.innerHeight || document.documentElement.clientHeight || 800,""",
     """      w: window.innerWidth || document.documentElement.clientWidth || 1280,
      h: (window.innerHeight || document.documentElement.clientHeight || 800) - VK1_INSET,"""),
    ("android-region-global",
     """  function vk1ReportRegion(now) {""",
     """  window.__vk1ReportRegion = function (now) { vk1ReportRegion(now) }
  function vk1ReportRegion(now) {"""),
    ("android-region-report",
     """    updatePat(dt)""",
     """    if (ANDROID) vk1ReportRegion(now)
    updatePat(dt)"""),

    ("android-express-transform",
     """  function express() {
    root.style.left = state.left + 'px'
    root.style.top = state.top + 'px'
  }""",
     """  function express() {
    if (ANDROID) {
      // left/top force a layout + full repaint of the overlay every frame, which is what
      // made dragging feel sticky; a composited transform does not.
      root.style.left = '0px'
      root.style.top = '0px'
      root.style.transform = 'translate3d(' + state.left + 'px,' + state.top + 'px,0)'
      return
    }
    root.style.left = state.left + 'px'
    root.style.top = state.top + 'px'
  }"""),

    ("android-needkey-state",
     """        else { state.connected = false; updateScreen() }""",
     """        else { state.connected = false; state.needKey = !!(d && d.needKey); updateScreen() }"""),
    ("android-needkey-label",
     """    updateTablet()
    dot.style.display = state.connected ? 'none' : 'block'
  }""",
     """    updateTablet()
    if (state.needKey && !isFinite(v)) {
      // No key yet: say so instead of blinking a red error dot.
      labelEl.textContent = '未连接'
      dot.style.display = 'none'
    } else {
      labelEl.textContent = LABEL_TEXT
      dot.style.display = state.connected ? 'none' : 'block'
    }
  }"""),
    ("android-menu-key-row",
     """    menuRow('设置', function () { showSettings('display') })""",
     """    if (ANDROID && state.needKey) {
      menuRow('填写 API Key', function () { ANDROID.openSetup() })
    }
    menuRow('设置', function () { showSettings('display') })"""),

    # A bowl that drops onto a head already wearing a pot hits the pot's bottom (which is
    # its top surface now, because the pot sits upside down). A real drop answers with a
    # short bounce; a gentle placement just slides off the rim. Nothing is fed through a
    # pot, so a bowl sitting on the lid cannot be swallowed by the character underneath.
    ("android-rice-pot-bounce-helpers",
     """  function ironOnHead(p) {""",
     """  function wornPot() {
    var top = null
    for (var i = 0; i < state.bowls.length; i++) {
      var b = state.bowls[i]
      if (!b.iron || !b.onHead || b.fadeT > 0) continue
      if (!top || b.Y < top.Y) top = b
    }
    return top
  }
  function potBlocksFeed(b) {
    // Once a bowl has touched the pot it must reach the floor before anything can feed it,
    // otherwise it just slides off the rim straight into her mouth.
    if (b.potBounced) return true
    var pot = wornPot()
    return !!pot && b.Y <= pot.Y + pot.artH * 0.5
  }
  var potBounceCount = 0
  function bounceOffWornPot(r, dt) {
    if (r.iron || r.dragging || r.onHead) return false
    var pot = wornPot()
    if (!pot) return false
    if (Math.abs(r.X - pot.X) > pot.artW * 0.5) return false
    var surface = pot.Y - pot.artH * 0.5
    var bottom = r.Y + r.R
    var band = Math.max(14, r.R * 0.7)
    // Swept test: a fast drop can cross the whole band inside one frame, and a plain
    // "is the bowl inside the band" check would let it tunnel straight through the lid.
    var prevBottom = bottom - Math.max(0, r.VY) * (dt || 0)
    if (bottom < surface - 1) return false
    if (prevBottom > surface + band) return false
    if (r.VY > 160) {
      var impact = r.VY
      r.Y = surface - r.R
      // Iron is springy enough to throw it clear, and the harder it lands the further it
      // goes — a fixed throttle made every drop bounce the same two weak hops.
      r.VY = -impact * 0.45
      // Push it toward the open half of the screen: she is usually docked against one edge,
      // and shoving the bowl into that wall made it ping between wall and pot, stuck.
      var vsb = viewportRect()
      var dir = (vsb.right - pot.X) > (pot.X - vsb.left) ? 1 : -1
      // Capped: a short drop used to fling the bowl most of the way across the screen.
      r.VX = dir * Math.min(260, Math.max(70, Math.abs(r.VX) * 0.35 + impact * 0.22))
      r.potBounced = 1
      r.bounces = 0
      r.grounded = false
      r.squish = 1; r.squishT = 0; r.squishDur = SQUISH_DUR
      potBounceCount++
      playPool(landPool)
      if (ANDROID && potBounceCount < 6) ANDROID.log('rice bounce ' + potBounceCount +
        ' x=' + Math.round(r.X) + ' y=' + Math.round(r.Y) + ' vy=' + Math.round(r.VY) +
        ' vx=' + Math.round(r.VX) + ' potX=' + Math.round(pot.X))
      return true
    }
    // Set down gently: iron does not spring. Ride the lid and slip off the rim instead of
    // hammering the same spot, which is what made close drops look like a stuck animation.
    r.Y = surface - r.R
    if (r.VY > 0) r.VY = 0
    var vsg = viewportRect()
    var dirg = (vsg.right - pot.X) > (pot.X - vsg.left) ? 1 : -1
    r.VX = dirg * Math.max(70, Math.abs(r.VX) * 0.8)
    // If something still pins it against the pot (a wall, the docked edge), stop being
    // polite and flick it clear instead of letting it sit there for the rest of the day.
    r.potT = (r.potT || 0) + (dt || 0.016)
    if (r.potT > 0.5) {
      r.potT = 0
      r.VX = dirg * 240
      r.VY = -150
    }
    r.potBounced = 1
    r.grounded = false
    return true
  }
  function ironOnHead(p) {"""),
    ("android-rice-pot-bounce-call",
     """        if (r.Y < top) { r.Y = top; if (r.VY < 0) r.VY = 0 }
        if (ironOnHead(r)) attachIronPot(r)""",
     """        if (r.Y < top) { r.Y = top; if (r.VY < 0) r.VY = 0 }
        if (!bounceOffWornPot(r, dt) && ironOnHead(r)) attachIronPot(r)"""),
    ("android-rice-pot-floor-clear",
     """        if (r.Y >= floor) {
          r.Y = floor""",
     """        if (r.Y >= floor) {
          r.Y = floor
          r.potBounced = 0"""),
    ("android-rice-pot-blocks-feed-release",
     """      } else if (riceOnGirl(b)) {
        onRiceFed(b)""",
     """      } else if (riceOnGirl(b) && !potBlocksFeed(b)) {
        onRiceFed(b)"""),
    ("android-rice-pot-blocks-feed-drop",
     """    if (!b.iron && riceOnGirl(b)) onRiceFed(b)""",
     """    if (!b.iron && riceOnGirl(b) && !potBlocksFeed(b)) onRiceFed(b)"""),
    ("android-rice-pot-blocks-feed",
     """      if (!r.iron && !r.fed && riceOnGirl(r)) onRiceFed(r)""",
     """      if (!r.iron && !r.fed && riceOnGirl(r) && !potBlocksFeed(r)) onRiceFed(r)"""),

    # Two independent switches: the bracket overlay, and the magnet that flies the rice to
    # her once the lock settles. Turning the display off must not silently disable the feed.
    ("android-radar-display-off",
     """  function renderRadar(list) {""",
     """  function renderRadar(list) {
    if (window.__vk1RadarOff) {
      if (radarSvg.firstChild) radarSvg.innerHTML = ''
      return
    }"""),
    ("android-radar-magnet-off",
     """    var magnet = state.lockAll && state.lockT >= LOCK_DELAY""",
     """    var magnet = state.lockAll && state.lockT >= LOCK_DELAY && !window.__vk1MagnetOff"""),

    # Facing is decided from state.h, which only gets set when her centre passes the 3/4
    # line. A big pet is wider than half the screen, so its centre can never reach that
    # line: h stayed null, she kept the unmirrored sprite and ended up staring into the
    # right-hand wall. Fall back to whichever half she actually occupies.
    ("android-mirror-by-position",
     """  function mirrored() { return state.h === 'right' }""",
     """  function mirrored() {
    if (state.h === 'right') return true
    if (state.h === 'left') return false
    return state.left + state.size / 2 > (viewport().w || 0) / 2
  }"""),

    # One rectangle per thing that actually wants touches: her square, and each prop on its
    # own. The old single union rect meant a bowl parked across the screen turned the whole
    # bottom strip into a dead zone for every app underneath.
    ("android-multi-region",
     """    var x0 = state.left, y0 = state.top
    var x1 = state.left + state.size, y1 = state.top + state.size
    for (var i = 0; i < state.bowls.length; i++) {
      var b = state.bowls[i]
      if (!b.el || b.fed) continue
      if (b.X - b.artW / 2 < x0) x0 = b.X - b.artW / 2
      if (b.Y - b.artH / 2 < y0) y0 = b.Y - b.artH / 2
      if (b.X + b.artW / 2 > x1) x1 = b.X + b.artW / 2
      if (b.Y + b.artH / 2 > y1) y1 = b.Y + b.artH / 2
    }
    x0 -= 8; y0 -= 8; x1 += 8; y1 += 8
    x0 = Math.max(0, x0); y0 = Math.max(0, y0)
    x1 = Math.min(innerWidth, x1); y1 = Math.min(innerHeight, y1)
    var r = vk1Region
    if (Math.abs(x0 - r.x0) + Math.abs(y0 - r.y0) + Math.abs(x1 - r.x1) + Math.abs(y1 - r.y1) < 3 &&
        now - r.t < 500) return
    r.x0 = x0; r.y0 = y0; r.x1 = x1; r.y1 = y1; r.t = now
    ANDROID.touchRegion(x0, y0, x1, y1)""",
     """    var rects = [[state.left, state.top, state.left + state.size, state.top + state.size]]
    for (var i = 0; i < state.bowls.length && rects.length < 16; i++) {
      var b = state.bowls[i]
      // A worn pot needs no touch target of its own: it comes off by double-clicking her
      // head, which is inside her own rect. Counting them starved the floor bowls.
      if (!b.el || b.fed || b.onHead) continue
      rects.push([b.X - b.artW / 2, b.Y - b.artH / 2, b.X + b.artW / 2, b.Y + b.artH / 2])
    }
    var key = ''
    for (var k = 0; k < rects.length; k++) {
      key += Math.round(rects[k][0]) + ',' + Math.round(rects[k][1]) + ',' +
        Math.round(rects[k][2]) + ',' + Math.round(rects[k][3]) + ';'
    }
    var r = vk1Region
    if (key === r.key && now - r.t < 500) return
    r.key = key; r.t = now
    ANDROID.touchRegions(JSON.stringify(rects))"""),

    # A top-up raises the true balance straight away but is only booked when its bowl is
    # eaten. Until then bookedAt sits BELOW the true balance, so the next poll lands in the
    # "balance is above the book" branch and silently re-syncs the book to the new figure —
    # the readout jumps at once, and then the bowl adds the same money a second time.
    # Result: she shows +10 for a +5 top-up and then drips -0.01 forever trying to walk it
    # back. While a credit is still waiting in a bowl, that branch must do nothing.
    ("android-topup-pending-guard",
     """        if (owed < -1e-9) {
          owed = state.pending
          state.bookedAt = round4(bal + owed)
          state.bookedBal = round4(bal + owed)
        }""",
     """        if (owed < -1e-9) {
          if (state.creditPending > 1e-9) {
            // The difference IS the bowl still sitting on screen. Leave the book alone:
            // feeding it will apply exactly this much.
            owed = 0
            state.pending = 0
            state.dueGap = 0
          } else {
            owed = state.pending
            state.bookedAt = round4(bal + owed)
            state.bookedBal = round4(bal + owed)
          }
        }"""),

    # Upstream only ever takes the pot off with a deliberate double-click on her head
    # (onDown already implements that). This port also knocked it off after 0.7 s of
    # stroking, so every casual pat dropped the pot — reported as a bug, and it is one.
    ("android-pat-keeps-pot",
     """        if (state.bowls.some(function (b) { return b.onHead })) {
          if (pat.moveTime >= (ANDROID ? 0.7 : 0.5)) { knockPotOff(); pat.waiting = true }
        }
        else { pat.active = true; pat.t = 0 }""",
     """        pat.active = true; pat.t = 0"""),

    # The pat hands and the worn pots both live in the stage layer, where the pot carries
    # z-index 10+ — so the hand was drawn underneath the pot it is supposed to pat.
    ("android-hand-above-pot",
     """    hand.style.cssText = 'position:absolute;pointer-events:none;display:none;transform-origin:0 0'""",
     """    hand.style.cssText = 'position:absolute;pointer-events:none;display:none;transform-origin:0 0;z-index:40'"""),


    # Squash bookkeeping: the pot and its hair-erase mask live outside her body element, so
    # the body transform never reaches them. Publish the frame's squash and replay the SAME
    # transform (scale included — a translated pot that does not shrink slides down over her
    # eyes as her head compresses) around the same pivot, which is her feet.
    ("android-squash-publish",
     """    body.style.transform = shakeTf""",
     """    state.squash = { sx: 1, sy: 1, tx: sx, ty: sy, ox: state.left + state.size / 2, oy: state.top + state.size }
    if (squash > 0.001) { state.squash.sx *= 1 + squash * 0.10; state.squash.sy *= 1 - squash * 0.16 }
    if (pat.active) {
      var pis = Math.floor(pat.t / 0.04) % 5
      state.squash.sx *= 1 + pis * 0.025
      state.squash.sy *= 1 - pis * 0.0625
      state.squash.ty += Math.min(state.size * pis * 0.05 * pis * 0.0625,
        Math.max(0, viewport().h - state.top - state.size))
    }
    body.style.transform = shakeTf"""),
    ("android-squash-apply-to-pot",
     """      r.el.style.transform = tf
      r.el.style.zIndex = r.onHead ? String(10 + ironStackIndex(r)) : '0'""",
     """      if (r.onHead && state.squash &&
          (state.squash.sx !== 1 || state.squash.sy !== 1 || state.squash.tx || state.squash.ty)) {
        var so = state.squash
        tf = 'translate(' + so.ox.toFixed(1) + 'px,' + so.oy.toFixed(1) + 'px)' +
          ' translate(' + so.tx.toFixed(1) + 'px,' + so.ty.toFixed(1) + 'px)' +
          ' scale(' + so.sx.toFixed(4) + ',' + so.sy.toFixed(4) + ')' +
          ' translate(' + (-so.ox).toFixed(1) + 'px,' + (-so.oy).toFixed(1) + 'px) ' + tf
      }
      r.el.style.transform = tf
      r.el.style.zIndex = r.onHead ? String(10 + ironStackIndex(r)) : '0'"""),

    # The pat hands were children of .dshvk1-root (z-index 9998) while the bowls live in
    # .dshvk1-stage (10001) — so a worn pot always painted over the hand that pats it.
    # Give the hands their own layer above the stage and shift them from root-local to
    # page coordinates.
    ("android-hand-layer-css",
     """    '.dshvk1-radar{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;overflow:visible}',""",
     """    '.dshvk1-radar{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;overflow:visible}',
    '.dshvk1-hands{position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:10002}',"""),
    ("android-hand-layer-create",
     """  document.body.appendChild(stage)""",
     """  document.body.appendChild(stage)
  var handLayer = document.createElement('div')
  handLayer.className = 'dshvk1-hands'
  document.body.appendChild(handLayer)"""),
    ("android-hand-layer-parent",
     """    root.appendChild(hand)""",
     """    handLayer.appendChild(hand)"""),
    ("android-hand-layer-coords",
     """    hands[frameIndex].style.left = x + 'px'
    hands[frameIndex].style.top = y + 'px'""",
     """    // The layer is fixed to the viewport, so root-local becomes page coordinates.
    hands[frameIndex].style.left = (state.left + x) + 'px'
    hands[frameIndex].style.top = (state.top + y) + 'px'"""),


    # A tall pot tower is funny for about five seconds and then it is a curtain over her
    # face, so the cap is a setting (App 首页可控).
    ("android-pot-stack-cap",
     """    dropIronPot(bowl.X, bowl.Y)""",
     """    var wornNow = 0
    for (var wi = 0; wi < state.bowls.length; wi++) {
      if (state.bowls[wi].onHead && state.bowls[wi].fadeT <= 0) wornNow++
    }
    var potCap = window.__vk1MaxPots
    if (!(potCap > 0)) potCap = 5
    if (wornNow < potCap) dropIronPot(bowl.X, bowl.Y)"""),

]


def main():
    text = open(SRC, encoding="utf-8").read()
    applied = []
    for pid, old, new in PATCHES:
        n = text.count(old)
        if n != 1:
            sys.exit("patch %s: anchor count %d" % (pid, n))
        text = text.replace(old, new)
        applied.append(pid)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print("patched", len(applied), "->", OUT, len(text), "bytes")


if __name__ == "__main__":
    main()
    # The pane draws the worn pot; the copy here must stay invisible, including pots
    # created after the handover.
    ("android-char-hide-pots",
     """      r.el.style.transform = tf
      r.el.style.zIndex = r.onHead ? String(10 + ironStackIndex(r)) : '0'""",
     """      r.el.style.transform = tf
      r.el.style.visibility = (window.__vk1CharHidden && r.onHead) ? 'hidden' : 'visible'
      r.el.style.zIndex = r.onHead ? String(10 + ironStackIndex(r)) : '0'"""),
