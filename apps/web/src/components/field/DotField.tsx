"use client";

import { useEffect, useRef } from "react";

import {
  buildParticles,
  CAMERA_DISTANCE,
  fieldState,
  FORMATIONS,
  type Formation,
  type Section,
} from "@/components/field/formations";
import {
  FULLSCREEN_VERTEX,
  MAX_SHADES,
  PANELS_FRAGMENT,
  POINTS_FRAGMENT,
  POINTS_VERTEX,
} from "@/components/field/shaders";

/*
 * The landing page's signature effect: one fixed WebGL2 canvas behind the page. Sections say
 * which formation they want (`data-field="panels|grid|cloud|torus|rings"`) and the dots morph
 * between them as you scroll; the hero and closing sections show our own procedural "imagery"
 * panels, which dissolve into the dots. Text over the field is marked `data-field-shade`, and
 * the field darkens behind it.
 *
 * Reduced motion: no animation loop, no morphing; static panels in the hero, a still grid
 * elsewhere. Without WebGL2 the sections' CSS fallback shows (html lacks data-field-on).
 */

const MAX_DPR = 1.5;

function compile(gl: WebGL2RenderingContext, vertex: string, fragment: string) {
  const program = gl.createProgram();
  for (const [type, source] of [
    [gl.VERTEX_SHADER, vertex],
    [gl.FRAGMENT_SHADER, fragment],
  ] as const) {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.warn("Field shader failed to compile", gl.getShaderInfoLog(shader));
      return null;
    }
    gl.attachShader(program, shader);
    gl.deleteShader(shader);
  }
  gl.linkProgram(program);
  return gl.getProgramParameter(program, gl.LINK_STATUS) ? program : null;
}

function weights(formation: Formation): number[] {
  return FORMATIONS.map((f) => (f === formation ? 1 : 0));
}

function readSections(): (Section & { element: HTMLElement })[] {
  return Array.from(document.querySelectorAll<HTMLElement>("section[data-field]")).map(
    (element) => {
      const rect = element.getBoundingClientRect();
      return {
        element,
        formation: element.dataset.field as Formation,
        top: rect.top + window.scrollY,
        bottom: rect.bottom + window.scrollY,
      };
    },
  );
}

