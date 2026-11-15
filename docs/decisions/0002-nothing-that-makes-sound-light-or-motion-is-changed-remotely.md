# 2. Nothing that makes sound, light or motion is changed remotely

- **Date:** 2026-10 (first kit); changed 2026-11-15
- **Status:** accepted
- **Rule:** Settings that make sound, light or motion change by hand only, one harmless change at a time; the one
  picture for Playback waits for the owner's typed word.

## Context

A run once woke people at night. Beeps, audio signals, volume, the AF illuminator, lamps, flash and video light, lens motors (Pre-AF, Eye-Start AF), the shutter curtain and SteadyShot all act on the world around the camera.

## Decision

They are changed by hand only. The owner may approve one change at a time when it is harmless (Video Light Setting with no light attached and nothing shot, 2026-11-02).

The kit releases the shutter once, `kit/tools/take_picture.py`, so the Playback rows have a picture to show: in a stills
mode, on the shooting screen, never where Drive Mode reads other than Single Shooting, interval shooting or Pre-Capture
on or the flash on, after the owner has typed their word at their own terminal to a question saying what will sound,
move or light and what the kit could not read; the answer is kept dated in the camera's reviewed scope, and the picture
stays on the card.

Before 2026-11-15 the kit never released the shutter.

## Consequences

Their proofs come from the closed watcher (the owner changes the setting, the kit downloads) or wait for the owner.
