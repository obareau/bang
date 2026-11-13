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
    let midi = MIDIOut()
    let synth = InternalSynth()
    private lazy var player: Player = {
        let midi = self.midi, synth = self.synth
        return Player { s, d1, d2 in
            midi.send(s, d1, d2)
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
        midi.onSetupChanged = { [weak self] in self?.refreshDestinations() }
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
    }

    func refreshDestinations() {
        destinations = MIDIOut.destinations()
        if let id = destinationID, !destinations.contains(where: { $0.id == id }) { destinationID = nil }
    }

    private func sessionChanged() {
        let input = session.renderInput()
        if player.isRunning { player.update(input) }
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
        player.start(session.renderInput())
        isPlaying = true
        poll = Timer.publish(every: 1.0 / 30, on: .main, in: .common).autoconnect().sink { [weak self] _ in
            guard let self else { return }
            let (step, steps, hits) = player.status()
            if play.step != step { play.step = step }
            if play.steps != steps { play.steps = steps }
            play.hits = hits
        }
    }

    func stop() {
        player.stop()
        isPlaying = false
        poll = nil
        play.step = 0
        play.hits = [:]
    }

    // MARK: - Fichiers

    var suggestedName: String {
        "bang_\(session.params.mode.rawValue)_\(session.lastSeed.prefix(8))"
    }

    func midiData() -> Data {
        MIDIFileWriter.export(session.renderInput(), numSteps: session.params.steps,
                              seed: session.lastSeed.isEmpty ? Dice.generateSeed() : session.lastSeed,
                              name: suggestedName)
    }

    func exportMIDI() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "mid") ?? .data]
        panel.nameFieldStringValue = suggestedName + ".mid"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            try midiData().write(to: url)
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

    func saveSession() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = suggestedName + ".json"
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
        panel.allowedContentTypes = [.json]
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
