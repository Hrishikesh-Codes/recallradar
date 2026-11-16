import { ImageResponse } from "next/og";

/*
 * The share card (1200×630), drawn at build time in the site's palette: the halftone dot field
 * with an orange glow, the headline, and the wordmark. No photos, no external fonts.
 */
export const alt = "RecallRadar: know if what you own was recalled";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const COLS = 40;
const ROWS = 21;
const GAP = 30;

export default function OpenGraphImage() {
  const dots = [];
  for (let row = 0; row < ROWS; row++) {
    for (let col = 0; col < COLS; col++) {
      // Brightest towards the right, where the headline leaves room.
      const dx = (col - COLS * 0.78) / COLS;
      const dy = (row - ROWS * 0.45) / ROWS;
      const glow = Math.max(0, 1 - Math.sqrt(dx * dx * 3 + dy * dy * 2.4) * 1.9);
      const lit = glow > 0.28 && (col * 7 + row * 13) % 5 !== 0;
      const dot = 3 + Math.round(glow * 9);
      dots.push(
        <div
          key={`${row}-${col}`}
          style={{
            position: "absolute",
            left: 15 + col * GAP - dot / 2,
            top: 15 + row * GAP - dot / 2,
            width: dot,
            height: dot,
            borderRadius: dot,
            background: lit ? (glow > 0.6 ? "#ff9d00" : "#e34608") : "#5e594a",
            opacity: lit ? 0.35 + glow * 0.65 : 0.45,
          }}
        />,
      );
    }
  }
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        background: "#010001",
        color: "#eeeadc",
      }}
    >
      {dots}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          background: "linear-gradient(90deg, #010001 0%, rgba(1,0,1,0.86) 46%, rgba(1,0,1,0) 78%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 72,
          top: 64,
          display: "flex",
          alignItems: "center",
          fontSize: 30,
          fontWeight: 600,
          letterSpacing: 1,
        }}
      >
        <div
          style={{
            width: 18,
            height: 18,
            borderRadius: 18,
            background: "#ff9d00",
            marginRight: 16,
          }}
        />
        RECALLRADAR
      </div>
      <div
        style={{
          position: "absolute",
          left: 72,
          bottom: 132,
          display: "flex",
          flexDirection: "column",
          fontSize: 104,
          fontWeight: 600,
          lineHeight: 0.95,
          letterSpacing: -3,
        }}
      >
        <div style={{ display: "flex" }}>KNOW IF WHAT</div>
        <div style={{ display: "flex" }}>YOU OWN WAS</div>
        <div style={{ display: "flex", color: "#ff9d00" }}>RECALLED</div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 76,
          bottom: 64,
          display: "flex",
          fontSize: 28,
          color: "#bbb8ab",
        }}
      >
        Checked against official U.S. recall notices, with the evidence.
      </div>
    </div>,
    size,
  );
}
