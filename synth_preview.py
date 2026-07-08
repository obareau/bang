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

    Genuinely multitimbral: every one of the 16 MIDI channels gets its own
    GM program assigned up front, matching live_clock.py's `default_channel()`
    routing (channel 0=Bass, 1=Lead/Markov, 2-5=Keystep tracks, 6=Volca Kick,
    7=Volca FM, 8=MicroFreak, drum_channel=kit). That way drums, bass and
    leads all sound simultaneously with distinct timbres instead of every
    non-drum voice piling onto one generic "everything is bass" channel.
    """

    DRUM_KIT_PROGRAM = 24   # GM2 "Electronic" kit (falls back gracefully)

    # channel -> (bank, program). Channels not listed default to bank 0
    # program 0 (Acoustic Grand) as a harmless fallback.
    CHANNEL_PROGRAMS = {
        0: (0, 38),    # Bass — Synth Bass 1 (bl, and low "drum"-typed notes like Bass/A1)
        1: (0, 81),    # Lead/Markov — Lead 2 (sawtooth)
        2: (0, 80),    # KSP Lead — Lead 1 (square)
        3: (0, 38),    # KSP Bass — Synth Bass 1
        4: (0, 89),    # KSP Chord — Pad 2 (warm)
        5: (0, 108),   # KSP Arp — Kalimba
        6: (0, 87),    # Volca Kick — Lead 8 (bass+lead)
        7: (0, 82),    # Volca FM — Lead 3 (calliope)
        8: (0, 84),    # MicroFreak — Lead 5 (charang)
    }

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
            if ch == drum_channel:
                self.fs.program_select(ch, sfid, 128, self.DRUM_KIT_PROGRAM)
            else:
                bank, program = self.CHANNEL_PROGRAMS.get(ch, (0, 0))
                self.fs.program_select(ch, sfid, bank, program)

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
