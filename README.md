# Diablo 4 Nutty Sage: Build Picker & Helper

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

## Roadmap (not built yet)

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
