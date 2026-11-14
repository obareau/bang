import Foundation

/// État de session — portage de bang_session.BangSession (sans threads :
/// c'est une valeur, la couche app la publie vers le lecteur live).
public struct BangSession: Sendable {
    public struct Snapshot: Codable, Equatable, Sendable {
        public var voices: [Voice]
        public var plocks: [[PLock]]
        public var params: GenParams
    }

    public var params = GenParams()
    public var voices: [Voice] = []
    public var plocks: [[PLock]] = []
    public var settings: [String: VoiceSettings] = [:]
    public var noteRemap: [String: Int] = [:]
    public var locked: Set<Int> = []
    public var muted: Set<Int> = []
    public var soloed: Set<Int> = []
    public var weather: Weather?
    public var lastSeed = ""
    public var currentPreset = ""
    public var currentKSPPreset = ""
    /// Polyphonie max (0 = illimitée), comme `max_poly` du webapp.
    public var maxPoly = 0
    /// Interpolation des p-locks entre deux valeurs définies.
    public var plockInterp: PLockInterpolation = .off
    public var history: [Snapshot] = []
    public var slots: [Snapshot?] = Array(repeating: nil, count: 8)
    public var currentSlot = 0
    /// Poids de tirage des mémoires pour l'avance automatique (1…9).
    public var slotWeights: [Int] = Array(repeating: 1, count: 8)
    public var slotA: Snapshot?
    public var slotB: Snapshot?

    public init() {}

    var snapshot: Snapshot { Snapshot(voices: voices, plocks: plocks, params: params) }

    mutating func pushHistory() {
        guard !voices.isEmpty else { return }
        history.append(snapshot)
        if history.count > 32 { history.removeFirst() }
    }

    mutating func restore(_ s: Snapshot) {
        voices = s.voices
        plocks = s.plocks
        params = s.params
    }

    // MARK: - Génération

    /// Nouveau pattern. Si `params.seed` est vide, une seed est tirée et
    /// mémorisée dans `lastSeed` pour pouvoir rejouer exactement ce résultat.
    public mutating func generate() {
        let p = params.normalized()
        let seed = p.seed.isEmpty ? Dice.generateSeed(weather: weather) : p.seed
        let rng = Dice(seedString: seed)
        pushHistory()
        var fresh = Generator.buildVoices(p, weather: weather, rng: rng)
        // Longueurs imposées (polymétrie), comme apply_voice_steps.
        for i in fresh.indices where !fresh[i].isCC && !fresh[i].isBabka {
            if let n = settings[fresh[i].label]?.length, n > 0 { fresh[i].dna = DNA.resize(fresh[i].dna, to: n) }
        }
        for idx in locked where idx < voices.count && idx < fresh.count { fresh[idx] = voices[idx] }
        params = p
        voices = fresh
        plocks = p.mode.hasPlocks ? Generator.plocks(for: fresh, params: p, rng: rng) : []
        lastSeed = seed
        let n = voices.count
        muted = muted.filter { $0 < n }
        soloed = soloed.filter { $0 < n }
        locked = locked.filter { $0 < n }
    }

    @discardableResult
    public mutating func undo() -> Bool {
        guard let last = history.popLast() else { return false }
        restore(last)
        return true
    }

    // MARK: - Transforms par voix

    @discardableResult
    public mutating func transform(_ idx: Int, _ f: (String) -> String) -> Bool {
        guard voices.indices.contains(idx), !locked.contains(idx), !voices[idx].isCC else { return false }
        pushHistory()
        voices[idx].dna = f(voices[idx].dna)
        return true
    }

    public mutating func setPattern(_ idx: Int, _ dna: String) {
        let d = dna.trimmingCharacters(in: .whitespaces)
        guard voices.indices.contains(idx), !d.isEmpty, voices[idx].dna != d else { return }
        pushHistory()
        voices[idx].dna = d
    }

    /// Clic dans la grille : fait tourner le symbole du step.
    public mutating func cycleStep(_ idx: Int, _ step: Int) {
        guard voices.indices.contains(idx), !locked.contains(idx) else { return }
        var a = Array(voices[idx].dna)
        guard a.indices.contains(step) else { return }
        pushHistory()
        a[step] = DNA.nextSymbol(a[step])
        voices[idx].dna = String(a)
    }

