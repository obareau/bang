import AppKit
import BangCore
import Combine
import CoreMIDI
import SwiftUI
import UniformTypeIdentifiers

/// Position de lecture — séparée du modèle pour ne redessiner que la grille
/// et le piano-roll 30 fois par seconde, pas toute la fenêtre.
/// Remplace `@State` : sans Xcode, le plugin de macro SwiftUI n'est pas
/// disponible, donc l'état local passe par un petit ObservableObject.
final class Box<T>: ObservableObject {
    @Published var value: T
    init(_ value: T) { self.value = value }
}

@MainActor
final class PlayState: ObservableObject {
    @Published var step = 0
    @Published var steps = 1
    @Published var hits: [Int: Double] = [:]
}

@MainActor
final class AppModel: ObservableObject {
    @Published var session = BangSession() {
        didSet { sessionChanged() }
    }
    @Published var isPlaying = false
    @Published var selectedVoice: Int?
    @Published var status = "Prêt."
    @Published var destinations: [MIDIOut.Destination] = []
    @Published var destinationID: MIDIUniqueID? {
        didSet {
            midi.select(destinationID)
            UserDefaults.standard.set(destinationID.map { Int($0) }, forKey: "destination")
        }
    }
    @Published var internalSynthOn: Bool {
        didSet {
            UserDefaults.standard.set(internalSynthOn, forKey: "internalSynth")
            if internalSynthOn { synth.start() } else { synth.stop() }
        }
    }
    @Published var virtualPortOn: Bool {
        didSet {
            UserDefaults.standard.set(virtualPortOn, forKey: "virtualPort")
            midi.setVirtual(virtualPortOn)
        }
    }
    /// Kit de batterie du synthé interne (canal 10).
    @Published var drumKit: DrumKit {
        didSet {
            UserDefaults.standard.set(drumKit.rawValue, forKey: "drumKit")
            synth.kit = drumKit
            if internalSynthOn && !isPlaying { synth.audition() }
            status = "Batterie : \(drumKit.label)"
        }
    }
    /// Zoom manuel (⌘+ / ⌘− / ⌘0), multiplié au zoom automatique de la fenêtre.
    @Published var zoom: Double = UserDefaults.standard.object(forKey: "zoom") as? Double ?? 1 {
        didSet { UserDefaults.standard.set(zoom, forKey: "zoom") }
    }
    func zoomIn() { zoom = min(2, (zoom * 1.1 * 100).rounded() / 100) }
    func zoomOut() { zoom = max(0.6, (zoom / 1.1 * 100).rounded() / 100) }
    @Published private(set) var preview: [MIDIEvent] = []

    let play = PlayState()
    let router = PortRouter()
    /// Mode FILL (conditions « fill » / « !fill »).
    @Published var fill = false {
        didSet { if player.isRunning { player.update(liveInput()) } }
    }
    /// Type de fichier MIDI à l'export : 1 = une piste par voix, 0 = une seule piste.
    @Published var midiType: Int = UserDefaults.standard.object(forKey: "midiType") as? Int ?? 1 {
        didSet { UserDefaults.standard.set(midiType, forKey: "midiType") }
    }
    /// Presets personnels (mêmes schémas que bang_presets.json / bang_ksp_presets.json).
    @Published var customDrumPresets: [String: [String: Int]] = [:]
    @Published var customKSPPresets: [String: KSPPreset] = [:]
    let studio = Studio()
    let midi = MIDIOut()
    let synth = InternalSynth()
    private lazy var player: Player = {
        let midi = self.midi, synth = self.synth
        let router = self.router
        return Player { s, d1, d2, voice in
            if voice == -2 {
                midi.send(s, d1, d2)
                for ep in router.all { midi.send(s, d1, d2, to: ep) }
            } else {
                midi.send(s, d1, d2, to: router.endpoint(for: voice))
            }
            synth.send(s, d1, d2)
        }
    }()
    private var poll: AnyCancellable?
    private var saveWork: DispatchWorkItem?

