# FM3 screenshot manifest

All screenshots use synthetic/public data. Original reference SHA-256:
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.
Full-page heights may exceed viewport height. Zoom captures use CSS zoom 200%.

| Viewport / zoom | FM1 reference filename | React fixture golden | Live Django golden | Minimal legacy jobs capture |
|---|---|---|---|---|
| 1440×1000 / 100% | mockup-chooser-1440x1000-1x.png | chooser-1440-1x-chromium.png | chooser-live-1440-1x-chromium.png | jobs-live-1440-1x.png |
| 1024×768 / 100% | mockup-chooser-1024x768-1x.png | chooser-1024-1x-chromium.png | chooser-live-1024-1x-chromium.png | jobs-live-1024-1x.png |
| 390×844 / 100% | mockup-chooser-390x844-1x.png | chooser-390-1x-chromium.png | chooser-live-390-1x-chromium.png | jobs-live-390-1x.png |
| 320×844 / 100% | mockup-chooser-320x844-1x.png | chooser-320-1x-chromium.png | chooser-live-320-1x-chromium.png | jobs-live-320-1x.png |
| 1440×1000 / 200% | mockup-chooser-1440x1000-2x.png | chooser-1440-2x-chromium.png | chooser-live-1440-2x-chromium.png | jobs-live-1440-2x.png |

Directories relative to repository root:

- Reference: `docs/evidence/frontend-migration/fm1-baselines/` (unchanged).
- Fixture goldens: `app/tests/browser/fm3-chooser.spec.ts-snapshots/`.
- Live goldens: `app/tests/browser/fm3-live.spec.ts-snapshots/`.
- Jobs captures: this directory; empty published list at capture time. These are
  evidence captures, not assertions against changing backend records.
- Additional error/loading golden: `chooser-error-loading-chromium.png` in the
  fixture-golden directory, 1280×720.

Fixture/live chooser goldens were compared again without snapshot updates in the
complete browser suite. Visual differences are explained in [FM3 evidence](../fm3.md).
