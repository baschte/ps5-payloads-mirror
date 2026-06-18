interface IconProps {
  className?: string;
}

const base = "h-[1.15em] w-[1.15em]";

function Svg({
  className,
  children,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className ?? base}
    >
      {children}
    </svg>
  );
}

export function IconSync({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      <path d="M3 21v-5h5" />
    </Svg>
  );
}

export function IconPlus({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function IconTrash({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
      <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
      <path d="M10 11v6M14 11v6" />
    </Svg>
  );
}

export function IconBolt({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </Svg>
  );
}

export function IconExternal({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M14 4h6v6" />
      <path d="M20 4 10 14" />
      <path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
    </Svg>
  );
}

export function IconPlay({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M7 5v14l11-7-11-7Z" />
    </Svg>
  );
}

export function IconPencil({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />
    </Svg>
  );
}

export function IconCheck({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M20 6 9 17l-5-5" />
    </Svg>
  );
}

export function IconX({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M18 6 6 18M6 6l12 12" />
    </Svg>
  );
}

export function IconUpload({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 15V4M8 8l4-4 4 4" />
      <path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
    </Svg>
  );
}

export function IconSun({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Svg>
  );
}

export function IconMoon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </Svg>
  );
}

/** Friendly brand logo mark: two interlocking rounded shards = "mirror". */
export function Logo({ className }: IconProps) {
  return (
    <span
      className={
        className ??
        "grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-lift"
      }
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="h-6 w-6"
      >
        <path d="M12 3 5 7v5c0 4 3 6.5 7 9 4-2.5 7-5 7-9V7l-7-4Z" />
        <path d="M12 7v10" />
      </svg>
    </span>
  );
}
