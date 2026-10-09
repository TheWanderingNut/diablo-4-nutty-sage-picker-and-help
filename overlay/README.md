# Player-Guided Overlay Prototype

This early Windows prototype reads the Diablo IV skill tree, watches the player's pointer position, and draws a
ring and guidance around the next planned skill node. It does not move the pointer, click, or send game key presses.

## Run

From this folder, install the packages in `requirements.txt`, then run:

```powershell
python guide.py
python guide.py <Maxroll guide URL>
```

Open the full skill tree, zoom all the way out, and follow the on-screen prompts. F8 confirms a pending step if the
point counter does not register; F9 confirms the tree is fully zoomed out; F12 closes the guide. Use Windowed or
Borderless Windowed mode so the overlay can appear above the game.

On first run, the tool downloads Maxroll game data into `data/`. It also reads the game window and pointer position
locally. The screen reader is OCR-based; no AI model is required.

## Known issues

The prototype can be slow, and the highlight can drift from the actual skill icon. Do not assume a step succeeded
unless the in-game point counter changes. Help improving calibration, marker tracking, and recovery after a missed
click is welcome.

This is experimental software. Back up or note your skill setup before testing and verify every allocation yourself.
