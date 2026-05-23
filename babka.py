"""
babka.py — Syntaxe Babka pour BANG!

Fusion DNA BANG + mini-notation Strudel.

Atomes DNA (inchangés) : x - ? ↺ ░
Opérateurs structurels :
  [a b c]    subdivision : n atomes dans 1 step
  <a b c>    alternance cycle par cycle (séparés par espaces)
  x(n,k)     euclidien inline : expand vers k steps
  [x(n,k)]   euclidien overlay : k steps compressés dans 1 step

Usage :
    from babka import parse, to_events
    steps = parse("x-[x x]-?(3,8)", cycle=0)
    events = to_events(steps, ticks_per_step=120, note=36)
"""

from __future__ import annotations

from dataclasses import dataclass, replace


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BabkaStep:
    trigger: bool
    velocity: int
    prob: float
    ratchet: int
    jitter: int
    duration: float = 1.0  # fraction d'un step de base (1.0 = plein, 0.5 = demi)


_ATOMS: dict[str, BabkaStep] = {
    'x': BabkaStep(True,  105, 1.0, 1,  0),
    '-': BabkaStep(False,   0, 0.0, 1,  0),
    '?': BabkaStep(True,   90, 0.5, 1,  0),
    '↺': BabkaStep(True,  110, 1.0, 3,  0),
    '░': BabkaStep(True,   85, 1.0, 1, 25),
}


def _mk(c: str, duration: float = 1.0) -> BabkaStep:
    base = _ATOMS.get(c, _ATOMS['-'])
    return replace(base, duration=duration)


# ---------------------------------------------------------------------------
# Euclidien (Bresenham)
# ---------------------------------------------------------------------------

def _euclidean(n: int, k: int, atom: str = 'x') -> list[BabkaStep]:
    """Distribue n triggers sur k steps — algorithme de Bresenham."""
    k = max(k, 1)
    n = min(max(n, 0), k)
    return [_mk(atom if (i * n % k) < n else '-') for i in range(k)]


# ---------------------------------------------------------------------------
# Parser récursif descendant
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, s: str, cycle: int) -> None:
        self.s = s
        self.pos = 0
        self.cycle = cycle

    def parse(self) -> list[BabkaStep]:
        steps: list[BabkaStep] = []
        while self.pos < len(self.s):
            steps.extend(self._item())
        return steps

    def _item(self) -> list[BabkaStep]:
        if self.pos >= len(self.s):
            return []

        c = self.s[self.pos]

        if c == '<':
            return self._alt()

        if c == '[':
            return self._group()

        if c in _ATOMS:
            self.pos += 1
            # suffixe euclidien uniquement sur les atomes
            if self.pos < len(self.s) and self.s[self.pos] == '(':
                n, k = self._euc_suffix()
                return _euclidean(n, k, c)
            return [_mk(c)]

        # caractère inconnu — on saute
        self.pos += 1
        return []

    def _group(self) -> list[BabkaStep]:
        """Parse [...] — subdivision : tous les steps partagent 1 step de durée."""
        self.pos += 1  # consume '['
        inner: list[BabkaStep] = []
        while self.pos < len(self.s) and self.s[self.pos] != ']':
            inner.extend(self._item())
        if self.pos < len(self.s):
            self.pos += 1  # consume ']'
        if not inner:
            return []
        total = sum(s.duration for s in inner)
        return [replace(s, duration=s.duration / total) for s in inner]

    def _alt(self) -> list[BabkaStep]:
        """Parse <a b c> — sélectionne alternatives[cycle % n] et re-parse."""
        self.pos += 1  # consume '<'
        alternatives: list[str] = []
        current: list[str] = []
        depth = 0

        while self.pos < len(self.s):
            c = self.s[self.pos]
            if c in ('<', '['):
                depth += 1
                current.append(c)
                self.pos += 1
            elif c == ']':
                depth -= 1
                current.append(c)
                self.pos += 1
            elif c == '>' and depth > 0:
                depth -= 1
                current.append(c)
                self.pos += 1
            elif c == '>' and depth == 0:
                alternatives.append(''.join(current))
                self.pos += 1
                break
            elif c == ' ' and depth == 0:
                alternatives.append(''.join(current))
                current = []
                self.pos += 1
            else:
                current.append(c)
                self.pos += 1

        if not alternatives:
            return []
        selected = alternatives[self.cycle % len(alternatives)]
        return _Parser(selected, self.cycle).parse()

    def _euc_suffix(self) -> tuple[int, int]:
        """Parse (n,k) depuis la position courante."""
        self.pos += 1  # consume '('
        start = self.pos
        while self.pos < len(self.s) and self.s[self.pos] != ')':
            self.pos += 1
        inside = self.s[start:self.pos]
        if self.pos < len(self.s):
            self.pos += 1  # consume ')'
        parts = inside.split(',')
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except (IndexError, ValueError):
            return 0, 1


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def parse(pattern: str, cycle: int = 0) -> list[BabkaStep]:
    """Parse un pattern Babka en liste de BabkaStep.

    Args:
        pattern: chaîne Babka (ex: "x-[x x]-?(3,8)")
        cycle:   numéro de cycle courant (pour résolution des <alternances>)

    Returns:
        Liste de BabkaStep — durations relatives, somme ≠ n steps fixes.
    """
    return _Parser(pattern.strip(), cycle).parse()