    static let stateURL: URL = {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("BANG", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("state.json")
    }()

    init() {
        let d = UserDefaults.standard
        internalSynthOn = d.object(forKey: "internalSynth") as? Bool ?? true
        drumKit = DrumKit(rawValue: d.string(forKey: "drumKit") ?? "") ?? .tr808
        virtualPortOn = d.object(forKey: "virtualPort") as? Bool ?? true
        midi.setVirtual(virtualPortOn)
        refreshDestinations()
        if let saved = d.object(forKey: "destination") as? Int,
           destinations.contains(where: { $0.id == MIDIUniqueID(saved) }) {
            destinationID = MIDIUniqueID(saved)
            midi.select(destinationID)
        }
        midi.onSetupChanged = { [weak self] in
            self?.refreshDestinations()
            self?.refreshClockSources()
        }
        synth.kit = drumKit
        if internalSynthOn { synth.start() }

        if let data = try? Data(contentsOf: Self.stateURL),
           let file = try? JSONDecoder().decode(SessionFile.self, from: data), !file.voices.isEmpty {
            var s = BangSession()
            file.apply(to: &s)
            s.history = []
            session = s
            status = "Session restaurée."
        } else {
            session.generate()
        }
        sessionChanged()
        refreshClockSources()
        setupClockIn()
        studio.model = self
        studio.start()
        loadPresets()
    }

    func refreshDestinations() {
        destinations = MIDIOut.destinations()
        if let id = destinationID, !destinations.contains(where: { $0.id == id }) { destinationID = nil }
    }

    private func sessionChanged() {
        let input = liveInput()
        if player.isRunning && !deferPlayerUpdate { player.update(input) }
        updatePortRouting()
        studio.sessionChanged()
        preview = Renderer.render(input, numSteps: session.params.steps,
                                  rng: Dice(seedString: session.lastSeed.isEmpty ? "0" : session.lastSeed))
        scheduleSave()
    }

    private func scheduleSave() {
        saveWork?.cancel()
        let file = SessionFile(session)
        let work = DispatchWorkItem {
            let enc = JSONEncoder()
            enc.outputFormatting = [.prettyPrinted, .sortedKeys]
            if let data = try? enc.encode(file) { try? data.write(to: AppModel.stateURL) }
        }
        saveWork = work
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 0.8, execute: work)
    }

    // MARK: - Génération

    func generate() {
        if session.params.mode == .weather && session.weather == nil {
            status = "Météo de Scaër…"
            Task {
                let w = await Generator.fetchWeather()
                session.weather = w
                status = w.map { String(format: "Scaër : %.1f °C, vent %.0f km/h", $0.temperature, $0.windSpeed) }
                    ?? "Hors-ligne : météo neutre (10 °C / 10 km/h)."
                session.generate()
            }
            return
        }
        session.generate()
        status = "\(session.params.mode.label) · seed \(session.lastSeed.prefix(12))…"
    }

    func refreshWeather() {
        Task {
            status = "Météo de Scaër…"
            let w = await Generator.fetchWeather()
            session.weather = w
            status = w.map { String(format: "Scaër : %.1f °C, vent %.0f km/h", $0.temperature, $0.windSpeed) }
                ?? "Hors-ligne."
        }
    }

    func undo() {
        if session.undo() { status = "Annulé." } else { status = "Rien à annuler." }
    }

    // MARK: - Transport

    func togglePlay() { isPlaying ? stop() : start() }

    func start() {
        if internalSynthOn { synth.start() }
        cycleCount = 0
        if song.on { beginSong() }
        player.start(liveInput())
        isPlaying = true
        poll = Timer.publish(every: 1.0 / 30, on: .main, in: .common).autoconnect().sink { [weak self] _ in
            guard let self else { return }
            let (step, steps, _, hits) = player.status()
            if play.step != step { play.step = step }
            if play.steps != steps { play.steps = steps }
            play.hits = hits
            if syncOn {
                let bpm = player.clockBPM
                let old = self.clockBPM
                if bpm.map({ abs($0 - (old ?? 0)) > 0.05 }) ?? (old != nil) { self.clockBPM = bpm }
            }
        }
    }

    func stop() {
        player.stop()
        isPlaying = false
        poll = nil
        play.step = 0
        play.hits = [:]
        if morph != nil { morph = nil }
    }

    // MARK: - Jeu live

    /// Morphing en cours : vers la mémoire `slot`, sur `cycles` cycles.
    struct MorphState: Equatable {
        var slot: Int
        var cycles: Int
        var progress: Double
    }

    struct SongState: Equatable {
        var on = false
        var text = "1x4 2x4"
        var part = 0
        var repeat_ = 0
    }

    /// Auto-évolution : une variation tous les N cycles (0 = off).
    @Published var evolveEvery: Int = 0
    @Published var autoAdvance = false
    @Published var advanceEvery: Int = 4
    @Published var morph: MorphState?
    @Published var morphTargetSlot = 1
    @Published var morphCycles = 8
    @Published var song = SongState()
    @Published private(set) var cycleCount = 0
    @Published var activeAB: Character?

