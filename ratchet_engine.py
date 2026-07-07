"""BANG! Ratchet Engine — step repeat with interpolation."""
from typing import List, Tuple


class RatchetTrack:
    """Single track with ratchet/step-repeat configuration."""

    def __init__(self):
        self.ratchets: dict = {}  # {step: repeat_count}
        self.decay: dict = {}     # {step: decay_factor (0-1)}
        self.variation: dict = {} # {step: markov_variation (0-1)}

    def set_ratchet(self, step: int, count: int, decay: float = 1.0, variation: float = 0.0):
        """Set ratchet on a step (1-8 repeats)."""
        self.ratchets[step] = max(1, min(8, count))
        self.decay[step] = max(0.0, min(1.0, decay))
        self.variation[step] = max(0.0, min(1.0, variation))

    def remove_ratchet(self, step: int):
        """Remove ratchet from a step."""
        self.ratchets.pop(step, None)
        self.decay.pop(step, None)
        self.variation.pop(step, None)

    def expand_sequence(self, sequence_length: int = 16) -> List[Tuple[float, int]]:
        """Expand sequence with ratchets (returns list of (step_pos, note))."""
        expanded = []

        for step in range(sequence_length):
            if step in self.ratchets:
                count = self.ratchets[step]
                decay = self.decay.get(step, 1.0)
                variation = self.variation.get(step, 0.0)

                # Generate ratcheted notes
                for i in range(count):
                    # Sub-step position (0-1 within the step)
                    sub_pos = i / count
                    # Decay amplitude
                    velocity_mul = decay ** (i / max(1, count - 1))
                    # Add slight variation for naturalness
                    if variation > 0 and i > 0:
                        sub_pos += (variation * 0.1) * (i % 2 * 2 - 1)

                    expanded.append((step + sub_pos, velocity_mul))
            else:
                # Normal note
                expanded.append((step, 1.0))

        return expanded


class RatchetSequence:
    """Complete ratchet sequence for multi-voice pattern."""

    def __init__(self, num_voices: int = 6):
        self.tracks = {i: RatchetTrack() for i in range(num_voices)}
        self.pattern_length = 16

    def set_voice_ratchet(self, voice: int, step: int, count: int, decay: float = 1.0, variation: float = 0.0):
        """Set ratchet for a specific voice/step."""
        if voice in self.tracks:
            self.tracks[voice].set_ratchet(step, count, decay, variation)

    def expand_all(self) -> dict:
        """Expand all voices with ratchets."""
        result = {}
        for voice, track in self.tracks.items():
            result[voice] = track.expand_sequence(self.pattern_length)
        return result

    def clear_all_ratchets(self):
        """Clear all ratchets."""
        for track in self.tracks.values():
            track.ratchets.clear()
            track.decay.clear()
            track.variation.clear()


# Example usage
if __name__ == "__main__":
    seq = RatchetSequence(2)

    # Voice 0: ratchet on steps 2, 6 (stutter pattern)
    seq.set_voice_ratchet(0, 2, 4, decay=0.8, variation=0.3)  # 4 hits with decay
    seq.set_voice_ratchet(0, 6, 2, decay=1.0, variation=0.0)  # 2 hits clean

    # Voice 1: normal sequence
    seq.set_voice_ratchet(1, 0, 1)
    seq.set_voice_ratchet(1, 4, 3, decay=0.9)
    seq.set_voice_ratchet(1, 8, 1)

    expanded = seq.expand_all()

    for voice, notes in expanded.items():
        print(f"\nVoice {voice}:")
        for step_pos, velocity in notes:
            print(f"  Step {step_pos:.2f}: velocity {velocity:.2f}")
