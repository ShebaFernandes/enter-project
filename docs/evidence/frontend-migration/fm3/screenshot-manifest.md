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

## Independent publication remediation — 2026-10-01

New operational evidence only, not replacements for mockup/chooser goldens. These
captures show real synthetic backend data on the unchanged legacy organization page.
The public UUID varies across isolated fixture runs. Publication time is visibly
server-assigned at confirmation; no optional company/skills/experience is fabricated.

| Viewport / zoom | Capture under `publication/` | SHA-256 |
|---|---|---|
| 1440×1000 / 100% | publication-1440-1x.png | `65998d1a2b2b87d0abfe20c20aa5a338c2530135794e09308d41703e29bd6f19` |
| 1024×768 / 100% | publication-1024-1x.png | `35e23ec43e6303496343f727c7921e108da64a013d2bc483c4ab684043150991` |
| 390×844 / 100% | publication-390-1x.png | `e6de559ad8ec0a850e1ab980e811b9410d5ee0792851f89efd8e0dfccca59b64` |
| 320×844 / 100% | publication-320-1x.png | `a3a91cd5c74dbeb1550c4525437c940fd06bed6c2c6e847036d8fdad05f72f00` |
| 1440×1000 / 200% CSS zoom | publication-1440-2x.png | `bb19a4415ac7e301366795e93d488e4d8bd1a0c1ba7a948e2513805bfd2638cb` |

Playwright source: `app/tests/browser/recruiter/opening-publication.spec.ts`.
Final raw outputs: `app/test-results/fm3-remediation-auth-4/`. Existing chooser
goldens passed without updates. Refreshed public-directory evidence is separately
under `app/test-results/fm3-remediation-live/`; 130 authenticated/mockup baseline
recaptures and manifest are under `app/test-results/fm3-remediation-baselines/`.
Old screenshots and original mockup remain unchanged. Intentional difference is
the approved legacy publication security controls, not an organization redesign.
