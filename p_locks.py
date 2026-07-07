"""BANG! P-lock System — parameter locks with interpolation."""
import math
from typing import Dict, List, Tuple
from enum import Enum


class InterpolationMode(Enum):
    """P-lock interpolation modes."""
    OFF = "off"          # No interpolation (step value only)
    LINEAR = "linear"    # Linear ramp between steps
    COSINE = "cosine"    # Ease-in/out cosine curve


class PLockTrack:
    """Single CC track with p-locks and interpolation."""

    def __init__(self, cc: int, name: str, min_val=0, max_val=127):
        self.cc = cc
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.p_locks: Dict[int, int] = {}  # {step: value}
        self.interpolation = InterpolationMode.OFF

    def set_plock(self, step: int, value: int):
        """Set p-lock on a step."""
        self.p_locks[step] = max(self.min_val, min(self.max_val, value))

    def remove_plock(self, step: int):
        """Remove p-lock from a step."""
        if step in self.p_locks:
            del self.p_locks[step]

    def get_value(self, step: float) -> int:
        """Get interpolated value at fractional step."""
        if not self.p_locks:
            return 64  # Default mid-value

        step_int = int(step)
        frac = step - step_int

        # Find surrounding p-locks
        before = None
        after = None

        for locked_step in sorted(self.p_locks.keys()):
            if locked_step <= step_int:
                before = (locked_step, self.p_locks[locked_step])
            if locked_step > step_int and after is None:
                after = (locked_step, self.p_locks[locked_step])

        # No interpolation: return exact step value
        if self.interpolation == InterpolationMode.OFF:
            if step_int in self.p_locks:
                return self.p_locks[step_int]
            elif before:
                return before[1]
            elif after:
                return after[1]
            else:
                return 64

        # Linear interpolation
        if self.interpolation == InterpolationMode.LINEAR:
            if before and after:
                v_before = before[1]
                v_after = after[1]
                step_distance = after[0] - before[0]
                blend = (step - before[0]) / step_distance
                return int(v_before + (v_after - v_before) * blend)
            elif before:
                return before[1]
            elif after:
                return after[1]

        # Cosine interpolation (ease-in/out)
        if self.interpolation == InterpolationMode.COSINE:
            if before and after:
                v_before = before[1]
                v_after = after[1]
                step_distance = after[0] - before[0]
                blend = (step - before[0]) / step_distance
                # Cosine ease-in/out
                ease = (1 - math.cos(blend * math.pi)) / 2
                return int(v_before + (v_after - v_before) * ease)
            elif before:
                return before[1]
            elif after:
                return after[1]

        return 64


class PLockSequence:
    """Complete p-lock sequence for a voice."""

    # NTS-1 default p-lock profile
    NTS1_PROFILE = {
        "cutoff": (43, "Cutoff", 0, 127),
        "oscshp": (53, "OscShp", 0, 127),
        "oscalt": (54, "OscAlt", 0, 127),
        "lfoint": (25, "LFOInt", 0, 127),
        "reso": (44, "Reso", 0, 127),
        "revmix": (38, "RevMix", 0, 127),
    }

    def __init__(self, profile: str = "nts1"):
        self.profile = profile
        self.tracks: Dict[str, PLockTrack] = {}
        self.pattern_length = 16  # Steps per pattern

        # Initialize tracks from profile
        if profile == "nts1":
            for name, (cc, label, min_v, max_v) in self.NTS1_PROFILE.items():
                self.tracks[name] = PLockTrack(cc, label, min_v, max_v)

    def set_interpolation(self, mode: InterpolationMode):
        """Set interpolation mode for all tracks."""
        for track in self.tracks.values():
            track.interpolation = mode

    def randomize_plocks(self, density: float = 0.5, min_val: int = 0, max_val: int = 127):
        """Randomly generate p-locks (density 0-1, min/max bounds)."""
        import random

        self.clear_plocks()

        for track in self.tracks.values():
            for step in range(self.pattern_length):
                if random.random() < density:
                    value = random.randint(min_val, max_val)
                    track.set_plock(step, value)

    def clear_plocks(self):
        """Clear all p-locks."""
        for track in self.tracks.values():
            track.p_locks.clear()

    def get_sequence(self, step_count: int = 16) -> Dict[str, List[int]]:
        """Generate full CC sequence with interpolation."""
        sequence = {}

        for name, track in self.tracks.items():
            values = []
            for step in range(step_count):
                values.append(track.get_value(step))
            sequence[name] = values

        return sequence

    def export_midi_events(self) -> List[Tuple[float, int, int]]:
        """Export as MIDI CC events (time_in_beats, cc, value)."""
        events = []

        for step in range(self.pattern_length):
            for name, track in self.tracks.items():
                if step in track.p_locks:
                    value = track.p_locks[step]
                    events.append((step, track.cc, value))

        return sorted(events)


# Example usage
if __name__ == "__main__":
    # Create NTS-1 sequence
    seq = PLockSequence("nts1")

    # Set some p-locks
    seq.tracks["cutoff"].set_plock(0, 30)
    seq.tracks["cutoff"].set_plock(8, 120)
    seq.tracks["reso"].set_plock(4, 80)

    # Test interpolation modes
    for mode in [InterpolationMode.OFF, InterpolationMode.LINEAR, InterpolationMode.COSINE]:
        seq.set_interpolation(mode)
        print(f"\n{mode.value.upper()} interpolation:")
        values = seq.get_sequence()
        print(f"  Cutoff: {values['cutoff']}")
        print(f"  Reso:   {values['reso']}")
