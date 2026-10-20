/*
 * GLSL for the landing page's field (WebGL2, no 3D library). Two passes:
 *
 * - PANELS: our own "imagery" for the hero and the closing section: domain-warped noise
 *   streaked like motion blur and graded black → ember → orange → sand with film grain, laid
 *   out as a collage of panels. It dissolves in pixel blocks into the dot grid as you scroll.
 * - POINTS: one set of particles morphing between formations (halftone grid, cloud, spinning
 *   globe of rings, radar rings).
 *
 * Text that sits over the field is passed in as rectangles (`u_shade`), and both passes darken
 * behind it so it keeps its contrast.
 */

export const MAX_SHADES = 6;

const COLOURS = /* glsl */ `
const vec3 BG = vec3(1.0, 0.0, 1.0) / 255.0;
const vec3 EMBER = vec3(70.0, 14.0, 4.0) / 255.0;
const vec3 DEEP = vec3(227.0, 70.0, 8.0) / 255.0;
const vec3 SOL = vec3(255.0, 157.0, 0.0) / 255.0;
const vec3 SAND = vec3(238.0, 234.0, 220.0) / 255.0;
const vec3 MOSS = vec3(94.0, 89.0, 74.0) / 255.0;
`;

const NOISE = /* glsl */ `
float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
             mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float sum = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 4; i++) {
    sum += amp * noise(p);
    p = mat2(1.6, 1.2, -1.2, 1.6) * p;
    amp *= 0.5;
  }
  return sum;
}

// Smoky, silky shapes: fbm warped by fbm, stretched along x like a long exposure.
float heat(vec2 p, float t, float seed) {
  p *= vec2(0.55, 1.7);
  vec2 q = vec2(fbm(p + vec2(seed, t * 0.05)), fbm(p * 1.3 + vec2(5.2 - t * 0.04, 1.3 + seed)));
  vec2 r = vec2(fbm(p + 2.2 * q + vec2(1.7, 9.2) + t * 0.03),
                fbm(p + 2.2 * q + vec2(8.3, 2.8) - t * 0.02));
  return fbm(p + 2.6 * r);
}

vec3 grade(float lum) {
  vec3 c = mix(BG, EMBER, smoothstep(0.0, 0.3, lum));
  c = mix(c, DEEP, smoothstep(0.26, 0.66, lum));
  c = mix(c, SOL, smoothstep(0.7, 0.95, lum) * 0.85);
  return mix(c, SAND, smoothstep(0.93, 1.05, lum) * 0.5);
}
`;

const SHADE = /* glsl */ `
uniform vec4 u_shade[${MAX_SHADES}];    // x, y, width, height in device pixels, y down
uniform float u_shadeCap[${MAX_SHADES}]; // brightest the field may be behind that text
uniform int u_shades;
uniform float u_dpr;

// Distance-weighted: 1 inside a text rectangle, fading to 0 within 110 CSS px of it.
float shadeWeight(vec4 r, vec2 px) {
  vec2 d = max(max(r.xy - px, px - (r.xy + r.zw)), 0.0);
  return 1.0 - smoothstep(0.0, 110.0 * u_dpr, length(d));
}

float shadeAt(vec2 px) {
  float s = 0.0;
  for (int i = 0; i < ${MAX_SHADES}; i++) {
    if (i >= u_shades) break;
    s = max(s, shadeWeight(u_shade[i], px));
  }
  return s;
}

// Dots only dim behind body text; display type is large enough to sit on them.
float bodyShadeAt(vec2 px) {
  float s = 0.0;
  for (int i = 0; i < ${MAX_SHADES}; i++) {
    if (i >= u_shades) break;
    if (u_shadeCap[i] < 0.4) s = max(s, shadeWeight(u_shade[i], px));
  }
  return s;
}

// Text keeps its contrast. Behind display type the field stays at ember (sand and orange both
// clear 3:1 there); behind body text it stays darker still (over 4.5:1).
float capAt(vec2 px) {
  float cap = 1.0;
  for (int i = 0; i < ${MAX_SHADES}; i++) {
    if (i >= u_shades) break;
    cap = min(cap, mix(1.0, u_shadeCap[i], shadeWeight(u_shade[i], px)));
  }
  return cap;
}
`;

export const FULLSCREEN_VERTEX = /* glsl */ `#version 300 es
in vec2 a_corner;
void main() { gl_Position = vec4(a_corner, 0.0, 1.0); }`;

