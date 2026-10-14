"use client";

import { useEffect, useRef } from "react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { cn } from "@/lib/cn";

/*
 * The hero's dot field with a radar sweep: a raw WebGL2 fragment shader (no 3D library). Each
 * dot brightens as the beam passes and fades behind it; a few "blips" glow orange longer.
 * Colours are the design tokens (bg-0, muted-3, accent). Decorative only.
 */
const VERTEX = `#version 300 es
in vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }`;

const FRAGMENT = `#version 300 es
precision highp float;
uniform vec2 u_res;
uniform vec2 u_origin;
uniform float u_time;
uniform float u_dpr;
out vec4 color;

const vec3 BG = vec3(1.0, 0.0, 1.0) / 255.0;
const vec3 DOT = vec3(94.0, 89.0, 74.0) / 255.0;
const vec3 ACCENT = vec3(255.0, 157.0, 0.0) / 255.0;
const float TAU = 6.28318530718;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

void main() {
  float spacing = 16.0 * u_dpr;
  vec2 cell = floor(gl_FragCoord.xy / spacing);
  vec2 centre = (cell + 0.5) * spacing;
  float dist = length(gl_FragCoord.xy - centre);
  float dotMask = 1.0 - smoothstep(0.9 * u_dpr, 1.5 * u_dpr, dist);

  vec2 v = centre - u_origin;
  float radius = length(v);
  float angle = atan(v.y, v.x);
  float beam = mod(-u_time * 0.55, TAU);
  float behind = mod(angle - beam, TAU);          // 0 on the beam, growing behind it
  float trail = exp(-behind * 2.6);

  float reach = max(u_res.x, u_res.y) * 0.95;
  float falloff = 1.0 - smoothstep(reach * 0.25, reach, radius);
  float rings = 1.0 - smoothstep(0.0, 1.2 * u_dpr, abs(mod(radius, 180.0 * u_dpr) - 90.0 * u_dpr));

  float blip = step(0.988, hash(cell)) * exp(-behind * 0.7);
  float glow = clamp(trail * 0.8 + blip, 0.0, 1.0);
  float alpha = (dotMask * (0.28 + 0.72 * glow) + rings * 0.05) * falloff;
  color = vec4(mix(BG, mix(DOT, ACCENT, glow), alpha), 1.0);
}`;

function compile(gl: WebGL2RenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
}

export function RadarField({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext("webgl2", { antialias: false, alpha: false });
    if (!canvas || !gl) return; // the CSS dot pattern behind the canvas stays visible

    const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX);
    const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT);
    const program = gl.createProgram();
    if (!vertex || !fragment || !program) return;
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);

    // One triangle that covers the viewport.
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    const uniform = (name: string) => gl.getUniformLocation(program, name);
    const [uRes, uOrigin, uTime, uDpr] = ["u_res", "u_origin", "u_time", "u_dpr"].map(uniform);

    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const resize = () => {
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(uRes!, canvas.width, canvas.height);
      // Sweep from the right-hand side, behind the headline's empty space.
      gl.uniform2f(uOrigin!, canvas.width * 0.78, canvas.height * 0.62);
      gl.uniform1f(uDpr!, dpr);
    };
    resize();

    let frame = 0;
    let visible = true;
    const started = performance.now();
    const draw = (now: number) => {
      gl.uniform1f(uTime!, reducedMotion ? 1.4 : (now - started) / 1000);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      if (!reducedMotion && visible && !document.hidden) frame = requestAnimationFrame(draw);
    };
    const restart = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(draw);
    };
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? true;
      if (visible) restart();
    });
    observer.observe(canvas);
    const resizeObserver = new ResizeObserver(() => {
      resize();
      restart();
    });
    resizeObserver.observe(canvas);
    document.addEventListener("visibilitychange", restart);
    restart();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resizeObserver.disconnect();
      document.removeEventListener("visibilitychange", restart);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
    };
  }, [reducedMotion]);

  return (
    <div aria-hidden className={cn("radar-field", className)}>
      <canvas ref={canvasRef} className="size-full" />
    </div>
  );
}
