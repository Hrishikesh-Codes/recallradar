/**
 * The app icon: the radar mark in orange on near-black, drawn for `ImageResponse`. The mark
 * fills the middle 60%, inside the safe zone Android uses when it crops "maskable" icons.
 */
export function RadarIcon({ size }: { size: number }) {
  const mark = Math.round(size * 0.6);
  return (
    <div
      style={{
        width: size,
        height: size,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#010001",
      }}
    >
      <svg
        width={mark}
        height={mark}
        viewBox="0 0 32 32"
        fill="none"
        stroke="#ff9d00"
        strokeWidth={1.75}
        strokeLinecap="round"
      >
        <circle cx="16" cy="16" r="2.5" fill="#ff9d00" stroke="none" />
        <path d="M10.3 21.7a8 8 0 0 1 0-11.4M21.7 10.3a8 8 0 0 1 0 11.4" />
        <path d="M6.1 25.9a14 14 0 0 1 0-19.8M25.9 6.1a14 14 0 0 1 0 19.8" opacity="0.55" />
      </svg>
    </div>
  );
}
