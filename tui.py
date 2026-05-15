"""BANG TUI — Interface Textual pour le séquenceur Dark Umbrae"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Button, Footer, Header, Input, Label,
    RichLog, Select, Static, Switch,
)
from rich.text import Text

from bang_engine import (
    BangEngine, dark_chain, fetch_weather,
    morph_dna, mutate_dna, random_dna,
    weather_cc_breakpoints, weather_dna,
    MarkovChain,
)
from cli import _markov_from_gravity


# ---------------------------------------------------------------------------
# DNA rendering
# ---------------------------------------------------------------------------

_DNA_STYLE: dict[str, str] = {
    'x': 'bold bright_white',
    '-': 'dim white',
    '?': 'bold yellow',
    '↺': 'bold cyan',
    '░': 'bold magenta',
}

_NOTE_NAMES: dict[int, str] = {
    24: 'Bass', 33: 'A1', 36: 'Kick', 38: 'Snare',
    40: 'E1',  42: 'HiHat', 43: 'G1', 48: 'Tom',
}

_MODE_OPTIONS = [
    ("Morph",    "morph"),
    ("Random",   "random"),
    ("Weather",  "weather"),
    ("Markov",   "markov"),
    ("Phase 2",  "phase2"),
]


def _render_dna(dna: str, max_len: int = 24) -> Text:
    t = Text()
    for c in dna[:max_len]:
        t.append(c + " ", style=_DNA_STYLE.get(c, ""))
    if len(dna) > max_len:
        t.append("…", style="dim")
    return t


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class VoiceRow(Static):
    DEFAULT_CSS = "VoiceRow { height: 1; padding: 0 1; }"

    def __init__(self, note: int, dna: str, voice_type: str = "drum", **kw):
        super().__init__(**kw)
        self._note = note
        self._dna = dna
        self._vtype = voice_type

    def render(self) -> Text:
        name = _NOTE_NAMES.get(self._note, f"n{self._note}")
        t = Text()
        t.append(f"{self._note:3d} ", style="bold green")
        t.append(f"{name:<5s}  ", style="bold")
        t.append_text(_render_dna(self._dna))
        if self._vtype == "markov":
            t.append("  ↳ Markov", style="italic cyan")
        elif self._vtype == "cc":
            t.append("  ↳ CC auto", style="italic yellow")
        return t


class VoiceGrid(Vertical):
    DEFAULT_CSS = """
    VoiceGrid {
        height: 100%;
        border: solid $primary;
        padding: 1 1;
        overflow-y: auto;
    }
    VoiceGrid Label { color: $text-muted; margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Label("VOIX  ─────────────────────────────────────────")
        yield Static("[dim]Appuyez sur G pour générer[/]", id="voice-hint")

    def update_voices(self, voices: list[tuple[int, str, str]]) -> None:
        for w in list(self.query("VoiceRow")):
            w.remove()
        for w in list(self.query("#voice-hint")):
            w.remove()
        for note, dna, vtype in voices:
            self.mount(VoiceRow(note=note, dna=dna, voice_type=vtype))


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class BangTUI(App):
    """Séquenceur algorithmique BANG — interface visuelle."""

    TITLE = "BANG  ·  Dark Umbrae Sequencer"
    CSS = """
    Screen { layout: vertical; background: $surface; }

    #weather-bar {
        height: 1;
        background: $boost;
        color: $text-muted;
        padding: 0 2;
    }

    #main {
        layout: horizontal;
        height: 1fr;
        margin: 0;
    }

    VoiceGrid { width: 3fr; margin: 1 1 1 1; }

    #controls {
        width: 2fr;
        border: solid $primary;
        padding: 1 2;
        margin: 1 1 1 0;
        overflow-y: auto;
    }

    #controls Label {
        color: $text-muted;
        margin-top: 1;
    }

    #controls .section-title {
        color: $primary;
        text-style: bold;
        margin-top: 0;
    }

    #buttons {
        layout: horizontal;
        height: auto;
        margin-top: 2;
    }

    Button { margin-right: 1; }

    #log-panel {
        height: 8;
        border: solid $panel;
        padding: 0 1;
        margin: 0 1 0 1;
    }

    #seed-bar {
        height: 1;
        background: $boost;
        color: $text-muted;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("g", "generate", "Générer"),
        Binding("e", "export",   "Exporter"),
        Binding("w", "météo",    "Météo"),
        Binding("q", "quit",     "Quitter"),
    ]

    # Internal state
    _engine: BangEngine | None = None
    _voices_state: list[tuple[int, str, str]] = []
    _weather: dict | None = None

    # ---------------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("  Météo Scaër non chargée — appuyez W", id="weather-bar")

        with Horizontal(id="main"):
            yield VoiceGrid(id="voice-grid")

            with Vertical(id="controls"):
                yield Label("MODE", classes="section-title")
                yield Select(_MODE_OPTIONS, value="morph", id="mode-select")

                yield Label("CHAOS  (0.0 – 1.0)")
                yield Input("0.30", placeholder="0.30", id="chaos")

                yield Label("BPM")
                yield Input("110", placeholder="110", id="bpm")

                yield Label("STEPS")
                yield Input("64", placeholder="64", id="steps")

                yield Label("GRAVITY MARKOV  (0.0 – 1.0)")
                yield Input("0.70", placeholder="0.70", id="gravity")

                yield Label("CC DEPTH  (0.0 – 1.0)")
                yield Input("0.50", placeholder="0.50", id="cc-depth")

                yield Label("FICHIER DE SORTIE")
                yield Input("bang_out.mid", placeholder="bang_out.mid", id="out")

                yield Label("ENTROPIE TEMPORELLE")
                yield Switch(value=False, id="temporal")

                with Horizontal(id="buttons"):
                    yield Button("Générer",  id="btn-generate", variant="primary")
                    yield Button("Exporter", id="btn-export",   variant="success")
                    yield Button("Météo",    id="btn-weather",  variant="default")

        yield Static("", id="seed-bar")

        with ScrollableContainer(id="log-panel"):
            yield RichLog(id="log", highlight=True, markup=True, max_lines=200)

        yield Footer()

    def on_mount(self) -> None:
        self._log("BANG prêt — [bold]G[/] générer  [bold]E[/] exporter  [bold]W[/] météo", style="dim")

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _log(self, msg: str, style: str = "") -> None:
        rich_log = self.query_one("#log", RichLog)
        if style:
            rich_log.write(Text.from_markup(f"[{style}]{msg}[/]"))
        else:
            rich_log.write(Text.from_markup(msg))

    def _val(self, widget_id: str, default: float) -> float:
        try:
            return max(0.0, min(1.0, float(self.query_one(f"#{widget_id}", Input).value)))
        except (ValueError, TypeError):
            return default

    def _int(self, widget_id: str, default: int) -> int:
        try:
            return max(1, int(self.query_one(f"#{widget_id}", Input).value))
        except (ValueError, TypeError):
            return default

    def _params(self) -> dict:
        mode = self.query_one("#mode-select", Select).value
        return {
            "mode":     str(mode) if mode != Select.BLANK else "morph",
            "chaos":    self._val("chaos",    0.30),
            "bpm":      self._int("bpm",      110),
            "steps":    self._int("steps",    64),
            "gravity":  self._val("gravity",  0.70),
            "cc_depth": self._val("cc-depth", 0.50),
            "out":      self.query_one("#out",      Input).value or "bang_out.mid",
            "temporal": self.query_one("#temporal", Switch).value,
        }

    def _build_voices(self, p: dict) -> list[tuple[int, str, str]]:
        chaos = p["chaos"]
        mode  = p["mode"]
        w     = self._weather or {"temperature": 10.0, "wind_speed": 10.0}

        if mode == "random":
            return [(n, random_dna(16), "drum") for n in [36, 38, 42, 48]]

        if mode == "morph":
            base = morph_dna("x---x---x---x---", "x---?---x↺--░---", mutation_rate=chaos * 0.5)
            return [
                (36, mutate_dna(base, intensity=chaos * 0.6), "drum"),
                (38, "----x-------x---",                       "drum"),
                (42, "x-x-x-x-x-x-x-x",                       "drum"),
                (24, "x-?-░",                                  "drum"),
            ]

        if mode == "weather":
            return [
                (note, mutate_dna(weather_dna(w, length), intensity=chaos * 0.4), "drum")
                for note, length in [(36, 16), (38, 8), (42, 16), (24, 5)]
            ]

        if mode in ("markov", "phase2"):
            voices = [
                (36, mutate_dna("x---x---", intensity=chaos * 0.4), "drum"),
                (38, "----x-------x---",                             "drum"),
                (42, "x-x-x-x-x-x-x-x",                             "drum"),
                (24, "x-?-░",                                        "markov"),
            ]
            if mode == "phase2":
                cc_peak = int(20 + p["cc_depth"] * 100)
                voices.append((0, f"CC74: 20→{cc_peak}→20", "cc"))
                if self._weather:
                    voices.append((0, "CC91: réverb inverse (météo)", "cc"))
            return voices

        return []

    def _assemble_engine(self, p: dict, voices: list[tuple[int, str, str]]) -> BangEngine:
        engine = BangEngine(bpm=p["bpm"])
        chain  = _markov_from_gravity(p["gravity"])
        cc_peak     = int(20 + p["cc_depth"] * 100)
        breakpoints = [20, cc_peak, cc_peak, int((20 + cc_peak) / 2), 20]

        kick_added = False
        for note, dna, vtype in voices:
            if vtype == "cc":
                continue  # ajoutés séparément
            elif vtype == "markov":
                engine.add_markov_voice(chain, trigger_dna=dna)
            elif p["mode"] == "phase2" and note == 36 and not kick_added:
                engine.add_voice(note, [dna, mutate_dna("x---x--x", intensity=p["chaos"] * 0.8)])
                kick_added = True
            else:
                engine.add_voice(note, dna)

        if p["mode"] in ("markov", "phase2"):
            engine.add_cc_drone(control=74, breakpoints=breakpoints)
            if p["mode"] == "phase2" and self._weather:
                bps = weather_cc_breakpoints(self._weather, num_points=7)
                engine.add_cc_drone(control=91, breakpoints=list(reversed(bps)))

        return engine

    # ---------------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------------

    def action_generate(self) -> None:
        p = self._params()
        self._voices_state = self._build_voices(p)
        self._engine = self._assemble_engine(p, self._voices_state)
        self.query_one("#voice-grid", VoiceGrid).update_voices(self._voices_state)
        n_voices = sum(1 for _, _, t in self._voices_state if t != "cc")
        self._log(
            f"[bold green]► Généré[/]  mode=[bold]{p['mode']}[/]  "
            f"chaos=[yellow]{p['chaos']:.2f}[/]  bpm=[cyan]{p['bpm']}[/]  "
            f"{n_voices} voix"
        )

    def action_export(self) -> None:
        if self._engine is None:
            self.action_generate()
        p = self._params()
        try:
            self._engine.export_midi(
                num_steps=p["steps"],
                filename=p["out"],
                weather=self._weather,
                temporal_jitter=p["temporal"],
            )
            seed  = (self._engine.last_seed or "")[:16]
            meteo = f"  {self._weather['temperature']}°C" if self._weather else ""
            tmp   = "  [+temporal]" if p["temporal"] else ""
            self.query_one("#seed-bar", Static).update(
                f"  seed: {seed}…{tmp}{meteo}"
            )
            self._log(
                f"[bold cyan]💾 Exporté[/]  [bold]{p['out']}[/]  "
                f"[dim]seed: {seed}…{tmp}{meteo}[/]"
            )
        except Exception as e:
            self._log(f"[bold red]✗ Erreur : {e}[/]")

    def action_météo(self) -> None:
        self._log("[dim]Récupération météo Scaër…[/]")
        w = fetch_weather()
        if w:
            self._weather = w
            self.query_one("#weather-bar", Static).update(
                f"  🌡 {w['temperature']}°C   💨 {w['wind_speed']} km/h   Scaër"
            )
            self._log(f"[green]🌤 Météo[/]  {w['temperature']}°C, vent {w['wind_speed']} km/h")
        else:
            self._log("[yellow]⚠ Météo hors-ligne[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        dispatch = {
            "btn-generate": self.action_generate,
            "btn-export":   self.action_export,
            "btn-weather":  self.action_météo,
        }
        action = dispatch.get(event.button.id)
        if action:
            action()


if __name__ == "__main__":
    BangTUI().run()
