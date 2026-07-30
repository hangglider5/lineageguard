# LineageGuard rough-cut video

This Remotion project builds the under-three-minute hackathon demo from real
LineageGuard UI footage, committed verification evidence, and a replaceable
English voice-over track.

The rough narration in `public/audio/narration-rough.wav` was synthesized with
HeyGen from `submission/demo-script.md`. It is a timing and editing aid, not a
requirement for the final submission; replace it with the entrant's recording
without changing the timeline.

## Capture the live read-only workflow

Start the local demo API from the repository root:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.demo_api
```

Then capture the actual browser interaction:

```bash
cd video
npm install
npm run capture:live
```

The capture is deliberately ignored by Git because it is reproducible and may
contain machine-specific timing. The committed video composition still fails at
render time if the expected capture is absent.

## Preview and render

```bash
cd video
npm run still
npm run studio
npm run render:rough
```

`render:rough` produces a faster 960×540 review copy. After the cut is approved,
`npm run render:final` produces the 1920×1080 master. Both are 170 seconds at
30 fps. The narration follows the seven sections in `submission/demo-script.md`;
the visual timeline consolidates them into six sequences.
