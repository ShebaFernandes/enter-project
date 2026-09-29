# Mockup accessibility inventory

This is a static baseline review, not a WCAG conformance claim.

## Present behavior

- Most interactive controls use native buttons, inputs, selects, and textareas.
- Key icon-only buttons and dynamic timeline graphics include accessible names.
- Speech and sign-in errors expose polite live regions.
- Candidate/profile overlays declare dialog semantics and `aria-modal`.
- Side-panel toggles expose expanded/controlled state; sidebar regions have labels.
- Visible focus styling and reduced-motion behavior require production verification at every breakpoint.

## Known gaps to resolve in implementation

- Dynamically opened dialogs do not consistently demonstrate focus placement, focus trapping, return focus, or Escape behavior.
- Screen switching is display-based and does not establish routed page titles, landmark focus, or history semantics.
- Some visible text is not programmatically associated with form controls; grouped choices rely partly on container labels rather than fieldsets/legends.
- Dynamic validation does not consistently provide an error summary or bind each error with `aria-describedby`.
- Status, filter, chip, and tab interactions need keyboard and selected-state verification.
- Color contrast, target size, reflow at 320px, and 200% zoom require measured evidence.
- Uploaded-file and parsing progress states need explicit status semantics and non-visual instructions.
- Speech must remain optional, announce all states, and never be the only route.

## Manual baseline procedure

Test the screen order with keyboard only; open and close every overlay; inspect the accessibility tree for names, roles, values, and states; exercise errors; verify live announcements; test reduced motion; and repeat at 320, 375, 768, 1024, and 1440 CSS pixels plus 200% zoom. Record browser/version and evidence without real candidate data.
