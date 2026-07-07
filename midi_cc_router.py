"""BANG! MIDI CC Router — route NTS-1 panel to MIDI output."""
import mido
from typing import Optional
from p_locks import PLockSequence, InterpolationMode


class MIDICCRouter:
    """Route CC values from NTS-1 panel to MIDI output."""

    def __init__(self, engine=None):
        self.engine = engine
        self.midi_output: Optional[mido.MidiFile] = None
        self.midi_port: Optional[str] = None
        self.channel = 1
        self.plock_seq: Optional[PLockSequence] = None

    def set_output_port(self, port_name: str):
        """Set MIDI output port."""
        try:
            if port_name == "— Virtual —":
                print(f"Virtual MIDI port selected")
            else:
                available = mido.get_output_names()
                if port_name in available:
                    self.midi_port = port_name
                    print(f"MIDI output: {port_name}")
                else:
                    print(f"Port not found: {port_name}")
        except Exception as e:
            print(f"Error setting MIDI port: {e}")

    def send_cc(self, cc: int, value: int, channel: int = None):
        """Send CC message to MIDI output."""
        if not self.midi_port:
            return

        try:
            ch = channel or self.channel
            msg = mido.Message("control_change", control=cc, value=value, channel=ch - 1)
            # In real app, would send via mido.open_output(self.midi_port).send(msg)
            print(f"CC {cc} = {value} (ch {ch})")
        except Exception as e:
            print(f"Error sending CC: {e}")

    def setup_nts1_plock_seq(self):
        """Initialize NTS-1 p-lock sequence."""
        self.plock_seq = PLockSequence("nts1")
        return self.plock_seq

    def render_pattern_with_plocks(self, pattern_length: int = 16) -> list:
        """Render full pattern with p-lock interpolation."""
        if not self.plock_seq:
            return []

        sequence = self.plock_seq.get_sequence(pattern_length)
        events = []

        for step in range(pattern_length):
            step_events = {}
            for cc_name, values in sequence.items():
                cc = self.plock_seq.tracks[cc_name].cc
                value = values[step]
                step_events[cc] = value
            events.append(step_events)

        return events

    def apply_nts1_slider(self, param: str, value: int):
        """Apply NTS-1 panel slider change (send CC + update p-lock for current step)."""
        if not self.plock_seq or param not in self.plock_seq.tracks:
            return

        track = self.plock_seq.tracks[param]
        self.send_cc(track.cc, value, self.channel)

    def set_plock_on_step(self, param: str, step: int, value: int):
        """Set p-lock on specific step."""
        if not self.plock_seq or param not in self.plock_seq.tracks:
            return

        self.plock_seq.tracks[param].set_plock(step, value)
        print(f"P-lock: {param} step {step} = {value}")

    def randomize_plock_track(self, param: str, density: float = 0.5, min_val: int = 20, max_val: int = 120):
        """Randomize p-locks for a single CC track."""
        if not self.plock_seq or param not in self.plock_seq.tracks:
            return

        import random
        track = self.plock_seq.tracks[param]
        track.p_locks.clear()

        for step in range(track.track_length if hasattr(track, 'track_length') else 16):
            if random.random() < density:
                value = random.randint(min_val, max_val)
                track.set_plock(step, value)

        print(f"Randomized {param}: {len(track.p_locks)} p-locks")

    def export_as_midi_file(self, filename: str, bpm: int = 120):
        """Export pattern as MIDI file with CC events."""
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Set tempo
        tempo = mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))
        track.append(tempo)

        # Render events
        if self.plock_seq:
            events = self.plock_seq.export_midi_events()
            time = 0
            for event_time, cc, value in events:
                # Convert beat to ticks
                delta = int((event_time - time) * mid.ticks_per_beat)
                msg = mido.Message("control_change", control=cc, value=value, channel=self.channel - 1, time=delta)
                track.append(msg)
                time = event_time

        # Save
        mid.save(filename)
        print(f"Exported to {filename}")


# Example usage
if __name__ == "__main__":
    router = MIDICCRouter()
    router.set_output_port("NTS-1")

    # Setup p-lock sequence
    seq = router.setup_nts1_plock_seq()
    seq.set_interpolation(InterpolationMode.LINEAR)

    # Set some p-locks
    router.set_plock_on_step("cutoff", 0, 30)
    router.set_plock_on_step("cutoff", 8, 120)
    router.set_plock_on_step("reso", 4, 80)

    # Render pattern
    pattern = router.render_pattern_with_plocks()
    print(f"\nPattern rendered: {len(pattern)} steps")
    for i, step_events in enumerate(pattern):
        print(f"  Step {i}: {step_events}")
