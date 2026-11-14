import AppKit
import BangCore
import CoreMIDI
import UniformTypeIdentifiers

/// Fonctions ajoutées pour la parité avec le webapp et le ROADMAP : presets
/// personnels (machines, KSP), export morceau, journal des exports, groupes
/// de voix, ports MIDI par voix.
extension AppModel {
    // MARK: - Ports MIDI par voix

    func updatePortRouting() {
        var map: [Int: MIDIEndpointRef] = [:]
        for (i, v) in session.voices.enumerated() {
            if let uid = session.settings[v.label]?.port, let ep = MIDIOut.endpoint(uid) { map[i] = ep }
        }
        router.update(map)
    }

    // MARK: - Presets personnels

    struct PresetFile: Codable {
        var drum: [String: [String: Int]] = [:]
        var ksp: [String: KSPPreset] = [:]
    }

    static let presetsURL = stateURL.deletingLastPathComponent().appendingPathComponent("presets.json")

    func loadPresets() {
        guard let data = try? Data(contentsOf: Self.presetsURL),
              let f = try? JSONDecoder().decode(PresetFile.self, from: data) else { return }
        customDrumPresets = f.drum
        customKSPPresets = f.ksp
    }

    private func savePresets() {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        try? enc.encode(PresetFile(drum: customDrumPresets, ksp: customKSPPresets)).write(to: Self.presetsURL)
    }