    private var deferPlayerUpdate = false

    /// Entrée de rendu pour le lecteur : la session + le morph en cours.
    func liveInput() -> RenderInput {
        var input = session.renderInput()
        input.fill = fill
        if let m = morph, let target = session.slots[m.slot] {
            input.morph = MorphTarget(voices: target.voices, progress: m.progress)
        }
        return input
    }

    /// Appelé un peu avant chaque fin de cycle : applique les automatismes
    /// (Song, avance auto, morph, évolution) pour le cycle `next`.
    private func cycleWillEnd(next: Int) {
        guard isPlaying else { return }
        deferPlayerUpdate = true
        cycleCount += 1
        let rng = Dice()

        if song.on {
            let chain = SongChain.parse(song.text)
            if !chain.parts.isEmpty {
                song.repeat_ += 1
                if song.repeat_ >= chain.parts[min(song.part, chain.parts.count - 1)].repeats {
                    song.part = (song.part + 1) % chain.parts.count
                    song.repeat_ = 0
                    session.loadSlot(chain.parts[song.part].slot)
                }
            }
        } else if autoAdvance && advanceEvery > 0 && cycleCount % advanceEvery == 0 {
            if let i = session.advanceSlot(rng: rng) { status = "Mémoire \(i + 1)" }
        }

        if var m = morph {
            m.progress = min(1, m.progress + 1 / Double(max(1, m.cycles)))
            if m.progress >= 1 {
                session.loadSlot(m.slot)
                morph = nil
                status = "Morph terminé : mémoire \(m.slot + 1)"
            } else {
                morph = m
            }
        }

        if evolveEvery > 0 && cycleCount % evolveEvery == 0 && morph == nil {
            session.varyAll()
        }

        deferPlayerUpdate = false
        player.queue(liveInput(), forCycle: next)
    }

    func toggleMorph() {
        if morph != nil { morph = nil; status = "Morph annulé."; return }
        guard session.slots[morphTargetSlot] != nil else {
            status = "Mémoire \(morphTargetSlot + 1) vide : rien vers quoi morpher."
            return
        }
        morph = MorphState(slot: morphTargetSlot, cycles: morphCycles, progress: 0)
        status = "Morph vers la mémoire \(morphTargetSlot + 1) en \(morphCycles) cycles"
        if player.isRunning { player.update(liveInput()) }
    }

    func beginSong() {
        let chain = SongChain.parse(song.text)
        guard let first = chain.parts.first else {
            status = "Song vide : écris par ex. « 1x4 2x2 3 »"
            song.on = false
            return
        }
        song.part = 0
        song.repeat_ = 0
        if session.slots[first.slot] != nil { session.loadSlot(first.slot) }
        status = "Song : \(chain.description)"
    }

    func toggleSong() {
        song.on.toggle()
        if song.on { autoAdvance = false; beginSong() }
    }

    func storeAB(_ b: Bool) {
        session.storeAB(b)
        activeAB = b ? "B" : "A"
        status = "Pattern mémorisé en \(b ? "B" : "A")."
    }

    func loadAB(_ b: Bool) {
        if session.loadAB(b) { activeAB = b ? "B" : "A"; status = "Pattern \(b ? "B" : "A")." }
        else { status = "\(b ? "B" : "A") est vide (⌥ clic pour mémoriser)." }
    }

    // MARK: Tap tempo

    private var taps: [Double] = []

    /// Médiane des intervalles des 5 derniers taps (comme le webapp).
    func tap() {
        let now = Player.now()
        if let last = taps.last, now - last > 3 { taps = [] }
        taps.append(now)
        if taps.count > 5 { taps.removeFirst() }
        guard taps.count >= 2 else { status = "TAP… encore"; return }
        let iv = zip(taps.dropFirst(), taps).map { $0 - $1 }.sorted()
        let median = iv[iv.count / 2]
        let bpm = Int((60 / median).rounded())
        session.params.bpm = min(240, max(40, bpm))
        status = "Tap tempo : \(session.params.bpm) BPM"
    }

    // MARK: Synchro MIDI clock

    @Published var clockSources: [MIDIClockIn.Source] = []
    @Published var syncSourceID: MIDIUniqueID? {
        didSet { applySync() }
    }
    @Published private(set) var clockBPM: Double?
    var syncOn: Bool { syncSourceID != nil }
    let clockIn = MIDIClockIn()