export const PANELS_FRAGMENT = /* glsl */ `#version 300 es
precision highp float;
uniform vec2 u_res;          // device pixels
uniform float u_time;
uniform vec4 u_rect;         // the section, device pixels, y down
uniform float u_alpha;
uniform float u_dissolve;    // 0 = whole, 1 = gone
uniform int u_layout;        // 0 hero wide, 1 hero tall, 2 closing wide, 3 closing tall
out vec4 colour;
${COLOURS}
${NOISE}
${SHADE}

// Panels in section-relative units (x, y, w, h; y down). Later panels sit on top.
vec4 panel(int arrangement, int i) {
  if (arrangement == 0) {
    if (i == 0) return vec4(0.0, 0.0, 1.0, 0.62);
    if (i == 1) return vec4(0.0, 0.5, 0.44, 0.5);
    return vec4(0.44, 0.66, 0.56, 0.34);
  }
  if (arrangement == 1) {
    if (i == 0) return vec4(0.0, 0.0, 1.0, 0.56);
    if (i == 1) return vec4(0.0, 0.5, 0.62, 0.5);
    return vec4(0.38, 0.68, 0.62, 0.32);
  }
  if (arrangement == 2) {
    if (i == 0) return vec4(0.0, 0.0, 0.36, 0.55);
    if (i == 1) return vec4(0.3, 0.0, 0.7, 0.42);
    return vec4(0.56, 0.42, 0.44, 0.58);
  }
  if (i == 0) return vec4(0.0, 0.0, 0.6, 0.4);
  if (i == 1) return vec4(0.4, 0.3, 0.6, 0.36);
  return vec4(0.0, 0.66, 0.7, 0.34);
}

void main() {
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
  vec2 local = (px - u_rect.xy) / u_rect.zw;
  if (any(lessThan(local, vec2(0.0))) || any(greaterThan(local, vec2(1.0)))) discard;

  int index = -1;
  vec4 box = vec4(0.0);
  for (int i = 0; i < 3; i++) {
    vec4 b = panel(u_layout, i);
    if (all(greaterThanEqual(local, b.xy)) && all(lessThan(local, b.xy + b.zw))) { index = i; box = b; }
  }
  if (index < 0) discard;

  // Each panel is its own "shot": different framing, direction, speed and exposure.
  float k = float(index);
  float seed = k * 7.31 + float(u_layout) * 3.17;
  vec2 uv = (local - box.xy) / box.zw;
  vec2 p = (uv - 0.5) * vec2(box.z * u_rect.z / u_rect.w, box.w) * (2.2 + k * 0.6);
  float angle = (k - 1.0) * 0.55 + 0.15;
  p = mat2(cos(angle), -sin(angle), sin(angle), cos(angle)) * p + seed;
  float t = u_time * (0.5 + 0.2 * k);
  float h = heat(p, t, seed);
  // Long-exposure streaks on top of the smoke.
  float streak = noise(p * vec2(0.35, 11.0) + vec2(t * 0.15, seed)) - 0.5;
  float lum = smoothstep(0.42, 0.84, h + streak * 0.24);
  // Large dark shapes, like the silhouettes in a photograph.
  lum *= smoothstep(0.3, 0.55, fbm(p * 0.32 + vec2(seed * 3.1, t * 0.02)));
  lum = clamp(lum * (k == 1.0 ? 0.85 : k == 2.0 ? 1.15 : 1.0), 0.0, 1.0);
  // A soft print vignette; the panel's own edge stays hard, so the collage reads.
  vec2 e = uv * (1.0 - uv) * 4.0;
  lum *= mix(0.6, 1.0, smoothstep(0.0, 0.45, min(e.x, e.y)));
  lum = min(lum, capAt(px));

  vec3 c = grade(lum);
  // Panel tints: one redder, one warmer.
  c *= k == 1.0 ? vec3(1.04, 0.86, 0.8) : k == 2.0 ? vec3(1.0, 1.04, 0.95) : vec3(1.0);

  // Dissolve in 8 px blocks, so the picture breaks up into the dot grid behind it.
  float block = hash12(floor(px / (8.0 * u_dpr)));
  if (block < u_dissolve) discard;
  colour = vec4(c, u_alpha);
}`;

// The panels render at half resolution (a quarter of the pixels: the noise is the expensive
// part, and the picture is soft anyway); this scales them up and adds film grain at full size.
export const COMPOSITE_FRAGMENT = /* glsl */ `#version 300 es
precision highp float;
uniform sampler2D u_panels;
uniform vec2 u_res;
uniform float u_time;
out vec4 colour;
${COLOURS}
${NOISE}
void main() {
  vec4 c = texture(u_panels, gl_FragCoord.xy / u_res);
  if (c.a <= 0.0) discard;
  colour = vec4(c.rgb + (hash12(gl_FragCoord.xy + fract(u_time) * 97.0) - 0.5) * 0.06, c.a);
}`;

