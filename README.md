# Diablo 4 Nutty Sage: Build Picker & Helper

> **An accessibility aid for Diablo IV.** BOB shows you *where* to click on the skill tree and explains your build in
> plain words: numbered boxes, big outlines, sound cues, short tips. It never clicks for you; you stay in control.
> Built for players who find the skill tree hard to read, hard to navigate or overwhelming.

**BOB the Nutty Sage** is a community-minded Diablo IV build helper. This is a separate project; it does not replace
or change the existing `build-pilot` auto-picker.

## About the Nut

Hey, I'm **The Nut**—a playful gamer and beginner coder who's been tinkering with code for about three years. I use
AI as a coding partner and learn as I build. I'm working on tools to help people with different needs pick skills,
understand builds, and enjoy games. My Arc Raiders skill-picker idea is still in development and isn't ready yet.

## What works today

The `overlay/` folder contains the early Diablo IV player-guided skill-tree overlay. It reads the screen and mouse
position, then highlights the next skill node; **you make the clicks**. A separate self/auto-picker exists, but it
is not included in this repository.

This is a working but experimental prototype—not a finished app. It can be slow, and its ring can drift away from
the skill icon, making it unclear where to click. Those are the specific problems we're asking contributors to
help solve. The game data is downloaded from Maxroll when needed; large data files, local logs, screenshots, and
private handoff notes are not included.

## New: Diablo BOB - Human-Proof Guidance (October 10)

`overlay/bob.py` is a new way to follow a build, and it fixes the drifting-ring problem by letting **you** line
things up instead of guessing:

1. Open the full skill tree, zoom all the way out, and hover any big skill square so BOB knows your class.
2. BOB draws a **ghost outline** of one tree section, with the section number in the middle. A circle (or an arrow,
   if it's off screen) shows where that section is right now.
3. Drag the tree until the real squares sit in the outline. It turns **green**; let go of the mouse, and after a
   second it locks with a chime.
4. **Every node to pick in that section gets a box at once**, each with a line to how many times to click it
   (`x1`, `x9`...). Click them; each box counts down as you click and turns into a green check.
5. Section done, chime, next section. At the end you get a short how-to-play note.

It never moves the mouse or presses keys - it only watches where you click. F7 = "it's lined up" / "this section
is done" if it ever gets stuck, F12 = quit. First full run on a live Warlock placed every point correctly.
Known issues: boxes can sit slightly off-centre on some nodes, and resuming after a restart relies on reading
"points spent" from the screen, so a full refund is the most reliable start.

```powershell
cd overlay
python bob.py
```

### Update (Oct 10, night): a trained detector keeps the boxes on the nodes

BOB now ships with a small trained detector (`overlay/models/d4ui.pt`, YOLO). It finds the big skill squares and section
diamonds in about 20-50 ms, and the rigid tree map measures every small node from them (position and scale), so the
boxes stay centred and follow the tree when you drag it, without jitter. Other fixes from live testing: clicks are
counted where they land and never un-count, the lineup only locks after you let go of the mouse, sections sit lower so
tooltips don't cover them, and a section only finishes when the in-game point counter agrees (otherwise BOB says how
many points didn't go in).

The detector is optional: `pip install ultralytics` to use it; without it BOB falls back to its older square finder.
Tip: grab the tree by empty space, and move the mouse off the skills after letting go (tooltips hide the nodes).
`python bob.py --collect` saves labeled screenshots for training a better detector (off unless you ask for it).

## Roadmap (not built yet)

Next up: pointing out which skill goes in which action-bar slot.

Open a simple chat window that asks how the player likes to play, then offers up to three build options labeled
**1 / 2 / 3**. The player chooses one and gets a clear skill plan with plain-language explanations of how to use
the build. Later, the helper could compare armor stats and rolls against the build, explain tempering choices, and
read guidance aloud with text-to-speech.

## Accessibility goals

Make choices easy to understand and navigate; support keyboard and pointer input; explain recommendations without
assuming prior game knowledge; and invite feedback from disabled players and accessibility practitioners. These
are goals, not a claim of formal accessibility certification.

The build-choice chat, gameplay coaching, gear-roll review, tempering guidance, and text-to-speech are ideas for
future versions; they are not included in the current prototype. The overlay is player-guided and does not send
game clicks or key presses. A disclaimer cannot make unauthorized automation permitted; check Blizzard's current
terms before connecting any tool to the game.

## Help wanted

Ideas and contributions are welcome, especially around making the overlay faster, keeping the marker centered on
the correct node, and recovering cleanly when it loses track. Accessibility feedback, build-data sources,
screen-reading/OCR, and plain-language explanations are welcome too. Please open an issue before building any
integration that controls the game.
