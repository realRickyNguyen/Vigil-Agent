# Vigil mascots: handoff

Last updated 26 Oct 2026 (Sydney). Read the project's `CLAUDE.md` and `docs/HANDOFF.md` first; this file covers only the video mascots.

## Where things stand

- **Decided (26 Oct):** the pixel-art capsule **Vigil** is the overall mascot and stands for the product. Each agent is a recoloured copy of the same capsule with its own prop. These are for the demo video and possibly the deck.
- **Committed** as `afdf0ef` on `feature/investigation-page` (local workspace `C:\Users\Sally\dev\genai_hackathon`). **Not pushed.** This file was written after that commit and is not committed yet.
- The same branch also has **uncommitted investigation-page work** (`README.md`, `app/`, `tests/`, `app/static/fonts/`, `.impeccable/` and the investigation-page row of `docs/HANDOFF.md`). It belongs to someone else's task. Don't commit it with mascot work; stage mascot files by path only.
- Nothing has been put into a video yet.

## Files

| Path | What it is |
|---|---|
| `make_mascots.py` | The only source. Draws every sprite from small text grids. Rebuild everything with `python -I docs/video/mascot/make_mascots.py` (needs Pillow, which is installed). |
| `sprites/*.png` | 43 transparent PNGs, each 640 × 576 (a 20 × 18 pixel canvas at 32×, nearest-neighbour). All share one canvas and position, so they can be swapped frame by frame. |
| `vigil-mascots.svg` | Overview sheet: Vigil's expressions and poses, the crew in three moods, a line-up. |
| `vigil-mascots.png` | The sheet at 2×, rendered with headless Edge (command below). |
| `app/static/mascots/*.png` | 1× copies (20 × 18) for the investigation page, written by the same script and served at `GET /mascots/<file>`. The page scales them by whole numbers with `image-rendering: pixelated`: a crew strip on the running view (the agent at work drawn larger and cycling its frames, the latest progress line under it), a small one beside each log line, one on each row of "How the agents got here", and Vigil looking concerned on a stopped run. The World Model and the orchestrator are shown as Vigil. |

Sprite names are `<character>-<state>.png`:
- characters: `vigil`, `clerk`, `analyst`, `reviewer`, `skeptic`
- states for every character: `neutral`, `blink`, `happy`, `alert`, `look`, `squint`, `concerned`, `bob` (body one pixel lower, for an idle bounce)
- Vigil only: `wave`, `point`, `cheer`

Render the sheet PNG after a change (PowerShell):

```powershell
Start-Process -FilePath "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList "--headless=new","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=2","--user-data-dir=$env:TEMP\edge-shot","--screenshot=C:\Users\Sally\dev\genai_hackathon\docs\video\mascot\vigil-mascots.png","--window-size=1400,1180","file:///C:/Users/Sally/dev/genai_hackathon/docs/video/mascot/vigil-mascots.svg" -Wait
```

## Design rules

- **Style:** big flat pixels with no outlines or shading. Eyes but no mouth, one-pixel nub arms, four short legs. The look takes inspiration from the Claude Code mascot's principles only. Don't copy its shape or its orange, and don't use Anthropic branding.
- **Body:** a dome-topped capsule. Top half, white seam, bottom half, navy legs. It is defined once in `BODY`; every character uses it.
- **Colours** come only from the Vigil logo (`docs/logo/`): navy `#14366B`, teal `#0F7C86`, orange `#B4441B`, slate `#5B6676`, plus white, eye black `#14161F` and lens blue `#CDE8EA`.

| Character | Top / bottom | Eyes | Prop | Role line |
|---|---|---|---|---|
| Vigil | teal / orange (as the logo capsule) | black | none | the product |
| Data Clerk | navy / teal | white | stack of cards | fetches the counts |
| Analyst | teal / navy | black, looking aside | magnifying glass | builds the case |
| Reviewer | orange / navy | black | tick | checks the numbers |
| Skeptic | slate / orange | white, one half shut | question mark | raises objections |

- In group shots Vigil is drawn larger than the crew. The sheet uses about 1.5× the crew size.
- **To add something:** an expression is a list of eye pixels in `EXPRESSIONS`. A pose is pixels to clear and add in `POSES`. A prop is canvas pixels in `PROPS`. A character is a row in `CAST`. Grid coordinates are (x, y) from the top left; the body grid sits at canvas offset (2, 3).

## What was tried and dropped

The earlier designs were deleted before the commit. They were never committed, so they're not in git.
- A 1950s-style pill bottle model sheet, built from the user's image prompt.
- A concept board with four designs: Lens, Night owl, Lantern and a first version of the crew.

## Suggested next steps

1. Short animated loops for the video, written as GIF or WebM from the same grids (Pillow can write GIFs). Examples: Vigil idle (neutral, blink, bob), Vigil waving, and each agent reacting.
2. A storyboard for the 1 to 4 minute video, in which the crew does what the system really does: the Data Clerk fetches the counts, the Analyst proposes, the Reviewer checks, the Skeptic objects, and the Analyst revises. Keep it honest. The mascots illustrate real steps shown in the real investigation page and traces. Never show made-up results.
3. Optional: put the sprites in the deck (title slide, agents slide).

## Watch-outs

- Deadline: submissions close **Tue 27 Oct 23:45 UTC (Wed 28 Oct 10:45 Sydney)**. Keep mascot work small.
- No Co-Authored-By trailers in commits (`CLAUDE.md`). Ask before pushing.
- Python runs with `-I`.
- Tone: Vigil is a drug-safety tool. Use the cheerful poses sparingly; the curious and concerned states fit most scenes.
