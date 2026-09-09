import { useId } from "react";

const SYMBOLS: Record<string, string> = {
  Supervisor:
    "M12 3v5M5 16v-4h14v4M12 12V8M9 2h6v6H9zM2 16h6v6H2zM9 16h6v6H9zM16 16h6v6h-6z",
  Settlement: "M3 7h17l-4-4M21 17H4l4 4M6 11v3M18 10v3",
  "Risk / Client": "M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6zM8 12l3 3 5-6",
  Knowledge:
    "M12 5v16M12 5C8 2 4 3 2 4v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-2-1-6-2-10 1",
  Developer: "M7 6l-5 6 5 6M17 6l5 6-5 6M14 3l-4 18",
  "Stock Loan":
    "M3 19h18M5 15V9h3v6M11 15V6h3v9M17 15V3h3v12M3 4h5l-2-2M8 4L6 6",
  Margin: "M12 3v17M5 21h14M4 7h16M6 7l-4 8h8L6 7M18 7l-4 8h8l-4-8",
  "Corporate Actions": "M4 5h16v16H4zM4 10h16M8 2v6M16 2v6M8 15l3 3 5-5",
  Cash: "M2 5h20v14H2zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M5 9v6M19 9v6",
};
const COLORS: Record<string, string> = {
  Supervisor: "#6c63ff",
  Settlement: "#3489ee",
  "Risk / Client": "#17a68a",
  Knowledge: "#aa6ce4",
  Developer: "#5a79ee",
  "Stock Loan": "#149fa7",
  Margin: "#ca942e",
  "Corporate Actions": "#d66b8e",
  Cash: "#299b70",
};
export default function AgentIllustration({ name }: { name: string }) {
  const id = useId();
  const color = COLORS[name] ?? "#6c63ff";
  return (
    <svg
      className="agent-illustration"
      viewBox="0 0 400 140"
      role="img"
      aria-label={`${name} capability illustration`}
    >
      <defs>
        <linearGradient id={id} x2="1" y2="1">
          <stop stopColor={color} stopOpacity=".15" />
          <stop offset="1" stopColor={color} stopOpacity=".02" />
        </linearGradient>
      </defs>
      <rect width="400" height="140" fill={`url(#${id})`} />
      <g stroke={color} fill="none" opacity=".18">
        <path d="M0 35h400M0 105h400M80 0v140M320 0v140" />
        <circle cx="200" cy="70" r="56" />
        <path d="M40 70h92M268 70h92" strokeDasharray="4 5" />
      </g>
      <g fill="white" stroke={color} strokeOpacity=".25">
        <rect x="36" y="49" width="50" height="42" rx="8" />
        <rect x="314" y="49" width="50" height="42" rx="8" />
        <rect x="158" y="28" width="84" height="84" rx="20" />
      </g>
      <g
        stroke={color}
        strokeWidth="1.7"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M48 61h26M48 69h18M48 77h22M327 70l7 7 16-16" />
        <g transform="translate(177 47) scale(1.9)">
          <path d={SYMBOLS[name]} />
        </g>
      </g>
      <circle cx="132" cy="70" r="3" fill={color} />
      <circle cx="268" cy="70" r="3" fill={color} />
    </svg>
  );
}
