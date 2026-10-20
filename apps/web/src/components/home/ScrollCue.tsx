/** "Scroll for more" with a dotted arrow whose dots run downwards (reference hero, bottom right). */
export function ScrollCue({ className }: { className?: string }) {
  return (
    <p aria-hidden className={className}>
      <span className="eyebrow flex items-center gap-3 text-text">
        Scroll for more
        <svg viewBox="0 0 12 20" width="12" height="20" fill="currentColor" className="scroll-cue">
          {[2, 6, 10, 14].map((y) => (
            <circle key={y} cx="6" cy={y} r="1" />
          ))}
          <circle cx="2" cy="14" r="1" />
          <circle cx="10" cy="14" r="1" />
          <circle cx="4" cy="16.5" r="1" />
          <circle cx="8" cy="16.5" r="1" />
          <circle cx="6" cy="18.5" r="1" />
        </svg>
      </span>
    </p>
  );
}
