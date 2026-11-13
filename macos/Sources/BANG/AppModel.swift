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
        virtualPortOn = d.object(forKey: "virtualPort") as? Bool ?? true
        midi.setVirtual(virtualPortOn)
        refreshDestinations()
        if let saved = d.object(forKey: "destination") as? Int,
           destinations.contains(where: { $0.id == MIDIUniqueID(saved) }) {
            destinationID = MIDIUniqueID(saved)
            midi.select(destinationID)
        }
        midi.onSetupChanged = { [weak self] in self?.refreshDestinations() }
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