def to_events(
    steps: list[BabkaStep],
    ticks_per_step: int,
    note: int,
) -> list[tuple[int, int, int, float, int, int]]:
    """Convertit des BabkaStep en events absolus pour BangEngine.

    Returns:
        Liste de (abs_tick, dur_ticks, velocity, prob, ratchet, jitter)
    """
    events = []
    cursor = 0.0
    for s in steps:
        dur_ticks = max(1, int(s.duration * ticks_per_step))
        if s.trigger:
            events.append((
                int(cursor),
                dur_ticks,
                s.velocity,
                s.prob,
                s.ratchet,
                s.jitter,
            ))
        cursor += s.duration * ticks_per_step
    return events


def total_steps(steps: list[BabkaStep]) -> float:
    """Durée totale du pattern en nombre de steps de base."""
    return sum(s.duration for s in steps)


# ---------------------------------------------------------------------------
# Tests rapides
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    cases = [
        # (pattern, cycle, description)
        ("x-x-",            0, "DNA pur"),
        ("x-[x x]-?",       0, "subdivision"),
        ("<x- -x>",         0, "alternance cycle 0"),
        ("<x- -x>",         1, "alternance cycle 1"),
        ("x(3,8)",          0, "euclidien inline 3/8"),
        ("[x(3,8)]",        0, "euclidien overlay 3/8 → 1 step"),
        ("x-[x(2,4)]?",    0, "euclidien overlay dans pattern"),
        ("<x-x- ?-?->",     1, "alternance complexe cycle 1"),
        ("↺-[x ?]-░(2,4)", 0, "combinaison complète"),
    ]

    ok = 0
    for pat, cyc, desc in cases:
        try:
            result = parse(pat, cycle=cyc)
            tot = total_steps(result)
            print(f"  OK  [{desc}]  '{pat}' c={cyc} → {len(result)} steps, total={tot:.3f}")
            ok += 1
        except Exception as e:
            print(f"  FAIL [{desc}]  '{pat}' c={cyc} → {e}", file=sys.stderr)

    print(f"\n{ok}/{len(cases)} passed")

    # Détail euclidien 3/8
    print("\n--- x(3,8) ---")
    for s in parse("x(3,8)"):
        sym = 'x' if s.trigger else '-'
        print(f"  {sym}  vel={s.velocity} dur={s.duration}")

    # Détail subdivision
    print("\n--- [x x x] ---")
    for s in parse("[x x x]"):
        print(f"  x  dur={s.duration:.4f}")

    # Détail euclidien overlay
    print("\n--- [x(3,4)] ---")
    for s in parse("[x(3,4)]"):
        sym = 'x' if s.trigger else '-'
        print(f"  {sym}  dur={s.duration:.4f}  (total={total_steps(parse('[x(3,4)]')):.4f})")
