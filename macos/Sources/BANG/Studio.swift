import AppKit
import BangCore
import CoreMIDI
import Foundation
import UniformTypeIdentifiers

/// DAW et matériel : OSC, Ableton Live (AbletonOSC), Strudel, export des
/// voix séparées, gabarit TouchOSC, MIDI Learn et panneaux NTS-1 / MicroFreak.
@MainActor
final class Studio: ObservableObject {
    enum Tab: String, CaseIterable { case osc = "OSC", ableton = "Ableton", export = "Strudel · export",
                                     learn = "MIDI Learn", nts1 = "NTS-1", microfreak = "MicroFreak" }

    weak var model: AppModel?
    let osc = OSCLink()
    let ableton = AbletonLink()
    let learnIn = MIDIClockIn()
    private let d = UserDefaults.standard

    @Published var showSheet = false
    @Published var tab: Tab = .osc

    // MARK: OSC
    @Published var oscTxOn: Bool { didSet { d.set(oscTxOn, forKey: "oscTxOn"); applyOSC() } }
    @Published var oscHost: String { didSet { d.set(oscHost, forKey: "oscHost"); applyOSC() } }
    @Published var oscTxPort: Int { didSet { d.set(oscTxPort, forKey: "oscTxPort"); applyOSC() } }
    @Published var oscRxOn: Bool { didSet { d.set(oscRxOn, forKey: "oscRxOn"); applyOSC() } }
    @Published var oscRxPort: Int { didSet { d.set(oscRxPort, forKey: "oscRxPort"); applyOSC() } }
    @Published var oscError: String?
    @Published var oscLog: [OSCLogEntry] = []
    private var lastSentFingerprint = ""

    // MARK: Ableton
    @Published var abletonHost: String { didSet { d.set(abletonHost, forKey: "abletonHost") } }
    @Published var abletonPort: Int { didSet { d.set(abletonPort, forKey: "abletonPort") } }
    @Published var abletonTrack: Int { didSet { d.set(abletonTrack, forKey: "abletonTrack") } }
    @Published var abletonSlot: Int { didSet { d.set(abletonSlot, forKey: "abletonSlot") } }
    @Published var abletonStatus = ""

    // MARK: MIDI Learn
    @Published var learnSources: [MIDIClockIn.Source] = []
    @Published var learnSourceID: MIDIUniqueID? { didSet { learnIn.connect(learnSourceID) } }
    @Published var learnState = ""
    @Published var learning = false
    private var learnHits: [Double] = []
    private var learnStart = 0.0

    // MARK: Synthés
    @Published var nts1Channel: Int { didSet { d.set(nts1Channel, forKey: "nts1Channel") } }
    @Published var mfChannel: Int { didSet { d.set(mfChannel, forKey: "mfChannel") } }
    @Published var ccValues: [String: Int] = [:]

    init() {
        oscTxOn = d.object(forKey: "oscTxOn") as? Bool ?? false
        oscHost = d.string(forKey: "oscHost") ?? "127.0.0.1"
        oscTxPort = d.object(forKey: "oscTxPort") as? Int ?? 57120
        oscRxOn = d.object(forKey: "oscRxOn") as? Bool ?? false
        oscRxPort = d.object(forKey: "oscRxPort") as? Int ?? 9000
        abletonHost = d.string(forKey: "abletonHost") ?? "127.0.0.1"
        abletonPort = d.object(forKey: "abletonPort") as? Int ?? 11000
        abletonTrack = d.object(forKey: "abletonTrack") as? Int ?? 1
        abletonSlot = d.object(forKey: "abletonSlot") as? Int ?? 1
        nts1Channel = d.object(forKey: "nts1Channel") as? Int ?? 1
        mfChannel = d.object(forKey: "mfChannel") as? Int ?? 9
        // Diagnostic : BANG_OSC_TX=hôte:port, BANG_OSC_RX=port, BANG_ABLETON=hôte:port (non mémorisés).
        let env = ProcessInfo.processInfo.environment
        if let tx = env["BANG_OSC_TX"]?.split(separator: ":"), tx.count == 2, let p = Int(tx[1]) {
            oscTxOn = true; oscHost = String(tx[0]); oscTxPort = p
        }
        if let rx = env["BANG_OSC_RX"].flatMap(Int.init) { oscRxOn = true; oscRxPort = rx }
        if let a = env["BANG_ABLETON"]?.split(separator: ":"), a.count == 2, let p = Int(a[1]) {
            abletonHost = String(a[0]); abletonPort = p
        }
    }

