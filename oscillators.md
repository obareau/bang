# BANG! Oscillators — NTS-1 logue SDK

## Status

**Compiled & Ready** ✅
- `MarkovWave` (1348 bytes, 1.8KB packaged)
  - Chaîne de Markov morphe sine/saw/square/triangle
  - SHAPE = chaos, SHIFT+SHAPE = vitesse morph, P1 = sub mix, P2 = sub interval, P3 = bias

**To Write** (4 oscillators)

### 1. Drone — Random walk harmonics

Concept: Very ambient, sustained tone with slow random harmonic evolution.

Parameters:
- SHAPE: base frequency (0-127)
- ALT: harmonic spread (0-127)
- P1: walk speed (0-127)
- P2: harmonic count (0-127)
- P3: sustain time (0-127)

Implementation:
```c
// Pseudo-code
float harmonics[8];  // Random walk on harmonic amplitudes
float walk_speed = param1 / 127.0;

for each sample:
  update each harmonic with brownian motion (walk_speed)
  output = sum of (sine * harmonic[i])
  apply slow envelope
```

**Difficulty**: LOW (basic oscillator + RNG)

---

### 2. Karplus-Strong — Physical string model

Concept: Plucked string simulation, very natural sounding.

Parameters:
- SHAPE: pluck position (0-127, 0=bridge, 127=fret)
- ALT: string stiffness (0-127)
- P1: decay time (0-127)
- P2: damping (0-127)
- P3: excitation noise (0-127)

Implementation:
```c
// Pseudo-code
float delay_line[buffer_size];  // Circular buffer
float write_pos = 0;

init: fill delay_line with noise * excitation
for each sample:
  read from delay_line[read_pos]
  apply low-pass filter (damping)
  apply feedback decay
  write back to delay_line[write_pos]
  advance read/write pointers
```

**Difficulty**: MEDIUM (circular buffer + filtering)

---

### 3. Bitfield — Lo-fi glitch operations

Concept: Bitwise operations on samples create digital/lo-fi artifacts.

Parameters:
- SHAPE: operation select (0=AND, 32=OR, 64=XOR, 96=SHL, 127=SHR)
- ALT: bit depth (8-24 bits)
- P1: sample rate reduction (0-127, glitch factor)
- P2: quantization levels (0-127)
- P3: feedback loop (0-127)

Implementation:
```c
// Pseudo-code
uint32_t state = seed;

for each sample:
  state = (state << 1) | (state >> 31);  // LCG or LFSR
  uint32_t sample = state & bit_mask;    // Reduce bit depth
  apply bitwise op (AND/OR/XOR/shift)
  quantize to N levels
  output as float
```

**Difficulty**: LOW (bitwise ops)

---

### 4. PM Stack — Phase modulation chain

Concept: Multiple sine operators phase-modulating each other (like FM but cleaner).

Parameters:
- SHAPE: ratio A:B (0-127 = 0.5 to 16.0)
- ALT: ratio C:D (0-127)
- P1: mod index (0-127)
- P2: stack depth (0-127, 2-8 operators)
- P3: feedback (0-127)

Implementation:
```c
// Pseudo-code (DX7-style 4-operator stack)
struct Op { float phase, ratio, level, feedback; };
Op ops[4];  // Selectable 2-8

for each sample:
  for op in ops:
    phase += ratio * base_freq
    mod_input = previous_op * level
    output = sin(phase + mod_input)
  apply feedback
```

**Difficulty**: MEDIUM (phase tracking, multiple ops)

---

## Build Instructions

```bash
cd ~/DEV/nts1-oscillators/

# MarkovWave (already compiled)
ls -la markovwave/markovwave.ntkdigunit  # 1.3 KB

# For new oscillators:
PLATFORMDIR=~/DEV/logue-sdk/platform/nutekt-digital make install
# Outputs: *.ntkdigunit files → Korg Librarian → NTS-1
```

## Integration

Once compiled:
1. Export .ntkdigunit files to Korg Librarian
2. Upload to NTS-1 via USB
3. In BANG! NTS-1 panel: oscillators appear in OSC selector
4. SHAPE/ALT parameters auto-map to P1-P3 in ratchet engine

## Timeline

- MarkovWave: ✅ READY
- Drone: ~2h (simple RNG harmonics)
- Karplus-Strong: ~3h (circular buffer + filtering)
- Bitfield: ~1h (bitwise ops, lo-fi effect)
- PM Stack: ~2h (phase tracking, multiple ops)

**Total Phase 5**: ~8h dev + testing
