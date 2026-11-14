import AVFoundation
import AudioToolbox
import BangCore
import Foundation

/// Rendu audio hors-ligne du pattern → fichier WAV.
///
/// Même chaîne que la lecture live (synthé GM d'Apple + réverbe, batterie
/// 808/909 synthétisée sur le canal 10), mais en mode « manual rendering »
/// d'AVAudioEngine : plus rapide que le temps réel, et chaque évènement MIDI
/// tombe à l'échantillon près (on rend jusqu'à l'évènement, on l'envoie, on
/// continue).
enum WavExport {
    struct Result {
        var seconds: Double
        var peakBefore: Float
    }

    enum Failure: LocalizedError {
        case engine(String)
        var errorDescription: String? {
            switch self { case .engine(let s): return "Moteur audio : \(s)" }
        }
    }

    static let sampleRate = 48_000.0

    /// - loops : nombre de répétitions du pattern. La 1re est identique à
    ///   l'export .mid (même seed) ; les suivantes sont re-tirées comme en live.
    /// - seamless : boucle parfaite. Le fichier dure exactement `loops` patterns
    ///   et ce qui sonne encore après la fin (queues de kick, réverbe…) est
    ///   replié au début : rejoué en boucle, la fin enchaîne sans couture.
    ///   Sinon, la queue est simplement ajoutée à la fin (rendu « one-shot »).
    /// - tail : secondes rendues après la fin pour capter les queues.
    static func render(input: RenderInput, numSteps: Int, loops: Int, seed: String,
                       kit: DrumKit, seamless: Bool = true, tail: Double = 4.0, to url: URL) throws -> Result {
        // --- Évènements de toute la durée ---
        let cycleTicks = numSteps * Renderer.ticksPerStep
        var events: [MIDIEvent] = []
        let base = Dice.seedValue(seed)
        for l in 0..<max(1, loops) {
            let rng = l == 0 ? Dice(seedString: seed) : Dice(seed: base &+ UInt64(l) &* 0x9E37_79B9)
            var cycleInput = input
            cycleInput.cycle = l   // conditions « 1:2 », « 1er cycle »… comme en lecture
            for var e in Renderer.render(cycleInput, numSteps: numSteps, rng: rng) {
                e.tick += l * cycleTicks
                events.append(e)
            }
        }
        events.sort { ($0.tick, $0.kind == .noteOn ? 1 : 0) < ($1.tick, $1.kind == .noteOn ? 1 : 0) }
        let secPerTick = 60.0 / (Double(max(1, input.params.bpm)) * Double(Renderer.ppq))
        func frame(_ tick: Int) -> AVAudioFramePosition { AVAudioFramePosition((Double(tick) * secPerTick * sampleRate).rounded()) }
        let musicFrames = frame(cycleTicks * max(1, loops))
        let totalFrames = musicFrames + AVAudioFramePosition(tail * sampleRate)

        // --- Graphe audio hors-ligne ---
        let engine = AVAudioEngine()
        let stereo = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 2)!
        let maxFrames: AVAudioFrameCount = 4096
        do {
            try engine.enableManualRenderingMode(.offline, format: stereo, maximumFrameCount: maxFrames)
        } catch { throw Failure.engine(error.localizedDescription) }