    public mutating func regen(_ idx: Int) {
        guard voices.indices.contains(idx), !locked.contains(idx), !voices[idx].isCC else { return }
        let rng = Dice()
        let fresh = Generator.buildVoices(params, weather: weather, rng: rng)
        pushHistory()
        voices[idx].dna = idx < fresh.count && fresh[idx].type == voices[idx].type
            ? fresh[idx].dna
            : DNA.mutate(voices[idx].dna, intensity: 0.9, rng: rng)
    }

    public mutating func varyAll() {
        guard !voices.isEmpty else { return }
        let rng = Dice()
        pushHistory()
        for i in voices.indices where !locked.contains(i) && !voices[i].isCC {
            voices[i].dna = DNA.mutate(voices[i].dna, intensity: 0.12, rng: rng)
        }
    }

    // MARK: - Mute / solo / lock

    public func isAudible(_ i: Int) -> Bool {
        soloed.isEmpty ? !muted.contains(i) : soloed.contains(i)
    }

    public mutating func toggle(_ set: WritableKeyPath<BangSession, Set<Int>>, _ i: Int) {
        if self[keyPath: set].contains(i) { self[keyPath: set].remove(i) } else { self[keyPath: set].insert(i) }
    }

    public func settings(for i: Int) -> VoiceSettings {
        voices.indices.contains(i) ? settings[voices[i].label] ?? VoiceSettings() : VoiceSettings()
    }

    public mutating func updateSettings(_ i: Int, _ f: (inout VoiceSettings) -> Void) {
        guard voices.indices.contains(i) else { return }
        var s = settings(for: i)
        f(&s)
        settings[voices[i].label] = s
    }

    /// Change la longueur d'une voix (polymétrie) et la mémorise pour les
    /// prochaines générations. 0 = longueur naturelle du mode.
    public mutating func setLength(_ i: Int, _ n: Int) {
        guard voices.indices.contains(i), !voices[i].isCC, !voices[i].isBabka, !locked.contains(i) else { return }
        updateSettings(i) { $0.length = n > 0 ? n : nil }
        if n > 0 && voices[i].dna.count != n {
            pushHistory()
            voices[i].dna = DNA.resize(voices[i].dna, to: n)
        }
    }

    /// Note de sortie d'une voix (non mélodique) ; nil = note d'origine.
    public mutating func setNote(_ i: Int, _ note: Int?) {
        guard voices.indices.contains(i) else { return }
        let v = voices[i]
        let key = v.isBabka ? (Voice.noteNames[v.note] ?? v.label) : v.label
        if let note { noteRemap[key] = min(127, max(0, note)) } else { noteRemap[key] = nil }
    }

    // MARK: - Presets

    public mutating func applyGroove(_ name: String) {
        guard let g = Presets.grooves.first(where: { $0.name == name })?.dna, !voices.isEmpty else { return }
        pushHistory()
        var pi = 0
        for i in voices.indices where !voices[i].isCC {
            if !locked.contains(i), pi < g.count, !g[pi].isEmpty { voices[i].dna = g[pi] }
            pi += 1
        }
    }

    /// Mapping de notes d'une boîte à rythme : appliqué à la sortie (rendu),
    /// les voix gardent leur note GM d'origine donc leur nom.
    /// Mapping de notes nommé (preset intégré ou personnel).
    public mutating func applyDrumMap(_ name: String, _ map: [String: Int]) {
        noteRemap = map
        currentPreset = name
    }

    /// Preset d'harmonie (KSP) : tonique, gamme, gravité et accords des pistes KSP.
    public mutating func applyKSP(_ name: String, _ preset: KSPPreset) {
        params.root = preset.root
        params.scale = preset.scale
        params.gravity = preset.gravity.clamped(0, 1)
        for (label, chord) in preset.chords where Chords.all.contains(where: { $0.id == chord }) {
            settings[label, default: VoiceSettings()].chord = chord
        }
        currentKSPPreset = name
    }

    /// Harmonie courante, pour l'enregistrer comme preset KSP.
    public var currentKSP: KSPPreset {
        KSPPreset(root: params.root, scale: params.scale, gravity: params.gravity,
                  chords: settings.filter { $0.key.hasPrefix("KSP") && $0.value.chord != "mono" }.mapValues(\.chord))
    }

