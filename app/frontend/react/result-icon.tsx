import type { ReactNode } from "react";
const paths: Record<string, ReactNode> = {
  mail: (
    <>
      <rect width="20" height="16" x="2" y="4" rx="2"></rect>
      <path d="m22 7-10 6L2 7"></path>
    </>
  ),
  whatsapp: (
    <>
      <path d="M3 21l1.7-4.8A8 8 0 1 1 8 19.3L3 21Z"></path>
      <path d="M9.3 8.7c.3-.5.6-.5.9-.3l1.1 1.2c.2.2.2.5 0 .8l-.4.5c.6 1.2 1.5 2.1 2.7 2.7l.5-.4c.3-.2.6-.2.8 0l1.2 1.1c.2.3.2.6-.3.9-.6.4-1.4.6-2.1.3-2.6-.9-4.4-2.7-5.3-5.3-.3-.7-.1-1.5.3-2.1Z"></path>
    </>
  ),
  linkedin: (
    <>
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6Z"></path>
      <rect width="4" height="12" x="2" y="9"></rect>
      <circle cx="4" cy="4" r="2"></circle>
    </>
  ),
  github: (
    <>
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-1.5 6-6A4.6 4.6 0 0 0 18.7 5c.2-1 .2-2.2-.3-3.1 0 0-1-.3-3.3 1.2a11.4 11.4 0 0 0-6 0C6.8 1.6 5.8 1.9 5.8 1.9c-.5.9-.5 2.1-.3 3.1A4.6 4.6 0 0 0 4.2 8.5c0 4.5 3 6 6 6A4.8 4.8 0 0 0 9 18v4"></path>
      <path d="M9 18c-4.5 2-5-2-7-2"></path>
    </>
  ),
  share: (
    <>
      <circle cx="18" cy="5" r="3"></circle>
      <circle cx="6" cy="12" r="3"></circle>
      <circle cx="18" cy="19" r="3"></circle>
      <path d="m8.6 13.5 6.8 4"></path>
      <path d="m15.4 6.5-6.8 4"></path>
    </>
  ),
  location: (
    <>
      <path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"></path>
      <circle cx="12" cy="10" r="3"></circle>
    </>
  ),
  briefcase: (
    <>
      <path d="M10 6V5a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1"></path>
      <rect width="20" height="14" x="2" y="6" rx="2"></rect>
      <path d="M2 12h20"></path>
    </>
  ),
  calendar: (
    <>
      <path d="M8 2v4"></path>
      <path d="M16 2v4"></path>
      <rect width="18" height="18" x="3" y="4" rx="2"></rect>
      <path d="M3 10h18"></path>
    </>
  ),
  rupee: (
    <>
      <path d="M6 3h12"></path>
      <path d="M6 8h12"></path>
      <path d="M6 13h7a5 5 0 0 0 0-10"></path>
      <path d="m6 13 8 8"></path>
    </>
  ),
  filters: (
    <>
      <path d="M4 7h16" />
      <path d="M4 17h16" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 7v5h-5" />
      <path d="M20 12a8 8 0 1 1-2-6" />
    </>
  ),
};
export function ResultIcon({ name }: { name: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[name]}
    </svg>
  );
}