    func refreshClockSources() {
        clockSources = MIDIClockIn.sources()
        if let id = syncSourceID, !clockSources.contains(where: { $0.id == id }) { syncSourceID = nil }
    }

    private func applySync() {
        clockIn.connect(syncSourceID)
        player.setSync(syncOn)
        clockBPM = nil
        if let id = syncSourceID, let s = clockSources.first(where: { $0.id == id }) {
            status = "Synchro sur « \(s.name) » : attend Start ou l'horloge…"
        } else {
            status = "Horloge interne."
        }
        if player.isRunning { player.update(liveInput()) }
    }

    private func setupClockIn() {
        let player = self.player
        clockIn.onRealtime = { [weak self] status, t in
            switch status {
            case 0xF8:
                player.clockPulse(at: t)
            case 0xFA:
                player.clockStart()
                DispatchQueue.main.async { self?.syncStart() }
            case 0xFB:
                DispatchQueue.main.async { self?.syncStart() }
            case 0xFC:
                DispatchQueue.main.async { if self?.syncOn == true { self?.stop() } }
            default:
                break
            }
        }
        // BANG_DEBUG_SLOW_CYCLE_MS : simule une interface lente (diagnostic).
        let slow = Double(ProcessInfo.processInfo.environment["BANG_DEBUG_SLOW_CYCLE_MS"] ?? "") ?? 0
        let studio = self.studio
        player.onStep = { step, steps in studio.clockStep(step, steps) }
        player.onNote = { voice, note, vel, step in studio.clockNote(voice: voice, note: note, velocity: vel, step: step) }
        player.onCycle = { [weak self] next in
            DispatchQueue.main.asyncAfter(deadline: .now() + slow / 1000) { self?.cycleWillEnd(next: next) }
        }
    }

    private func syncStart() {
        guard syncOn else { return }
        if !isPlaying { start() }
    }

    // MARK: - Fichiers

    var suggestedName: String {
        "bang_\(session.params.mode.rawValue)_\(session.lastSeed.prefix(8))"
    }

    func midiData() -> Data {
        MIDIFileWriter.export(session.renderInput(), numSteps: session.params.steps,
                              seed: session.lastSeed.isEmpty ? Dice.generateSeed() : session.lastSeed,
                              name: suggestedName, type: midiType)
    }

