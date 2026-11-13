import Foundation

/// Écriture Standard MIDI File (type 0 ou 1) — sans dépendance.
public enum MIDIFileWriter {
    struct Track {
        var bytes: [UInt8] = []
        var lastTick = 0

        mutating func delta(_ tick: Int) {
            let d = max(0, tick - lastTick)
            bytes += vlq(d)
            lastTick = max(lastTick, tick)
        }

        mutating func meta(_ type: UInt8, _ payload: [UInt8], at tick: Int = 0) {
            delta(tick)
            bytes += [0xFF, type] + vlq(payload.count) + payload
        }

        mutating func event(_ e: MIDIEvent) {
            delta(e.tick)
            bytes += [e.statusByte, UInt8(e.data1 & 0x7F), UInt8(e.data2 & 0x7F)]
        }

        mutating func end() { meta(0x2F, [], at: lastTick) }

        var chunk: [UInt8] { Array("MTrk".utf8) + be32(bytes.count) + bytes }
    }

    static func vlq(_ value: Int) -> [UInt8] {
        var v = max(0, value)
        var out = [UInt8(v & 0x7F)]
        v >>= 7
        while v > 0 {
            out.insert(UInt8(v & 0x7F) | 0x80, at: 0)
            v >>= 7
        }
        return out
    }

    static func be32(_ v: Int) -> [UInt8] { [24, 16, 8, 0].map { UInt8((v >> $0) & 0xFF) } }
    static func be16(_ v: Int) -> [UInt8] { [8, 0].map { UInt8((v >> $0) & 0xFF) } }

    /// Export d'un pattern complet.
    /// type 1 : piste 0 tempo/seed + une piste par voix + une par drone CC.
    public static func export(_ input: RenderInput, numSteps: Int, seed: String,
                              name: String = "bang", type: Int = 1) -> Data {
        let rng = Dice(seedString: seed)
        let events = Renderer.render(input, numSteps: numSteps, rng: rng)
        let tempo = Int(60_000_000 / Double(max(1, input.params.bpm)))
        let tempoBytes = [UInt8((tempo >> 16) & 0xFF), UInt8((tempo >> 8) & 0xFF), UInt8(tempo & 0xFF)]

        func header(_ t: inout Track) {
            t.meta(0x03, Array(name.utf8))
            t.meta(0x01, Array("BANG_SEED:\(seed)".utf8))
            t.meta(0x51, tempoBytes)
        }

        var tracks: [Track] = []
        if type == 0 {
            var t = Track()
            header(&t)
            for e in events { t.event(e) }
            t.end()
            tracks = [t]
        } else {
            var t0 = Track()
            header(&t0)
            t0.end()
            tracks.append(t0)
            for (vi, v) in input.voices.enumerated() where !v.isCC {
                var t = Track()
                t.meta(0x03, Array(v.label.utf8))
                for e in events where e.voice == vi { t.event(e) }
                t.end()
                tracks.append(t)
            }
            for (k, ccName) in Renderer.ccTrackNames(input.params, weather: input.weather).enumerated() {
                var t = Track()
                t.meta(0x03, Array(ccName.utf8))
                for e in events where e.voice == -(k + 1) { t.event(e) }
                t.end()
                tracks.append(t)
            }
        }

        var out = Array("MThd".utf8) + be32(6) + be16(type == 0 ? 0 : 1) + be16(tracks.count) + be16(Renderer.ppq)
        for t in tracks { out += t.chunk }
        return Data(out)
    }
}
