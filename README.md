# Diablo 4 Nutty Sage: Build Picker & Helper

**BOB the Nutty Sage** is a community-minded idea for a friendly Diablo IV build and gear coach. This is a separate starter project; it does not replace or change the existing `build-pilot` auto-picker.

## The idea

Open a simple chat window that asks how the player likes to play, then offers up to three build options labeled **1 / 2 / 3**. The player chooses one and gets a clear skill plan with plain-language explanations of how to use the build. Later, the helper could compare armor stats and rolls against the build, explain tempering choices, and read guidance aloud with text-to-speech.

## Accessibility goals

Make choices easy to understand and navigate; support keyboard and pointer input; explain recommendations without assuming prior game knowledge; and invite feedback from disabled players and accessibility practitioners. These are goals, not a claim of formal accessibility certification.

## Scope and status

This repository is an early concept. The chat picker, build explanations, gear review, tempering coach, and text-to-speech are **not implemented yet**. The initial public direction is to recommend and explain, leaving the player in control rather than automating game input. A disclaimer cannot make unauthorized automation permitted; check Blizzard's current terms before connecting any tool to the game.

## Help wanted

Ideas and contributions are welcome, especially around accessible chat design, build-data sources, item-stat comparison, screen-reading/OCR, and plain-language explanations. Please open an issue to discuss an approach before building integrations that control the game.
