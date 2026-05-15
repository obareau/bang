#!/usr/bin/env python3
"""
BANG CLI — Séquenceur algorithmique Dark Umbrae
"""
import argparse
import sys
import time

from bang_engine import (
    BangEngine,
    MarkovChain,
    dark_chain,
    fetch_weather,
    morph_dna,
    mutate_dna,
    random_dna,
    weather_cc_breakpoints,
    weather_dna,
)


# ---------------------------------------------------------------------------
# MIDI Controller (Zoom R8 / générique)
# ---------------------------------------------------------------------------

def _rtmidi():
    try:
        import rtmidi
        return rtmidi
    except ImportError:
        return None


def list_midi_ports() -> list[str]:
    rt = _rtmidi()
    if not rt:
        return []
    m = rt.MidiIn()
    ports = m.get_ports()
    m.close_port()
    return ports


class MidiController:
    """
    Écoute un port MIDI et capture les CC pour paramétrer la génération.

    Mapping par défaut :
      CC 1  → chaos    (0.0–1.0)
      CC 7  → bpm      (60–160, normalisé)
      CC 11 → gravity  (gravité Markov, 0.0–1.0)
      CC 74 → cc_depth (amplitude automation filtre, 0.0–1.0)

    Sur le Zoom R8, les touches transport envoient des CC configurables.
    Utilisez --list-ports pour trouver le nom exact du port.
    """

    CC_MAP = {1: "chaos", 7: "bpm", 11: "gravity", 74: "cc_depth"}

    def __init__(self, port_hint: str = "Zoom"):
        rt = _rtmidi()
        if not rt:
            raise RuntimeError(
                "python-rtmidi non disponible. "
                "Installez-le avec : uv add python-rtmidi"
            )
        self._midi = rt.MidiIn()
        ports = self._midi.get_ports()
        idx = next((i for i, p in enumerate(ports) if port_hint.lower() in p.lower()), None)
        if idx is None:
            raise RuntimeError(
                f"Port MIDI '{port_hint}' introuvable.\n"
                f"Ports disponibles : {ports or ['(aucun)']}\n"
                "Utilisez --list-ports pour voir les options."
            )
        self._midi.open_port(idx)
        print(f"Contrôleur connecté : {ports[idx]}")

    def capture(self, duration: float = 5.0) -> dict:
        """
        Écoute pendant `duration` secondes.
        Retourne les paramètres capturés (seuls les CC reçus sont présents).
        """
        print(f"Bougez les faders ({duration:.0f}s)", end="", flush=True)
        captured: dict[str, float] = {}

        def _cb(message, _):
            msg, _ = message
            if (msg[0] & 0xF0) == 0xB0:  # CC message
                param = self.CC_MAP.get(msg[1])
                if param:
                    captured[param] = msg[2] / 127.0

        self._midi.set_callback(_cb)
        for _ in range(int(duration)):
            time.sleep(1)
            print(".", end="", flush=True)
        time.sleep(duration % 1)
        self._midi.cancel_callback()
        print(f" OK")
        if captured:
            print(f"Capturé : { {k: round(v, 2) for k, v in captured.items()} }")
        else:
            print("(aucun CC reçu — paramètres CLI conservés)")
        return captured

    def close(self) -> None:
        self._midi.close_port()


# ---------------------------------------------------------------------------
# Construction de session
# ---------------------------------------------------------------------------

def _markov_from_gravity(gravity: float) -> MarkovChain:
    """
    Interpole entre transitions uniformes (gravity=0) et dark_chain() (gravity=1).
    Permet de doser la gravité vers les graves sans reconstruire la matrice à la main.
    """
    base = dark_chain()
    if gravity >= 0.98:
        return base
    notes  = base.notes
    uniform = 1.0 / len(notes)
    matrix = {
        note: {m: base.matrix[note][m] * gravity + uniform * (1 - gravity) for m in notes}
        for note in notes
    }
    return MarkovChain(notes, matrix)