        let desc = AudioComponentDescription(componentType: kAudioUnitType_MusicDevice,
                                             componentSubType: kAudioUnitSubType_DLSSynth,
                                             componentManufacturer: kAudioUnitManufacturer_Apple,
                                             componentFlags: 0, componentFlagsMask: 0)
        let synth = AVAudioUnitMIDIInstrument(audioComponentDescription: desc)
        let reverb = AVAudioUnitReverb()
        reverb.loadFactoryPreset(.mediumRoom)
        reverb.wetDryMix = 14
        let drums = DrumSynth(sampleRate: sampleRate)
        drums.gain = 0.5
        let mono = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)!
        let drumNode = AVAudioSourceNode(format: mono) { _, _, frames, abl -> OSStatus in
            let buffers = UnsafeMutableAudioBufferListPointer(abl)
            guard let first = buffers.first, let data = first.mData else { return noErr }
            drums.render(data.assumingMemoryBound(to: Float.self), count: Int(frames))
            for b in buffers.dropFirst() { b.mData?.copyMemory(from: data, byteCount: Int(b.mDataByteSize)) }
            return noErr
        }
        drumNode.volume = 0.6
        engine.attach(synth)
        engine.attach(reverb)
        engine.attach(drumNode)
        engine.connect(synth, to: reverb, format: nil)
        engine.connect(reverb, to: engine.mainMixerNode, format: nil)
        engine.connect(drumNode, to: engine.mainMixerNode, format: mono)

        do { try engine.start() } catch { throw Failure.engine(error.localizedDescription) }
        defer { engine.stop() }
        for (ch, prog) in InternalSynth.programs { synth.sendProgramChange(prog, onChannel: UInt8(ch)) }

        // --- Rendu par tranches, coupées aux instants des évènements ---
        let buffer = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat, frameCapacity: maxFrames)!
        var left = [Float](), right = [Float]()
        left.reserveCapacity(Int(totalFrames)); right.reserveCapacity(Int(totalFrames))
        var pos: AVAudioFramePosition = 0
        var idx = 0
        let drumCh = Int(InternalSynth.drumChannel)

        func send(_ e: MIDIEvent) {
            if kit != .gm && e.channel == drumCh {
                if e.kind == .noteOn { drums.trigger(note: e.data1, velocity: e.data2, kit: kit) }
                return
            }
            synth.sendMIDIEvent(e.statusByte, data1: UInt8(e.data1 & 0x7F), data2: UInt8(e.data2 & 0x7F))
        }

        while pos < totalFrames {
            while idx < events.count && frame(events[idx].tick) <= pos {
                send(events[idx]); idx += 1
            }
            // À la fin de la musique : on relâche tout ce qui tient encore.
            if pos >= musicFrames && idx >= events.count {
                for ch in 0..<16 { synth.sendMIDIEvent(0xB0 | UInt8(ch), data1: 123, data2: 0) }
                idx = Int.max / 2
            }
            var n = AVAudioFramePosition(maxFrames)
            if idx < events.count { n = min(n, max(1, frame(events[idx].tick) - pos)) }
            n = min(n, totalFrames - pos)
            let status: AVAudioEngineManualRenderingStatus
            do { status = try engine.renderOffline(AVAudioFrameCount(n), to: buffer) }
            catch { throw Failure.engine(error.localizedDescription) }
            guard status == .success, let ch = buffer.floatChannelData else {
                throw Failure.engine("rendu interrompu (\(status.rawValue))")
            }
            let got = Int(buffer.frameLength)
            left.append(contentsOf: UnsafeBufferPointer(start: ch[0], count: got))
            right.append(contentsOf: UnsafeBufferPointer(start: ch[min(1, Int(buffer.format.channelCount) - 1)], count: got))
            pos += AVAudioFramePosition(got)
        }

        // --- Boucle parfaite : la queue est repliée sur le début ---
        if seamless {
            let m = Int(musicFrames)
            if m > 0 && left.count > m {
                for i in m..<left.count {
                    left[i % m] += left[i]
                    right[i % m] += right[i]
                }
                left.removeSubrange(m...)
                right.removeSubrange(m...)
            }
        } else {
            // One-shot : on coupe le silence superflu en fin de queue.
            var end = left.count
            while end > Int(musicFrames) && max(abs(left[end - 1]), abs(right[end - 1])) < 1e-5 { end -= 1 }
            left.removeSubrange(end...)
            right.removeSubrange(end...)
        }

        // --- Normalisation à -1 dBFS ---
        var peak: Float = 0
        for i in left.indices { peak = max(peak, abs(left[i]), abs(right[i])) }
        let target: Float = powf(10, -1 / 20)
        let g: Float = peak > 0 ? target / peak : 1
        try write(left: left, right: right, gain: g, to: url)
        return Result(seconds: Double(left.count) / sampleRate, peakBefore: peak)
    }

    @inline(__always) static func put(_ b: inout [UInt8], _ o: Int, _ x: Float) {
        let v = Int32((max(-1, min(1, x)) * 8_388_607).rounded())
        b[o] = UInt8(truncatingIfNeeded: v)
        b[o + 1] = UInt8(truncatingIfNeeded: v >> 8)
        b[o + 2] = UInt8(truncatingIfNeeded: v >> 16)
    }

    /// WAV PCM 24 bits stéréo 48 kHz.
    static func write(left: [Float], right: [Float], gain: Float, to url: URL) throws {
        let n = left.count
        var d = Data(capacity: 44 + n * 6)
        func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        func u16(_ v: UInt16) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        d.append(contentsOf: Array("RIFF".utf8)); u32(UInt32(36 + n * 6))
        d.append(contentsOf: Array("WAVE".utf8))
        d.append(contentsOf: Array("fmt ".utf8)); u32(16); u16(1); u16(2)
        u32(UInt32(sampleRate)); u32(UInt32(sampleRate) * 6); u16(6); u16(24)
        d.append(contentsOf: Array("data".utf8)); u32(UInt32(n * 6))
        var bytes = [UInt8](repeating: 0, count: n * 6)
        for i in 0..<n {
            put(&bytes, i * 6, left[i] * gain)
            put(&bytes, i * 6 + 3, right[i] * gain)
        }
        d.append(contentsOf: bytes)
        try d.write(to: url, options: .atomic)
    }
}
