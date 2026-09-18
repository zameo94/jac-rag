interface FlagProps {
  className?: string;
}

export function ItalyFlag({ className }: FlagProps) {
  return (
    <svg
      viewBox="0 0 3 2"
      className={className}
      role="img"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="1" height="2" fill="#009246" />
      <rect x="1" width="1" height="2" fill="#ffffff" />
      <rect x="2" width="1" height="2" fill="#ce2b37" />
    </svg>
  );
}

export function UnitedStatesFlag({ className }: FlagProps) {
  const stripeHeight = 30 / 13;
  return (
    <svg
      viewBox="0 0 60 30"
      className={className}
      role="img"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="60" height="30" fill="#ffffff" />
      {Array.from({ length: 7 }).map((_, index) => (
        <rect
          key={index}
          y={index * stripeHeight * 2}
          width="60"
          height={stripeHeight}
          fill="#b22234"
        />
      ))}
      <rect width="24" height={stripeHeight * 7} fill="#3c3b6e" />
    </svg>
  );
}