def build_session(
    chaos: float          = 0.3,
    bpm: int              = 110,
    steps: int            = 64,
    mode: str             = "morph",
    out: str              = "bang_out.mid",
    seed: str | None      = None,
    weather: dict | None  = None,
    temporal_jitter: bool = False,
    gravity: float        = 0.7,
    cc_depth: float       = 0.5,
) -> None:
    """Assemble et exporte une session MIDI selon les paramètres fournis."""
    engine = BangEngine(bpm=bpm)

    if mode == "random":
        for note in [36, 38, 42, 48]:
            engine.add_voice(note, random_dna(16))

    elif mode == "morph":
        base = morph_dna(
            "x---x---x---x---", "x---?---x↺--░---",
            mutation_rate=chaos * 0.5,
        )
        (engine
            .add_voice(36, mutate_dna(base, intensity=chaos * 0.6))
            .add_voice(38, "----x-------x---")
            .add_voice(42, "x-x-x-x-x-x-x-x")
            .add_voice(24, "x-?-░"))

    elif mode == "weather":
        w = weather or fetch_weather() or {"temperature": 10.0, "wind_speed": 10.0}
        weather = w
        for note, length in [(36, 16), (38, 8), (42, 16), (24, 5)]:
            engine.add_voice(note, mutate_dna(weather_dna(w, length), intensity=chaos * 0.4))

    elif mode in ("markov", "phase2"):
        chain = _markov_from_gravity(gravity)
        kick_patterns = [
            "x---x---",
            mutate_dna("x---x--x", intensity=chaos * 0.8),
            mutate_dna("x-x-x---", intensity=chaos * 0.4),
        ]
        cc_peak     = int(20 + cc_depth * 100)
        breakpoints = [20, cc_peak, cc_peak, int((20 + cc_peak) / 2), 20]

        (engine
            .add_voice(36, kick_patterns if mode == "phase2" else kick_patterns[0])
            .add_voice(38, "----x-------x---")
            .add_voice(42, "x-x-x-x-x-x-x-x")
            .add_markov_voice(chain, trigger_dna=["x-?-░", "x---?---"])
            .add_cc_drone(control=74, breakpoints=breakpoints))

        if weather and mode == "phase2":
            bps = weather_cc_breakpoints(weather, num_points=7)
            engine.add_cc_drone(control=91, breakpoints=list(reversed(bps)))

    engine.export_midi(
        num_steps=steps,
        filename=out,
        seed=seed,
        weather=weather,
        temporal_jitter=temporal_jitter,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bang",
        description="BANG — Séquenceur algorithmique Dark Umbrae",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
modes :
  morph    Croisement + mutation de patterns DNA (défaut)
  random   DNA entièrement aléatoire
  weather  Texture dictée par la météo live de Scaër
  markov   Ligne de basse Markov + polyrythmie
  phase2   Markov + drone CC + météo combinés

exemples :
  python cli.py --chaos 0.7 --bpm 100 --mode markov --steps 128 --out dark.mid
  python cli.py --mode weather --temporal --out live.mid
  python cli.py --mode phase2 --gravity 0.9 --cc-depth 0.8
  python cli.py --list-ports
  python cli.py --controller Zoom --capture 8 --mode phase2 --out zoom_session.mid
        """,
    )

    parser.add_argument(
        "--chaos", type=float, default=0.3, metavar="0-1",
        help="Degré de chaos / mutation (0.0–1.0, défaut : 0.3)",
    )
    parser.add_argument(
        "--bpm", type=int, default=110,
        help="Tempo en BPM (défaut : 110)",
    )
    parser.add_argument(
        "--steps", type=int, default=64,
        help="Nombre de steps à générer (défaut : 64)",
    )
    parser.add_argument(
        "--mode", type=str, default="morph",
        choices=["morph", "random", "weather", "markov", "phase2"],
        help="Mode de génération (défaut : morph)",
    )
    parser.add_argument(
        "--out", type=str, default="bang_out.mid",
        help="Fichier MIDI de sortie (défaut : bang_out.mid)",
    )
    parser.add_argument(
        "--seed", type=str, default=None,
        help="Seed SHA-256 pour régénérer un fichier à l'identique",
    )
    parser.add_argument(
        "--weather", action="store_true",
        help="Récupérer la météo de Scaër (activé automatiquement pour les modes weather/phase2)",
    )
    parser.add_argument(
        "--temporal", action="store_true",
        help="Entropie temporelle : jitter influencé par les microsecondes système",
    )
    parser.add_argument(
        "--gravity", type=float, default=0.7, metavar="0-1",
        help="Gravité Markov vers les graves (0=uniforme, 1=très sombre, défaut : 0.7)",
    )
    parser.add_argument(
        "--cc-depth", type=float, default=0.5, metavar="0-1",
        help="Amplitude de l'automation CC filtre (défaut : 0.5)",
    )
    parser.add_argument(
        "--list-ports", action="store_true",
        help="Afficher les ports MIDI disponibles et quitter",
    )
    parser.add_argument(
        "--controller", type=str, default=None, metavar="NOM",
        help="Nom (partiel) du port MIDI contrôleur à écouter (ex : Zoom, MPK)",
    )
    parser.add_argument(
        "--capture", type=float, default=5.0,
        help="Durée d'écoute du contrôleur en secondes (défaut : 5)",
    )

    args = parser.parse_args()
    args.chaos    = max(0.0, min(1.0, args.chaos))
    args.gravity  = max(0.0, min(1.0, args.gravity))
    args.cc_depth = max(0.0, min(1.0, args.cc_depth))

    # --- --list-ports ---
    if args.list_ports:
        ports = list_midi_ports()
        if ports:
            print("Ports MIDI disponibles :")
            for i, p in enumerate(ports):
                print(f"  [{i}] {p}")
        else:
            print("Aucun port MIDI détecté (python-rtmidi installé ?)")
        sys.exit(0)

    # --- Contrôleur MIDI ---
    ctrl_params: dict = {}
    if args.controller:
        try:
            ctrl = MidiController(port_hint=args.controller)
            ctrl_params = ctrl.capture(duration=args.capture)
            ctrl.close()
        except RuntimeError as e:
            print(f"[Contrôleur] {e}", file=sys.stderr)
            sys.exit(1)

    # Fusion : CLI comme base, contrôleur en override si des CC ont été reçus
    chaos    = ctrl_params.get("chaos",    args.chaos)
    gravity  = ctrl_params.get("gravity",  args.gravity)
    cc_depth = ctrl_params.get("cc_depth", args.cc_depth)
    bpm      = args.bpm
    if "bpm" in ctrl_params:
        bpm = int(60 + ctrl_params["bpm"] * 100)  # 0→60 BPM, 1→160 BPM

    # --- Météo ---
    weather = None
    if args.weather or args.mode in ("weather", "phase2"):
        weather = fetch_weather()
        if weather:
            print(f"Météo Scaër : {weather['temperature']}°C, vent {weather['wind_speed']} km/h")
        else:
            print("Météo Scaër : hors-ligne")

    print(
        f"\nchaos={chaos:.2f}  bpm={bpm}  steps={args.steps}  "
        f"mode={args.mode}  temporal={'oui' if args.temporal else 'non'}"
    )

    build_session(
        chaos=chaos,
        bpm=bpm,
        steps=args.steps,
        mode=args.mode,
        out=args.out,
        seed=args.seed,
        weather=weather,
        temporal_jitter=args.temporal,
        gravity=gravity,
        cc_depth=cc_depth,
    )


if __name__ == "__main__":
    main()