    // MARK: - Pistes CC (p-locks)

    /// Ajoute une piste CC vide à une voix (gardée d'une génération à l'autre).
    public mutating func addCCLane(_ i: Int, cc: Int, name: String) {
        guard voices.indices.contains(i), !voices[i].isCC else { return }
        let n = max(1, voices[i].isBabka ? params.steps : max(voices[i].dna.count, params.steps))
        updateSettings(i) { s in
            if !s.ccLanes.contains(where: { $0.cc == cc }) {
                s.ccLanes.append(PLock(cc: cc, name: name, style: "manuel", values: Array(repeating: nil, count: n)))
            }
        }
    }

    public mutating func removeCCLane(_ i: Int, cc: Int) {
        updateSettings(i) { $0.ccLanes.removeAll { $0.cc == cc } }
    }

    /// Tirage aléatoire borné des p-locks d'une voix (pistes générées et
    /// ajoutées) : chaque step reçoit une valeur dans [lo, hi] avec la probabilité `density`.
    public mutating func randomizePlocks(_ i: Int, density: Double, lo: Int, hi: Int, rng: Dice) {
        guard voices.indices.contains(i) else { return }
        let a = min(lo, hi), b = max(lo, hi)
        func roll(_ pl: PLock) -> PLock {
            var out = pl
            out.values = pl.values.indices.map { _ in rng.random() < density ? rng.int(a, b) : nil }
            return out
        }
        pushHistory()
        if i < plocks.count { plocks[i] = plocks[i].map(roll) }
        updateSettings(i) { $0.ccLanes = $0.ccLanes.map(roll) }
    }

    public mutating func clearPlocks(_ i: Int) {
        guard voices.indices.contains(i) else { return }
        pushHistory()
        func clear(_ pl: PLock) -> PLock { var o = pl; o.values = o.values.map { _ in nil }; return o }
        if i < plocks.count { plocks[i] = plocks[i].map(clear) }
        updateSettings(i) { $0.ccLanes = $0.ccLanes.map(clear) }
    }

    public mutating func applyDrumPreset(_ name: String) {
        guard let map = Presets.drumMachines.first(where: { $0.name == name })?.map else { return }
        noteRemap = map
        currentPreset = name
    }

    // MARK: - Slots SEQ (8 mémoires)

    public mutating func saveSlot(_ i: Int) {
        guard slots.indices.contains(i), !voices.isEmpty else { return }
        slots[i] = snapshot
        currentSlot = i
    }

    public mutating func loadSlot(_ i: Int) {
        guard slots.indices.contains(i), let s = slots[i] else { return }
        pushHistory()
        restore(s)
        currentSlot = i
    }

    /// Avance automatique : tire une autre mémoire pleine, pondérée par
    /// `slotWeights` (portage de seq_advance). Retourne l'index chargé ou nil.
    @discardableResult
    public mutating func advanceSlot(rng: Dice) -> Int? {
        let filled = slots.indices.filter { slots[$0] != nil }
        guard !filled.isEmpty else { return nil }
        let others = filled.filter { $0 != currentSlot }
        let pool = others.isEmpty ? filled : others
        let next = rng.weighted(pool, pool.map { Double(max(1, slotWeights[$0])) })
        loadSlot(next)
        return next
    }

    // MARK: - A/B

    public mutating func storeAB(_ b: Bool) {
        guard !voices.isEmpty else { return }
        if b { slotB = snapshot } else { slotA = snapshot }
    }

    @discardableResult
    public mutating func loadAB(_ b: Bool) -> Bool {
        guard let s = b ? slotB : slotA else { return false }
        pushHistory()
        restore(s)
        return true
    }

    // MARK: - Rendu

    public func renderInput(drumChannel: Int = 9, respectMute: Bool = true) -> RenderInput {
        var input = RenderInput(voices: voices, params: params, settings: settings, plocks: plocks, weather: weather,
                                drumChannel: drumChannel, noteRemap: noteRemap,
                                audible: respectMute ? voices.indices.map(isAudible) : [])
        input.maxPoly = maxPoly
        input.plockInterp = plockInterp
        return input
    }
}
