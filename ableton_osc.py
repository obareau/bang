"""BANG! Ableton OSC bridge — sync tempo + push patterns as Live clips.

Framework-agnostic port of web.py's `/ableton/sync_bpm` (web.py:3156-3181)
and `/ableton/send` (web.py:3285-3347). Talks to AbletonOSC
(https://github.com/ideoforms/AbletonOSC) running inside Ableton Live.
"""
from __future__ import annotations

import socket

from bang_engine import compile_dna, vel_map


def query_ableton_tempo(host: str, port: int, timeout: float = 0.8) -> float | None:
    """Ask AbletonOSC for the current Live set tempo. None if no response."""
    try:
        from pythonosc.osc_message_builder import OscMessageBuilder
        from pythonosc.osc_message import OscMessage
        msg = OscMessageBuilder(address="/live/song/get/tempo").build()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(msg.dgram, (host, port))
            data, _ = s.recvfrom(1024)
            return float(OscMessage(data).params[0])
    except Exception:
        return None


def send_pattern_to_ableton(
    voices: list[tuple[int, str, str]],
    p: dict,
    host: str = "127.0.0.1",
    port: int = 11000,
    track_offset: int = 0,
    slot: int = 0,
) -> tuple[int, str | None]:
    """Create a clip per voice in Ableton Live and fill it with the current
    pattern's notes via AbletonOSC. Returns (voices_sent, error_message).
    """
    if not voices or not p:
        return 0, "Aucun pattern généré."

    try:
        from pythonosc.udp_client import SimpleUDPClient
        client = SimpleUDPClient(host, port)

        client.send_message("/live/song/set/tempo", float(p["bpm"]))

        steps = p["steps"]
        clip_len_beats = steps / 4.0

        vf  = p.get("vel_floor", 0)
        vc  = p.get("vel_ceiling", 127)
        vcu = p.get("vel_curve", 1.0)

        sent = 0
        vi = 0
        for note, dna, vtype in voices:
            if vtype == "cc":
                continue
            track_id = track_offset + vi

            client.send_message("/live/clip_slot/create_clip", [track_id, slot, clip_len_beats])

            compiled = compile_dna(dna)
            dna_len = len(compiled)
            note_args = []
            for i in range(steps):
                row = compiled[i % dna_len]
                if row[0] <= 0:
                    continue
                vel = vel_map(int(row[1]), vf, vc, vcu)
                ratchet = max(1, int(row[3]))
                if ratchet > 1:
                    rd = 0.25 / ratchet
                    for r in range(ratchet):
                        note_args.extend([note, i / 4.0 + r * rd, rd * 0.85, vel, 0])
                else:
                    note_args.extend([note, i / 4.0, 0.225, vel, 0])

            if note_args:
                client.send_message("/live/clip/add_notes", [track_id, slot] + note_args)
            vi += 1
            sent += 1

        return sent, None
    except Exception as e:
        return 0, str(e)


if __name__ == "__main__":
    from bang_session import BangSession

    session = BangSession()
    session.generate(mode="morph", chaos=0.3, bpm=110, steps=16)

    tempo = query_ableton_tempo("127.0.0.1", 11000, timeout=0.3)
    print(f"Ableton tempo query (expect None if Live isn't running): {tempo}")

    sent, err = send_pattern_to_ableton(session.voices, session.last_p, host="127.0.0.1", port=11000)
    print(f"send_pattern_to_ableton -> sent={sent} err={err!r}")
    print("(err is expected here — no Ableton/AbletonOSC running in this sandbox)")
    print("\n✓ ableton_osc.py smoke test OK — functions callable, fail gracefully offline")