    func start() {
        osc.onReceive = { [weak self] m in
            DispatchQueue.main.async { self?.handle(m) }
        }
        learnIn.onNoteOn = { [weak self] _, _, t in
            DispatchQueue.main.async { self?.learnHit(t) }
        }
        refreshLearnSources()
        applyOSC()
        // Moniteur OSC : rafraîchi 4 fois par seconde tant que la fenêtre est ouverte.
        Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.showSheet, self.tab == .osc else { return }
                let l = self.osc.log
                if l != self.oscLog { self.oscLog = l }
            }
        }
    }

    // MARK: - OSC

    private func applyOSC() {
        osc.configureTX(host: oscTxOn ? oscHost : nil, port: UInt16(clamping: oscTxPort))
        osc.configureRX(port: oscRxOn ? UInt16(clamping: oscRxPort) : 0) { [weak self] err in
            DispatchQueue.main.async { self?.oscError = err }
        }
        if oscTxOn { lastSentFingerprint = ""; sessionChanged() }
    }

    /// Appelé à chaque changement de session : met à jour les noms de voix et,
    /// si le pattern a changé, émet l'état (/bang/bpm, /bang/voice/n/dna…).
    func sessionChanged() {
        guard let s = model?.session else { return }
        osc.setLabels(s.voices.map(\.label))
        guard oscTxOn else { return }
        let fp = s.lastSeed + "|" + s.voices.map(\.dna).joined(separator: "|") + "|\(s.params.bpm)|\(s.params.steps)"
        guard fp != lastSentFingerprint else { return }
        lastSentFingerprint = fp
        var msgs = [
            OSCMessage("/bang/bpm", [.int(Int32(s.params.bpm))]),
            OSCMessage("/bang/chaos", [.float(Float(s.params.chaos))]),
            OSCMessage("/bang/steps", [.int(Int32(s.params.steps))]),
            OSCMessage("/bang/mode", [.string(s.params.mode.rawValue)]),
            OSCMessage("/bang/seed", [.string(String(s.lastSeed.prefix(16)))]),
        ]
        let input = s.renderInput()
        for (i, v) in s.voices.enumerated() where !v.isCC {
            msgs.append(OSCMessage("/bang/voice/\(i)/dna", [.string(v.dna)]))
            msgs.append(OSCMessage("/bang/voice/\(i)/note", [.int(Int32(input.outputNote(for: i)))]))
        }
        for m in msgs { osc.send(m) }
    }

    /// Hooks de l'horloge (thread temps réel) : /bang/clock et /bang/<voix>.
    nonisolated func clockStep(_ step: Int, _ steps: Int) {
        guard osc.transmitting else { return }
        osc.send(OSCMessage("/bang/clock", [.int(Int32(step)), .int(Int32(steps))]), log: step == 0)
    }

    nonisolated func clockNote(voice: Int, note: Int, velocity: Int, step: Int) {
        guard osc.transmitting, let name = osc.label(voice) else { return }
        osc.send(OSCMessage("/bang/\(name)", [.int(Int32(step)), .int(Int32(velocity)), .int(Int32(note))]))
    }

    /// Messages reçus (mêmes adresses que le webapp, plus quelques commandes live).
    private func handle(_ m: OSCMessage) {
        guard let model else { return }
        let parts = m.address.split(separator: "/").map(String.init)   // ["bang", "param", "bpm"]
        guard parts.first == "bang", parts.count >= 2 else { return }
        let n = m.args.first?.number
        func voiceIndex(_ key: String) -> Int? {
            if let i = Int(key), model.session.voices.indices.contains(i) { return i }
            return model.session.voices.firstIndex { $0.label == key || $0.label.hasPrefix(key + " ") }
        }
        switch parts[1] {
        case "generate": model.generate()
        case "vary": model.session.varyAll()
        case "play": model.start()
        case "stop": model.stop()
        case "param" where parts.count >= 3 && n != nil:
            let v = n!
            switch parts[2] {
            case "bpm": model.session.params.bpm = Int(v.clamped(40, 240))
            case "chaos": model.session.params.chaos = v.clamped(0, 1)
            case "gravity": model.session.params.gravity = v.clamped(0, 1)
            case "swing": model.session.params.swing = v.clamped(0, 1)
            case "microtiming": model.session.params.microtiming = v.clamped(0, 1)
            case "cc_depth": model.session.params.ccDepth = v.clamped(0, 1)
            case "steps": model.session.params.steps = Int(v.clamped(1, 256))
            default: break
            }
        case "density" where parts.count >= 3 && n != nil:
            if let i = voiceIndex(parts[2]) { model.session.updateSettings(i) { $0.density = n!.clamped(0, 1) } }
        case "lock" where parts.count >= 3:
            if let i = voiceIndex(parts[2]) {
                if (n ?? 1) != 0 { model.session.locked.insert(i) } else { model.session.locked.remove(i) }
            }
        case "mute" where parts.count >= 3:
            if let i = voiceIndex(parts[2]) {
                if (n ?? 1) != 0 { model.session.muted.insert(i) } else { model.session.muted.remove(i) }
            }
        case "slot" where parts.count >= 3:
            if let k = Int(parts[2]), (1...8).contains(k) { model.session.loadSlot(k - 1) }
        case "evolve":
            model.evolveEvery = Int((n ?? 0).clamped(0, 64))
        default:
            break
        }
    }

    // MARK: - Ableton Live

    func sendToAbleton() {
        guard let s = model?.session, !s.voices.isEmpty else { return }
        let host = abletonHost, port = UInt16(clamping: abletonPort)
        let firstTrack = max(0, abletonTrack - 1), slot = max(0, abletonSlot - 1)
        let length = Float(s.params.steps) / 4
        var msgs = [OSCMessage("/live/song/set/tempo", [.float(Float(s.params.bpm))])]
        var count = 0
        for (k, clip) in VoiceNotes.clips(s).enumerated() {
            let t = Int32(firstTrack + k), sl = Int32(slot)
            msgs.append(OSCMessage("/live/clip_slot/delete_clip", [.int(t), .int(sl)]))
            msgs.append(OSCMessage("/live/clip_slot/create_clip", [.int(t), .int(sl), .float(length)]))
            msgs.append(OSCMessage("/live/clip/set/name", [.int(t), .int(sl), .string("BANG! \(clip.label)")]))
            // AbletonOSC : pitch, début, durée, vélocité, mute — par lots pour rester sous la taille d'un paquet UDP.
            for chunk in stride(from: 0, to: clip.notes.count, by: 64) {
                var args: [OSCMessage.Arg] = [.int(t), .int(sl)]
                for nt in clip.notes[chunk..<min(clip.notes.count, chunk + 64)] {
                    args += [.int(Int32(nt.pitch)), .float(Float(nt.startBeats)), .float(Float(nt.durationBeats)),
                             .int(Int32(nt.velocity)), .int(0)]
                }
                msgs.append(OSCMessage("/live/clip/add_notes", args))
            }
            count += 1
        }
        ableton.send(msgs, host: host, port: port)
        abletonStatus = "\(count) clip(s) envoyé(s) : pistes \(firstTrack + 1)–\(firstTrack + count), scène \(slot + 1), \(s.params.bpm) BPM."
        model?.status = "Ableton : " + abletonStatus
    }

    func syncTempoFromAbleton() {
        abletonStatus = "Demande du tempo à Live…"
        ableton.queryTempo(host: abletonHost, port: UInt16(clamping: abletonPort)) { [weak self] bpm in
            DispatchQueue.main.async {
                guard let self else { return }
                if let bpm {
                    self.model?.session.params.bpm = Int(bpm.rounded())
                    self.abletonStatus = String(format: "Tempo de Live : %.2f BPM", bpm)
                } else {
                    self.abletonStatus = "Pas de réponse : Live est-il ouvert avec AbletonOSC actif (port \(self.abletonPort)) ?"
                }
            }
        }
    }

    // MARK: - Strudel, export, TouchOSC

    func copyStrudel() {
        guard let s = model?.session else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(StrudelExport.code(s), forType: .string)
        model?.status = "Code Strudel copié dans le presse-papier."
    }

    func exportVoices() {
        guard let model else { return }
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Exporter ici"
        panel.message = "Un fichier .mid par voix (pour les glisser sur des pistes séparées)."
        guard panel.runModal() == .OK, let dir = panel.url else { return }
        var n = 0
        for (i, v) in model.session.voices.enumerated() where !v.isCC {
            let name = "\(model.wavPreset)-\(AppModel.slug(v.label))-\(i + 1).mid"
            if (try? MIDIFileWriter.exportVoice(model.session, voice: i).write(to: dir.appendingPathComponent(name))) != nil { n += 1 }
        }
        model.status = "\(n) voix exportées dans « \(dir.lastPathComponent) »."
    }

    static var touchOSCTemplate: URL? {
        if let u = Bundle.main.url(forResource: "bang_control", withExtension: "tosc") { return u }
        // Lancement depuis les sources : macos/Sources/BANG/… → static/
        let repo = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let u = repo.appendingPathComponent("static/bang_control.tosc")
        return FileManager.default.fileExists(atPath: u.path) ? u : nil
    }

    func saveTouchOSC() {
        guard let src = Studio.touchOSCTemplate else { model?.status = "Gabarit TouchOSC introuvable."; return }
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "bang_control.tosc"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        try? FileManager.default.removeItem(at: url)
        if (try? FileManager.default.copyItem(at: src, to: url)) != nil {
            model?.status = "Gabarit TouchOSC enregistré : \(url.lastPathComponent)"
        }
    }

    // MARK: - MIDI Learn

    func refreshLearnSources() {
        learnSources = MIDIClockIn.sources()
        if let id = learnSourceID, !learnSources.contains(where: { $0.id == id }) { learnSourceID = nil }
    }

    /// Décompte de 2 temps, puis enregistre la longueur du pattern et quantifie.
    func learn(voice: Int) {
        guard let model, !learning else { return }
        guard learnSourceID != nil else {
            tab = .learn; showSheet = true
            learnState = "Choisis d'abord l'entrée MIDI (clavier ou pads)."
            return
        }
        let bpm = Double(model.session.params.bpm)
        let steps = max(1, model.session.voices.indices.contains(voice) ? model.session.voices[voice].dna.count : model.session.params.steps)
        let stepSec = 60 / bpm / 4
        let beat = 60 / bpm
        learning = true
        learnHits = []
        learnStart = .infinity   // rien n'est retenu pendant le décompte
        Task { @MainActor in
            for k in stride(from: 2, through: 1, by: -1) {
                learnState = "Décompte : \(k)…"
                if model.internalSynthOn { model.synth.audition(note: 37) }
                try? await Task.sleep(nanoseconds: UInt64(beat * 1e9))
            }
            learnStart = Player.now()
            let total = Double(steps) * stepSec
            learnState = String(format: "⏺ Enregistrement — %.1f s", total)
            try? await Task.sleep(nanoseconds: UInt64(total * 1e9))
            learning = false
            let dna = MIDILearn.quantize(learnHits, steps: steps, stepSeconds: stepSec)
            if learnHits.isEmpty {
                learnState = "Aucune note reçue : rien n'a changé."
            } else {
                model.session.setPattern(voice, dna)
                learnState = "✓ \(model.session.voices[voice].label) : \(dna)"
            }
            model.status = "MIDI Learn — " + learnState
        }
    }

    private func learnHit(_ t: Double) {
        guard learning, learnStart > 0, t >= learnStart - 0.05 else { return }
        learnHits.append(max(0, t - learnStart))
    }

    // MARK: - Synthés (CC en direct)

    func sendCC(_ cc: Int, _ value: Int, channel: Int, key: String) {
        ccValues[key] = value
        model?.midi.send(0xB0 | UInt8((channel - 1) & 0x0F), UInt8(cc & 0x7F), UInt8(value & 0x7F))
    }
}
