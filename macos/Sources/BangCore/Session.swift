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
    public var history: [Snapshot] = []
    public var slots: [Snapshot?] = Array(repeating: nil, count: 8)
    public var currentSlot = 0

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

    // MARK: - Rendu

    public func renderInput(drumChannel: Int = 9, respectMute: Bool = true) -> RenderInput {
        RenderInput(voices: voices, params: params, settings: settings, plocks: plocks, weather: weather,
                    drumChannel: drumChannel, noteRemap: noteRemap,
                    audible: respectMute ? voices.indices.map(isAudible) : [])
    }
}