    /// Fenêtre de saisie d'un nom. nil = annulé ou vide.
    func askName(_ title: String, _ message: String, initial: String = "") -> String? {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.addButton(withTitle: "Enregistrer")
        alert.addButton(withTitle: "Annuler")
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 260, height: 24))
        field.stringValue = initial
        alert.accessoryView = field
        alert.window.initialFirstResponder = field
        guard alert.runModal() == .alertFirstButtonReturn else { return nil }
        let name = field.stringValue.trimmingCharacters(in: .whitespaces)
        return name.isEmpty ? nil : name
    }

    func saveDrumPreset() {
        guard !session.noteRemap.isEmpty else {
            status = "Aucun mapping de notes à enregistrer : choisis d'abord une machine ou change des notes."
            return
        }
        guard let name = askName("Enregistrer le mapping de notes",
                                 "Les notes de sortie actuelles (Kick, Snare, HiHat…) sous ce nom.",
                                 initial: session.currentPreset) else { return }
        storeDrumPreset(name)
    }

    @discardableResult
    func storeDrumPreset(_ name: String) -> Bool {
        guard !Presets.drumMachines.contains(where: { $0.name == name }) else {
            status = "« \(name) » est un preset intégré : choisis un autre nom."
            return false
        }
        customDrumPresets[name] = session.noteRemap
        session.currentPreset = name
        savePresets()
        status = "Preset machine « \(name) » enregistré."
        return true
    }

    func deleteDrumPreset(_ name: String) {
        customDrumPresets[name] = nil
        if session.currentPreset == name { session.currentPreset = "" }
        savePresets()
        status = "Preset machine « \(name) » supprimé."
    }

    func applyKSP(_ name: String) {
        guard let p = Presets.ksp.first(where: { $0.name == name })?.preset ?? customKSPPresets[name] else { return }
        session.applyKSP(name, p)
        status = "Harmonie « \(name) » : \(p.root) \(Scales.intervals.first { $0.id == p.scale }?.name ?? p.scale), gravité \(String(format: "%.2f", p.gravity))"
    }

    func saveKSPPreset() {
        guard let name = askName("Enregistrer l'harmonie",
                                 "Tonique, gamme, gravité et accords des pistes KSP actuels.",
                                 initial: session.currentKSPPreset) else { return }
        storeKSPPreset(name)
    }

    @discardableResult
    func storeKSPPreset(_ name: String) -> Bool {
        guard !Presets.ksp.contains(where: { $0.name == name }) else {
            status = "« \(name) » est un preset intégré : choisis un autre nom."
            return false
        }
        customKSPPresets[name] = session.currentKSP
        session.currentKSPPreset = name
        savePresets()
        status = "Harmonie « \(name) » enregistrée."
        return true
    }

    func deleteKSPPreset(_ name: String) {
        customKSPPresets[name] = nil
        if session.currentKSPPreset == name { session.currentKSPPreset = "" }
        savePresets()
        status = "Harmonie « \(name) » supprimée."
    }

    // MARK: - Panneaux d'enregistrement

    func midiTypePopup() -> NSPopUpButton {
        let p = NSPopUpButton(frame: .zero, pullsDown: false)
        p.addItems(withTitles: ["Type 1 — une piste par voix", "Type 0 — une seule piste"])
        p.selectItem(at: midiType == 0 ? 1 : 0)
        return p
    }

    func accessoryRow(_ views: [NSView]) -> NSView {
        let row = NSStackView(views: views)
        row.spacing = 12
        row.edgeInsets = NSEdgeInsets(top: 8, left: 12, bottom: 8, right: 12)
        return row
    }

    // MARK: - Journal des exports

    static let exportLogURL = stateURL.deletingLastPathComponent().appendingPathComponent("bang_sessions.jsonl")

    /// Une ligne JSON par export (comme bang_sessions.jsonl du webapp) : de quoi
    /// retrouver la seed et les réglages d'un fichier.
    func logExport(kind: String, file: URL, seed: String, extra: [String: Any] = [:]) {
        let iso = ISO8601DateFormatter()
        var entry: [String: Any] = [
            "timestamp": iso.string(from: Date()),
            "kind": kind,
            "seed": seed,
            "filename": file.lastPathComponent,
            "bpm": session.params.bpm,
            "mode": session.params.mode.rawValue,
            "voices": session.voices.filter { !$0.isCC }.map { ["type": $0.type, "note": $0.note, "pattern_length": $0.dna.count] },
        ]
        if let w = session.weather { entry["weather"] = ["temperature": w.temperature, "wind_speed": w.windSpeed] }
        if session.params.temporal { entry["temporal_jitter"] = true }
        for (k, v) in extra { entry[k] = v }
        guard var line = try? JSONSerialization.data(withJSONObject: entry, options: [.sortedKeys]) else { return }
        line.append(0x0A)
        let url = Self.exportLogURL
        if let h = try? FileHandle(forWritingTo: url) {
            h.seekToEndOfFile(); h.write(line); try? h.close()
        } else {
            try? line.write(to: url)
        }
    }

    func showExportLog() {
        let url = Self.exportLogURL
        if FileManager.default.fileExists(atPath: url.path) {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        } else {
            status = "Aucun export pour l'instant : le journal sera créé au premier export."
        }
    }

    // MARK: - Export morceau

    /// Morceau complet (intro → … → fin) avec les réglages actuels : un .mid
    /// (une piste par instrument, marqueurs de section), et en option un .mid
    /// par section (comme le webapp) et le rendu audio .wav.
    func exportSong() {
        let tag = String(Dice.generateSeed().prefix(8))
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyyMMdd"
        let panel = NSSavePanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "mid") ?? .data]
        panel.nameFieldStringValue = "bang-morceau-\(df.string(from: Date()))-\(tag).mid"
        panel.message = "Morceau d'environ 944 steps : intro, transition, couplets, break, climax, outro, fin (modes Ambient / Noise), avec le chaos, le BPM et la gravité actuels."
        let sectionsBox = NSButton(checkboxWithTitle: "Un .mid par section (dossier)", target: nil, action: nil)
        sectionsBox.state = UserDefaults.standard.bool(forKey: "songSections") ? .on : .off
        let wavBox = NSButton(checkboxWithTitle: "Rendu audio .wav", target: nil, action: nil)
        wavBox.state = UserDefaults.standard.bool(forKey: "songWav") ? .on : .off
        let typePopup = midiTypePopup()
        panel.accessoryView = accessoryRow([typePopup, sectionsBox, wavBox])
        guard panel.runModal() == .OK, let url = panel.url else { return }
        midiType = typePopup.indexOfSelectedItem == 1 ? 0 : 1
        let wantSections = sectionsBox.state == .on, wantWav = wavBox.state == .on
        UserDefaults.standard.set(wantSections, forKey: "songSections")
        UserDefaults.standard.set(wantWav, forKey: "songWav")
        writeSong(to: url, tag: tag, sections: wantSections, wav: wantWav)
    }

    /// Génère et écrit le morceau (tâche de fond). `done` reçoit le message d'état.
    func writeSong(to url: URL, tag: String, sections wantSections: Bool, wav wantWav: Bool,
                   done: ((String) -> Void)? = nil) {

        let p = session.params, weather = session.weather, remap = session.noteRemap
        let kit = drumKit, type = midiType
        status = "Morceau en cours de génération…"
        DispatchQueue.global(qos: .userInitiated).async {
            let seed = Dice.generateSeed()
            let song = SongBuilder.build(chaos: p.chaos, bpm: p.bpm, gravity: p.gravity, ccDepth: p.ccDepth,
                                         weather: weather, seed: seed)
            let input = song.renderInput(noteRemap: remap, weather: weather)
            var written: [String] = []
            var failure: String?
            do {
                try MIDIFileWriter.export(input, numSteps: song.totalSteps, seed: seed,
                                          name: url.deletingPathExtension().lastPathComponent, type: type,
                                          markers: song.markers).write(to: url)
                written.append(url.lastPathComponent)
                if wantSections {
                    let folder = URL(fileURLWithPath: url.deletingPathExtension().path + "-sections")
                    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                    for sec in song.sections {
                        let sin = RenderInput(voices: sec.voices, params: sec.params, weather: weather, noteRemap: remap)
                        try MIDIFileWriter.export(sin, numSteps: sec.steps, seed: seed, name: sec.name, type: type)
                            .write(to: folder.appendingPathComponent("\(sec.name)-\(tag).mid"))
                    }
                    written.append("\(song.sections.count) sections dans « \(folder.lastPathComponent) »")
                }
                if wantWav {
                    let wav = url.deletingPathExtension().appendingPathExtension("wav")
                    let r = try WavExport.render(input: input, numSteps: song.totalSteps, loops: 1, seed: seed,
                                                 kit: kit, seamless: false, to: wav)
                    written.append(String(format: "%@ (%.0f s)", wav.lastPathComponent, r.seconds))
                }
            } catch {
                failure = error.localizedDescription
            }
            DispatchQueue.main.async {
                if let failure {
                    self.status = "Échec du morceau : \(failure)"
                } else {
                    self.logExport(kind: "song", file: url, seed: seed,
                                   extra: ["chaos": p.chaos, "gravity": p.gravity, "cc_depth": p.ccDepth,
                                           "steps": song.totalSteps, "sections": song.sections.count])
                    self.status = "Morceau exporté : " + written.joined(separator: " · ")
                }
                done?(self.status)
            }
        }
    }

    // MARK: - Groupes de voix

    enum VoiceGroup: String, CaseIterable {
        case drums = "BATTERIE", melody = "MÉLODIE", synths = "SYNTHÉS"

        func contains(_ v: Voice) -> Bool {
            if v.isCC { return false }
            let synth = v.type == "vk" || v.type.hasPrefix("vd") || v.type.hasPrefix("vfm") || v.type.hasPrefix("mf")
            switch self {
            case .melody: return v.isMelodic
            case .synths: return synth
            case .drums: return !v.isMelodic && !synth
            }
        }
    }

    func groupIndices(_ g: VoiceGroup) -> [Int] { session.voices.indices.filter { g.contains(session.voices[$0]) } }

    /// Mute (ou solo) collectif : si toutes les voix du groupe le sont déjà, on retire, sinon on applique.
    func toggleGroup(_ g: VoiceGroup, solo: Bool) {
        let idx = groupIndices(g)
        guard !idx.isEmpty else { return }
        let set = solo ? session.soloed : session.muted
        let all = idx.allSatisfy { set.contains($0) }
        for i in idx {
            if solo { if all { session.soloed.remove(i) } else { session.soloed.insert(i) } }
            else { if all { session.muted.remove(i) } else { session.muted.insert(i) } }
        }
    }

    func groupState(_ g: VoiceGroup, solo: Bool) -> Bool {
        let idx = groupIndices(g)
        let set = solo ? session.soloed : session.muted
        return !idx.isEmpty && idx.allSatisfy { set.contains($0) }
    }
}
