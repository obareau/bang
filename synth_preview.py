"""BANG! Synth Preview — built-in software synth so patterns are audible
without external MIDI hardware or a DAW.

Uses FluidSynth (via the `pyfluidsynth` ctypes binding, against the system
`libfluidsynth3` + a GM soundfont) and exposes a tiny object with the same
`.send(mido.Message)` / `.close()` shape as a real `mido` output port, so
`LiveClock` (live_clock.py) can target it transparently — zero duplication
of the real-time clock/modulation logic.
"""
from __future__ import annotations

import glob
import os


def find_default_soundfont() -> str | None:
    """Look for a General MIDI soundfont in common system locations."""
    candidates = [
        "/etc/alternatives/default-GM.sf2",
        "/usr/share/sounds/sf2/TimGM6mb.sf2",
        "/usr/share/sounds/sf2/FluidR3_GM.sf2",
        "/usr/share/soundfonts/default.sf2",
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.realpath(c)
    for pattern in ("/usr/share/sounds/sf2/*.sf2", "/usr/share/soundfonts/*.sf2"):
        found = glob.glob(pattern)
        if found:
            return found[0]
    return None


class FluidSynthPort:
    """Mido-output-shaped adapter around a FluidSynth instance.

    Drum channel (default 9, 0-based = MIDI ch10) gets the GM percussion
    bank (128) so drum-machine voices (vd*/vk/drum on ch10) sound like a kit
    instead of a pitched instrument; every other channel gets bank 0 program 0
    (Acoustic Grand) as a reasonable default preview voice.
    """

    def __init__(self, soundfont_path: str | None = None, drum_channel: int = 9):
        import fluidsynth  # deferred import — optional dependency

        sf_path = soundfont_path or find_default_soundfont()
        if not sf_path:
            raise RuntimeError(
                "No GM soundfont found. Install one (e.g. `sudo apt install fluid-soundfont-gm`) "
                "or pass an explicit soundfont_path."
            )

        self.fs = fluidsynth.Synth()
        self.fs.start()  # auto-selects an audio driver (pulseaudio/alsa/...)
        sfid = self.fs.sfload(sf_path)
        for ch in range(16):
            bank = 128 if ch == drum_channel else 0
            self.fs.program_select(ch, sfid, bank, 0)

    def send(self, msg) -> None:
        if msg.type == "note_on":
            if msg.velocity == 0:
                self.fs.noteoff(msg.channel, msg.note)
            else:
                self.fs.noteon(msg.channel, msg.note, msg.velocity)
        elif msg.type == "note_off":
            self.fs.noteoff(msg.channel, msg.note)
        elif msg.type == "control_change":
            self.fs.cc(msg.channel, msg.control, msg.value)

    def close(self) -> None:
        self.fs.delete()


if __name__ == "__main__":
    import time
    import mido

    sf = find_default_soundfont()
    print(f"Soundfont: {sf}")
    if not sf:
        print("No soundfont found — cannot test.")
    else:
        port = FluidSynthPort(sf)
        for note in (60, 64, 67, 72):
            port.send(mido.Message("note_on", note=note, velocity=100, channel=0))
            time.sleep(0.25)
            port.send(mido.Message("note_off", note=note, channel=0))
        port.close()
        print("✓ synth_preview.py smoke test OK (should have heard an arpeggio)")
