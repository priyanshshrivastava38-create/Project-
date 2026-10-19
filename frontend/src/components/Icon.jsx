/** Inline SVG icon set (stroke icons, 24x24 viewBox). */
const PATHS = {
  dashboard: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
  assistant: 'M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4L12 3zM19 14l.9 2.1 2.1.9-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14z',
  customers: 'M16 11a4 4 0 1 0-8 0M3 21v-1a6 6 0 0 1 6-6h6a6 6 0 0 1 6 6v1M12 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8z',
  orders: 'M9 3h6l1 2h3v16H5V5h3l1-2zM9 11h6M9 15h6',
  inventory: 'M3 7l9-4 9 4-9 4-9-4zm0 0v10l9 4 9-4V7M12 11v10',
  production: 'M3 21V10l6 4V10l6 4V6l6 4v11H3zM7 17h2M12 17h2M17 17h2',
  quality: 'M12 3l7 3v6c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6l7-3zm-3 9l2 2 4-4',
  deliveries: 'M3 6h11v10H3zM14 9h4l3 3v4h-7M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm10 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  suppliers: 'M3 21V9l9-6 9 6v12M9 21v-6h6v6M3 21h18',
  documents: 'M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6',
  reports: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  users: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a6 6 0 0 1 6-6h2a6 6 0 0 1 6 6v1M17 3.5a4 4 0 0 1 0 7M22 21v-1a6 6 0 0 0-4-5.6',
  audit: 'M12 8v4l3 2M3.05 11a9 9 0 1 1 .5 4M3 4v5h5',
  menu: 'M3 6h18M3 12h18M3 18h18',
  close: 'M6 6l12 12M18 6L6 18',
  plus: 'M12 5v14M5 12h14',
  search: 'M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm10 17l-5-5',
  logout: 'M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11',
  chevronLeft: 'M15 6l-6 6 6 6',
  chevronRight: 'M9 6l6 6-6 6',
  chevronDown: 'M6 9l6 6 6-6',
  sortAsc: 'M8 15l4-4 4 4',
  sortDesc: 'M8 9l4 4 4-4',
  sort: 'M8 10l4-4 4 4M8 14l4 4 4-4',
  check: 'M5 12l5 5 9-10',
  alert: 'M12 3l10 18H2L12 3zm0 7v5m0 3v.01',
  info: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm0 8v5m0-8v.01',
  download: 'M12 4v11m-5-5l5 5 5-5M4 20h16',
  upload: 'M12 20V9m-5 5l5-5 5 5M4 4h16',
  refresh: 'M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7',
  edit: 'M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4',
  send: 'M4 12l16-8-6 16-2-6-8-2z',
  box: 'M3 7l9-4 9 4v10l-9 4-9-4V7z',
  clock: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm0 4v5l3 2',
  board: 'M4 4h4v16H4zM10 4h4v10h-4zM16 4h4v13h-4z',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  external: 'M14 4h6v6M20 4l-9 9M18 14v6H4V6h6',
  truck: 'M3 6h11v10H3zM14 9h4l3 3v4h-7',
};

export default function Icon({ name, size = 18, className = '', title, strokeWidth = 1.8 }) {
  const d = PATHS[name] || PATHS.info;
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      <path d={d} />
    </svg>
  );
}
