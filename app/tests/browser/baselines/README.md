# Mockup visual baseline

`mockup-baseline.spec.ts` captures the unmodified root HTML mockup with synthetic fixture data at 320, 375, 768, 1024, and 1440 CSS pixels and in a 200% zoom/reflow case. Generated PNGs remain test evidence and contain no real candidate data.

Run `npm run test:browser -- --update-snapshots`. Review every diff; visual updates require an explicit preservation decision. The HTML source itself must not be rewritten by this test.