export const POINTS_VERTEX = /* glsl */ `#version 300 es
precision highp float;
in vec3 a_grid;
in vec3 a_cloud;
in vec3 a_torus;
in vec3 a_rings;
in float a_inGrid;
in float a_inRings;
in float a_seed;

uniform float u_from[5];      // weights: panels, grid, cloud, torus, rings
uniform float u_to[5];
uniform float u_t;
uniform float u_time;
uniform float u_aspect;
uniform vec2 u_res;
uniform float u_camera;
uniform float u_spacing;      // grid spacing, CSS px (dot sizes scale with it)
out vec3 v_colour;
out float v_alpha;
${COLOURS}
${NOISE}
${SHADE}

mat3 rotateY(float a) { float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }
mat3 rotateX(float a) { float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }

struct Look { vec3 pos; vec3 colour; float alpha; float size; };

Look formation(int f) {
  Look l;
  if (f <= 1) {
    // Halftone grid: dot size and colour follow a slow "image" of the same heat field.
    vec2 screen = vec2(a_grid.x / u_aspect, a_grid.y) * 0.5 + 0.5;
    float b = heat(vec2(screen.x * u_aspect, screen.y) * 1.4 + 3.0, u_time * 0.35, 1.7);
    b = smoothstep(0.35, 0.85, b) * smoothstep(1.25, 0.2, length((screen - 0.5) * vec2(u_aspect, 1.0)));
    float twinkle = 0.75 + 0.25 * sin(u_time * (1.2 + a_seed * 2.0) + a_seed * 40.0);
    l.pos = a_grid;
    l.colour = b > 0.4 ? mix(DEEP * 0.85, mix(DEEP, SOL, 0.35), smoothstep(0.4, 0.95, b)) : MOSS * 0.8;
    l.alpha = f == 0 ? 0.0 : a_inGrid * mix(0.6, 1.0, b) * twinkle;
    l.size = mix(0.17, 0.62, b) * u_spacing;
    return l;
  }
  if (f == 2) {
    vec3 p = rotateY(u_time * 0.06) * a_cloud;
    p += 0.015 * vec3(sin(u_time * 0.7 + a_seed * 30.0), cos(u_time * 0.6 + a_seed * 20.0), 0.0);
    l.pos = p;
    l.colour = a_seed > 0.85 ? MOSS * 1.5 : mix(DEEP, SOL, fract(a_seed * 7.0) * 0.45);
    l.alpha = 0.9 * smoothstep(-1.2, 0.6, p.z);
    l.size = 0.22 * u_spacing;
    return l;
  }
  if (f == 3) {
    vec3 p = rotateX(0.22) * rotateY(u_time * 0.1) * a_torus;
    float front = smoothstep(-0.9, 0.9, p.z);
    l.pos = p;
    l.colour = mix(MOSS * 1.4, mix(DEEP, SOL, front * 0.4), smoothstep(0.15, 0.7, front));
    l.alpha = mix(0.35, 1.0, front);
    l.size = 0.34 * u_spacing;
    return l;
  }
  // Radar: pulses run outwards and a sweep brightens the dots it passes.
  float radius = length(a_rings.xy);
  float pulse = exp(-8.0 * fract(radius * 1.3 - u_time * 0.28));
  float angle = atan(a_rings.y, a_rings.x);
  float sweep = exp(-2.5 * mod(angle + u_time * 0.6, 6.28318));
  float glow = clamp(pulse * 0.7 + sweep * 0.9, 0.0, 1.0);
  l.pos = a_rings * (1.0 + 0.012 * sin(u_time * 1.5 - radius * 6.0));
  float fade = 1.0 - smoothstep(0.35, 1.0, radius);
  l.colour = mix(DEEP, SOL, max(glow * 0.75, fade * 0.45));
  l.alpha = a_inRings * mix(0.6, 1.0, max(glow, fade * 0.6));
  l.size = mix(0.56, 0.68, glow) * u_spacing;
  return l;
}

Look blend(float w[5]) {
  Look sum = Look(vec3(0.0), vec3(0.0), 0.0, 0.0);
  for (int f = 0; f < 5; f++) {
    if (w[f] <= 0.0) continue;
    Look l = formation(f);
    sum.pos += l.pos * w[f];
    sum.colour += l.colour * w[f];
    sum.alpha += l.alpha * w[f];
    sum.size += l.size * w[f];
  }
  return sum;
}

void main() {
  // Each dot starts its move a little later than the last: the morph ripples, not snaps.
  float t = clamp((u_t - a_seed * 0.3) / 0.7, 0.0, 1.0);
  t = t * t * (3.0 - 2.0 * t);
  Look a = blend(u_from);
  Look b = a;
  if (u_t > 0.0) b = blend(u_to);
  vec3 pos = mix(a.pos, b.pos, t);
  float perspective = u_camera / (u_camera - pos.z);
  vec2 clip = vec2(pos.x * perspective / u_aspect, pos.y * perspective);
  gl_Position = vec4(clip, 0.0, 1.0);

  vec2 px = vec2(clip.x * 0.5 + 0.5, 0.5 - clip.y * 0.5) * u_res;
  v_colour = mix(a.colour, b.colour, t);
  v_alpha = mix(a.alpha, b.alpha, t) * (1.0 - 0.65 * bodyShadeAt(px));
  gl_PointSize = mix(a.size, b.size, t) * perspective * u_dpr;
}`;

export const POINTS_FRAGMENT = /* glsl */ `#version 300 es
precision highp float;
in vec3 v_colour;
in float v_alpha;
out vec4 colour;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float a = v_alpha * (1.0 - smoothstep(0.32, 0.5, d));
  if (a <= 0.002) discard;
  colour = vec4(v_colour, a);
}`;