export function DotField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext("webgl2", { antialias: false, premultipliedAlpha: false });
    if (!canvas || !gl) return;
    const panels = compile(gl, FULLSCREEN_VERTEX, PANELS_FRAGMENT);
    const points = compile(gl, POINTS_VERTEX, POINTS_FRAGMENT);
    if (!panels || !points) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const root = document.documentElement;
    root.dataset.fieldOn = "";

    // Fullscreen triangle for the panels pass.
    const quadVao = gl.createVertexArray();
    gl.bindVertexArray(quadVao);
    const quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const corner = gl.getAttribLocation(panels, "a_corner");
    gl.enableVertexAttribArray(corner);
    gl.vertexAttribPointer(corner, 2, gl.FLOAT, false, 0, 0);

    const pointsVao = gl.createVertexArray();
    const buffers: WebGLBuffer[] = [];
    let count = 0;
    let builtFor = { width: 0, height: 0 };

    const upload = (name: string, data: Float32Array, size: number) => {
      const location = gl.getAttribLocation(points, name);
      if (location < 0) return;
      const buffer = gl.createBuffer();
      buffers.push(buffer);
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, size, gl.FLOAT, false, 0, 0);
    };

    const build = (width: number, height: number) => {
      buffers.splice(0).forEach((b) => gl.deleteBuffer(b));
      const particles = buildParticles({ width, height });
      gl.bindVertexArray(pointsVao);
      upload("a_grid", particles.positions.grid, 3);
      upload("a_cloud", particles.positions.cloud, 3);
      upload("a_torus", particles.positions.torus, 3);
      upload("a_rings", particles.positions.rings, 3);
      upload("a_inGrid", particles.inGrid, 1);
      upload("a_inRings", particles.inRings, 1);
      upload("a_seed", particles.seeds, 1);
      count = particles.count;
      builtFor = { width, height };
    };

    const u = (program: WebGLProgram, name: string) => gl.getUniformLocation(program, name);
    const pu = Object.fromEntries(
      [
        "u_res",
        "u_time",
        "u_rect",
        "u_alpha",
        "u_dissolve",
        "u_layout",
        "u_shade",
        "u_shadeCap",
        "u_shades",
        "u_dpr",
      ].map((n) => [n, u(panels, n)]),
    );
    const qu = Object.fromEntries(
      [
        "u_from",
        "u_to",
        "u_t",
        "u_time",
        "u_aspect",
        "u_res",
        "u_camera",
        "u_shade",
        "u_shadeCap",
        "u_shades",
        "u_dpr",
      ].map((n) => [n, u(points, n)]),
    );

    let dpr = 1;
    const resize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, width < 768 ? 1.25 : MAX_DPR);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      gl.viewport(0, 0, canvas.width, canvas.height);
      // Phones resize as the address bar shows and hides; only rebuild for real changes.
      if (width !== builtFor.width || Math.abs(height - builtFor.height) > height * 0.2) {
        build(width, height);
      }
    };
    resize();

    const shades = new Float32Array(MAX_SHADES * 4);
    const caps = new Float32Array(MAX_SHADES);
    const readShades = () => {
      const elements = document.querySelectorAll<HTMLElement>("[data-field-shade]");
      let n = 0;
      for (const element of elements) {
        const r = element.getBoundingClientRect();
        if (n >= MAX_SHADES || r.bottom < 0 || r.top > window.innerHeight || r.width === 0)
          continue;
        shades.set([r.left * dpr, r.top * dpr, r.width * dpr, r.height * dpr], n * 4);
        // `data-field-shade="large"`: display type (3:1 is enough); otherwise body text (4.5:1).
        caps[n] = element.dataset.fieldShade === "large" ? 0.45 : 0.3;
        n++;
      }
      return n;
    };

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    const started = performance.now();

    const draw = () => {
      const still = reducedMotion.matches;
      const time = still ? 12 : (performance.now() - started) / 1000;
      const vh = window.innerHeight;
      const sections = readSections();
      let state = fieldState(sections, window.scrollY, vh);
      if (still) {
        // A still picture: the panels where they belong, a quiet grid everywhere else.
        const current = state.t < 0.5 ? state.from : state.to;
        const formation: Formation = current === "panels" ? "panels" : "grid";
        state = { from: formation, to: formation, t: 0 };
      }
      const nShades = readShades();

      gl.clearColor(1 / 255, 0, 1 / 255, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);

      // Panels: the hero and the closing section, wherever they are on screen.
      gl.useProgram(panels);
      gl.bindVertexArray(quadVao);
      gl.uniform2f(pu.u_res!, canvas.width, canvas.height);
      gl.uniform1f(pu.u_time!, time);
      gl.uniform1f(pu.u_dpr!, dpr);
      gl.uniform4fv(pu.u_shade!, shades);
      gl.uniform1fv(pu.u_shadeCap!, caps);
      gl.uniform1i(pu.u_shades!, nShades);
      const tall = window.innerWidth < window.innerHeight;
      const panelSections = sections.filter((s) => s.formation === "panels");
      panelSections.forEach((section, index) => {
        const rect = section.element.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > vh) return;
        // How much of this section's picture is showing: all of it while held, fading as the
        // field morphs away from it (or towards it).
        const isFirst = index === 0;
        const leaving = state.from === "panels" && state.to !== "panels";
        const arriving = state.to === "panels" && state.from !== "panels";
        let presence = state.from === "panels" && state.to === "panels" ? 1 : 0;
        if (leaving && isFirst) presence = 1 - state.t;
        if (arriving && !isFirst) presence = state.t;
        if (presence <= 0.001) return;
        gl.uniform4f(
          pu.u_rect!,
          rect.left * dpr,
          rect.top * dpr,
          rect.width * dpr,
          rect.height * dpr,
        );
        gl.uniform1f(pu.u_alpha!, 1);
        gl.uniform1f(pu.u_dissolve!, 1 - presence);
        gl.uniform1i(pu.u_layout!, (isFirst ? 0 : 2) + (tall ? 1 : 0));
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      });

      // Dots.
      if (!(state.from === "panels" && state.to === "panels")) {
        gl.useProgram(points);
        gl.bindVertexArray(pointsVao);
        gl.uniform1fv(qu.u_from!, weights(state.from));
        gl.uniform1fv(qu.u_to!, weights(state.to));
        gl.uniform1f(qu.u_t!, state.t);
        gl.uniform1f(qu.u_time!, time);
        gl.uniform1f(qu.u_aspect!, window.innerWidth / vh);
        gl.uniform2f(qu.u_res!, canvas.width, canvas.height);
        gl.uniform1f(qu.u_camera!, CAMERA_DISTANCE);
        gl.uniform1f(qu.u_dpr!, dpr);
        gl.uniform4fv(qu.u_shade!, shades);
        gl.uniform1fv(qu.u_shadeCap!, caps);
        gl.uniform1i(qu.u_shades!, nShades);
        gl.drawArrays(gl.POINTS, 0, count);
      }
    };

    let frame = 0;
    const loop = () => {
      draw();
      if (!reducedMotion.matches && !document.hidden) frame = requestAnimationFrame(loop);
    };
    const restart = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(loop);
    };
    // Under reduced motion there is no loop: redraw when something moves.
    const redrawStill = () => {
      if (reducedMotion.matches) requestAnimationFrame(draw);
    };
    const onResize = () => {
      resize();
      if (reducedMotion.matches) redrawStill();
    };

    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", redrawStill, { passive: true });
    document.addEventListener("visibilitychange", restart);
    reducedMotion.addEventListener("change", restart);
    restart();

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", redrawStill);
      document.removeEventListener("visibilitychange", restart);
      reducedMotion.removeEventListener("change", restart);
      delete root.dataset.fieldOn;
      buffers.forEach((b) => gl.deleteBuffer(b));
      gl.deleteBuffer(quad);
      gl.deleteVertexArray(quadVao);
      gl.deleteVertexArray(pointsVao);
      gl.deleteProgram(panels);
      gl.deleteProgram(points);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 size-full"
    />
  );
}
