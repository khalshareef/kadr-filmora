/* Kadr motion helpers — deterministic, time-driven motion graphics for HTML/SVG pages rendered by motion_render.py.
   A page defines  window.KADR = {width, height, fps, duration, render(t)}  and draws everything as a pure function of t
   (seconds). No CSS animations or timers: the renderer seeks frame by frame, so the result is exact and repeatable.

   Helpers (all pure):
     E.out(u) E.in(u) E.inout(u) E.back(u) E.elastic(u)       easing, u in 0..1
     prog(t, t0, t1, ease='inout')                             0..1 progress of a time window (clamped, eased)
     lerp(a, b, u), clamp(v, a, b), mapr(v, a, b, c, d)
     draw(el, p)            SVG stroke drawing 0..1 (path needs pathLength="1"); p<0 hides
     tr(el, {x, y, s, sx, sy, r, o})  transform + opacity (x/y in px, s scale, r degrees)
     pop(t, t0, d=0.45)     scale 0 -> 1 with overshoot ; fade(t, t0, t1) ; win(t, a, b) true inside [a, b)
     stagger(i, step)       i * step ; wave(t, i, speed, phase) 0..1 oscillation
     spring(t, t0, f=2.2, z=0.75)   closed-form spring step 0 -> 1 (f = speed in Hz, z = damping; 1 = no overshoot)
     springs(t, steps, f, z)        value that changes target many times: steps = [[t0, value], ...] (sum of springs)
     expOut(t, t0, rate=7)          exponential arrival 0 -> 1 (enters already moving, settles softly)
     zoomLerp(z0, z1, u)            zoom interpolated in log space (constant perceived speed)
     $(id)                  document.getElementById
   Use:  const { E, prog, draw, tr, pop, fade, $ } = KADR_HELPERS;
*/
(() => {
const E = {
  lin: u => u,
  in: u => u * u * u,
  out: u => 1 - Math.pow(1 - u, 3),
  inout: u => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2),
  back: u => 1 + 2.70158 * Math.pow(u - 1, 3) + 1.70158 * Math.pow(u - 1, 2),
  elastic: u => (u === 0 || u === 1 ? u : Math.pow(2, -10 * u) * Math.sin((u * 10 - 0.75) * (2 * Math.PI) / 3) + 1),
};
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, u) => a + (b - a) * u;
const mapr = (v, a, b, c, d) => c + (d - c) * clamp((v - a) / (b - a), 0, 1);
const prog = (t, t0, t1, ease = 'inout') => E[ease](clamp((t - t0) / Math.max(1e-6, t1 - t0), 0, 1));
const win = (t, a, b) => t >= a && t < b;
const stagger = (i, step) => i * step;
const wave = (t, i = 0, speed = 1, phase = 0.6) => 0.5 + 0.5 * Math.sin(t * speed * 2 * Math.PI + i * phase);
const pop = (t, t0, d = 0.45) => E.back(clamp((t - t0) / d, 0, 1));
const fade = (t, t0, t1) => clamp((t - t0) / Math.max(1e-6, t1 - t0), 0, 1);
const $ = id => document.getElementById(id);
function spring(t, t0, f = 2.2, z = 0.75) {
  const tau = t - t0; if (tau <= 0) return 0;
  const w = 2 * Math.PI * f;
  if (z >= 1) return 1 - (1 + w * tau) * Math.exp(-w * tau);
  const wd = w * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * w * tau) * (Math.cos(wd * tau) + (z / Math.sqrt(1 - z * z)) * Math.sin(wd * tau));
}
function springs(t, steps, f = 2.2, z = 0.8) {
  let v = steps.length ? steps[0][1] : 0;
  for (let i = 1; i < steps.length; i++) v += (steps[i][1] - steps[i - 1][1]) * spring(t, steps[i][0], f, z);
  return v;
}
const expOut = (t, t0, rate = 7) => (t <= t0 ? 0 : 1 - Math.exp(-rate * (t - t0)));
const zoomLerp = (z0, z1, u) => Math.exp(Math.log(z0) + (Math.log(z1) - Math.log(z0)) * u);

function draw(el, p) {
  if (!el) return;
  el.style.strokeDasharray = '1 1';
  el.style.strokeDashoffset = String(1 - clamp(p, 0, 1));
  el.style.opacity = p <= 0 ? 0 : 1;
}

function tr(el, o = {}) {
  if (!el) return;
  const x = o.x || 0, y = o.y || 0, r = o.r || 0;
  const sx = o.sx !== undefined ? o.sx : (o.s !== undefined ? o.s : 1);
  const sy = o.sy !== undefined ? o.sy : (o.s !== undefined ? o.s : 1);
  el.style.transformBox = 'fill-box';
  el.style.transformOrigin = o.origin || 'center';
  el.style.transform = `translate(${x}px, ${y}px) rotate(${r}deg) scale(${sx}, ${sy})`;
  if (o.o !== undefined) el.style.opacity = clamp(o.o, 0, 1);
}

window.KADR_HELPERS = { E, clamp, lerp, mapr, prog, win, stagger, wave, pop, fade, draw, tr, $, spring, springs, expOut, zoomLerp };
})();