    func exportMIDI() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "mid") ?? .data]
        panel.nameFieldStringValue = suggestedName + ".mid"
        let typePopup = midiTypePopup()
        panel.accessoryView = accessoryRow([NSTextField(labelWithString: "Fichier MIDI :"), typePopup])
        guard panel.runModal() == .OK, let url = panel.url else { return }
        midiType = typePopup.indexOfSelectedItem == 1 ? 0 : 1
        do {
            try midiData().write(to: url)
            logExport(kind: "midi", file: url, seed: session.lastSeed)
            status = "Exporté : \(url.lastPathComponent)"
        } catch {
            status = "Échec export : \(error.localizedDescription)"
        }
    }

    // MARK: - Export WAV

    @Published var wavLoops: Int = UserDefaults.standard.object(forKey: "wavLoops") as? Int ?? 1 {
        didSet { UserDefaults.standard.set(wavLoops, forKey: "wavLoops") }
    }
    @Published var wavSeamless: Bool = UserDefaults.standard.object(forKey: "wavSeamless") as? Bool ?? true {
        didSet { UserDefaults.standard.set(wavSeamless, forKey: "wavSeamless") }
    }
    @Published private(set) var isRenderingWav = false

    static func slug(_ s: String) -> String {
        let folded = s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .init(identifier: "fr_FR"))
        let parts = folded.lowercased().split { !($0.isLetter || $0.isNumber) }
        return parts.joined(separator: "-")
    }

    /// Partie « preset » du nom : mode + kit (+ machine si un preset est appliqué).
    var wavPreset: String {
        var p = "\(Self.slug(session.params.mode.rawValue))-\(drumKit.short.lowercased())"
        if !session.currentPreset.isEmpty { p += "-" + Self.slug(session.currentPreset) }
        return p
    }

    /// Numéro de variation : augmente quand on exporte un pattern différent
    /// pour le même preset (mémorisé entre les lancements).
    func variationNumber(commit: Bool) -> Int {
        let key = wavPreset
        let fingerprint = session.lastSeed + "|" + session.voices.map(\.dna).joined(separator: "|")
        var store = UserDefaults.standard.dictionary(forKey: "wavVariations") as? [String: [String: Any]] ?? [:]
        let last = store[key]
        let n = last?["n"] as? Int ?? 0
        let same = (last?["fp"] as? String) == fingerprint
        let number = same ? max(1, n) : n + 1
        if commit {
            store[key] = ["n": number, "fp": fingerprint]
            UserDefaults.standard.set(store, forKey: "wavVariations")
        }
        return number
    }

    /// preset-variation-date, ex. « bassline-808-v003-2026-11-13_2150 ».
    var wavName: String {
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd_HHmm"
        return "\(wavPreset)-v\(String(format: "%03d", variationNumber(commit: false)))-\(df.string(from: Date()))"
    }

    func exportWAV() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [UTType.wav]
        panel.nameFieldStringValue = wavName + ".wav"
        panel.message = "Rendu audio du pattern avec le synthé interne (batterie \(drumKit.short))."

        // Choix du nombre de répétitions, dans la fenêtre d'enregistrement.
        let label = NSTextField(labelWithString: "Répétitions du pattern :")
        let popup = NSPopUpButton(frame: .zero, pullsDown: false)
        let choices = [1, 2, 4, 8, 16]
        popup.addItems(withTitles: choices.map { "×\($0)" })
        popup.selectItem(at: choices.firstIndex(of: wavLoops) ?? 0)
        let loopBox = NSButton(checkboxWithTitle: "Boucle parfaite (la queue des sons revient au début)",
                               target: nil, action: nil)
        loopBox.state = wavSeamless ? .on : .off
        let row = NSStackView(views: [label, popup, loopBox])
        row.spacing = 12
        row.edgeInsets = NSEdgeInsets(top: 8, left: 12, bottom: 8, right: 12)
        panel.accessoryView = row

        guard panel.runModal() == .OK, let url = panel.url else { return }
        wavLoops = choices[max(0, popup.indexOfSelectedItem)]
        wavSeamless = loopBox.state == .on
        renderWAV(to: url)
    }

    /// Lance le rendu en tâche de fond (n'interrompt pas la lecture).
    func renderWAV(to url: URL, done: ((Result<WavExport.Result, Error>) -> Void)? = nil) {
        guard !isRenderingWav else { return }
        _ = variationNumber(commit: true)
        let input = session.renderInput()
        let steps = session.params.steps
        let seed = session.lastSeed.isEmpty ? Dice.generateSeed() : session.lastSeed
        let loops = wavLoops, kit = drumKit, seamless = wavSeamless
        isRenderingWav = true
        status = "Rendu WAV…"
        DispatchQueue.global(qos: .userInitiated).async {
            let result = Result {
                try WavExport.render(input: input, numSteps: steps, loops: loops, seed: seed, kit: kit,
                                    seamless: seamless, to: url)
            }
            DispatchQueue.main.async {
                self.isRenderingWav = false
                switch result {
                case .success(let r):
                    self.logExport(kind: "wav", file: url, seed: seed, extra: ["loops": loops, "kit": kit.short])
                    self.status = String(format: "WAV exporté : %@ (%.1f s)", url.lastPathComponent, r.seconds)
                case .failure(let e):
                    self.status = "Échec WAV : \(e.localizedDescription)"
                }
                done?(result)
            }
        }
    }

    /// Fichier .mid temporaire pour le glisser-déposer vers un DAW / le Finder.
    func dragFile() -> NSItemProvider {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(suggestedName + ".mid")
        try? midiData().write(to: url)
        return NSItemProvider(contentsOf: url) ?? NSItemProvider()
    }

    /// Projet complet (.bang = la session JSON : pattern, réglages, mémoires, A/B).
    static var bangType: UTType { UTType(filenameExtension: "bang") ?? .json }

    func saveSession() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [Self.bangType, .json]
        panel.nameFieldStringValue = suggestedName + ".bang"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        do {
            try enc.encode(SessionFile(session)).write(to: url)
            status = "Session enregistrée : \(url.lastPathComponent)"
        } catch {
            status = "Échec : \(error.localizedDescription)"
        }
    }

    func openSession() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [Self.bangType, .json]
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let file = try JSONDecoder().decode(SessionFile.self, from: Data(contentsOf: url))
            file.apply(to: &session)
            status = "Session ouverte : \(url.lastPathComponent) (\(file.bangVersion))"
        } catch {
            status = "Fichier illisible : \(error.localizedDescription)"
        }
    }
}
