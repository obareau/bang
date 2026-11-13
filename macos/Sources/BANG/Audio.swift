import AVFoundation
import AudioToolbox
import CoreMIDI
import Foundation

/// Sortie CoreMIDI : un port virtuel « BANG! » (visible dans Ableton, Logic,
/// SuperCollider…) + envoi direct vers une destination matérielle choisie.
final class MIDIOut: @unchecked Sendable {
    struct Destination: Identifiable, Hashable {
        let id: MIDIUniqueID
        let name: String
    }

    private var client = MIDIClientRef()
    private var port = MIDIPortRef()
    private var source = MIDIEndpointRef()
    private let lock = NSLock()
    private var destination: MIDIEndpointRef = 0
    private var virtualEnabled = true
    var onSetupChanged: (() -> Void)?

    init() {
        MIDIClientCreateWithBlock("BANG!" as CFString, &client) { [weak self] notif in
            if notif.pointee.messageID == .msgSetupChanged {
                DispatchQueue.main.async { self?.onSetupChanged?() }
            }
        }
        MIDIOutputPortCreate(client, "BANG! out" as CFString, &port)
        MIDISourceCreateWithProtocol(client, "BANG!" as CFString, ._1_0, &source)
    }

    static func destinations() -> [Destination] {
        (0..<MIDIGetNumberOfDestinations()).compactMap { i in
            let ep = MIDIGetDestination(i)
            var uid: MIDIUniqueID = 0
            MIDIObjectGetIntegerProperty(ep, kMIDIPropertyUniqueID, &uid)
            var name: Unmanaged<CFString>?
            MIDIObjectGetStringProperty(ep, kMIDIPropertyDisplayName, &name)
            guard let n = name?.takeRetainedValue() as String? else { return nil }
            return Destination(id: uid, name: n)
        }
    }

    func select(_ uid: MIDIUniqueID?) {
        var ep: MIDIEndpointRef = 0
        if let uid {
            var type: MIDIObjectType = .other
            var obj: MIDIObjectRef = 0
            if MIDIObjectFindByUniqueID(uid, &obj, &type) == noErr, type == .destination { ep = obj }
        }
        lock.lock(); destination = ep; lock.unlock()
    }

    func setVirtual(_ on: Bool) {
        lock.lock(); virtualEnabled = on; lock.unlock()
    }

    func send(_ status: UInt8, _ d1: UInt8, _ d2: UInt8) {
        lock.lock()
        let dest = destination, virt = virtualEnabled
        lock.unlock()
        guard dest != 0 || virt else { return }
        // UMP MIDI 1.0 channel voice (message type 0x2, groupe 0)
        var word: UInt32 = 0x2000_0000 | UInt32(status) << 16 | UInt32(d1 & 0x7F) << 8 | UInt32(d2 & 0x7F)
        var list = MIDIEventList()
        withUnsafeMutablePointer(to: &list) { lp in
            let pk = MIDIEventListInit(lp, ._1_0)
            _ = MIDIEventListAdd(lp, MemoryLayout<MIDIEventList>.size, pk, 0, 1, &word)
            if dest != 0 { MIDISendEventList(port, dest, lp) }
            if virt { MIDIReceivedEventList(source, lp) }
        }
    }
}

/// Synthé General MIDI intégré (DLS d'Apple) — pour entendre BANG! sans
/// aucun matériel. Multitimbral : canal 10 = batterie, autres canaux = GM.
final class InternalSynth: @unchecked Sendable {
    private let engine = AVAudioEngine()
    private let synth: AVAudioUnitMIDIInstrument
    private let reverb = AVAudioUnitReverb()
    private(set) var running = false

    /// Programmes GM par canal (0-based), alignés sur Voice.defaultChannel.
    private static let programs: [Int: UInt8] = [
        0: 38,   // Synth Bass 1   — basses / Bass ♩
        1: 80,   // Square Lead    — Markov
        2: 81,   // Saw Lead       — KSP Lead
        3: 33,   // Finger Bass    — KSP Bass
        4: 89,   // Warm Pad       — KSP Chord
        5: 4,    // E.Piano        — KSP Arp
        6: 118,  // Synth Drum     — Volca Kick
        7: 5,    // E.Piano 2 (FM) — Volca FM
        8: 87,   // Bass + Lead    — MicroFreak
    ]

    init() {
        let desc = AudioComponentDescription(componentType: kAudioUnitType_MusicDevice,
                                             componentSubType: kAudioUnitSubType_DLSSynth,
                                             componentManufacturer: kAudioUnitManufacturer_Apple,
                                             componentFlags: 0, componentFlagsMask: 0)
        synth = AVAudioUnitMIDIInstrument(audioComponentDescription: desc)
        reverb.loadFactoryPreset(.mediumRoom)
        reverb.wetDryMix = 14
        engine.attach(synth)
        engine.attach(reverb)
        engine.connect(synth, to: reverb, format: nil)
        engine.connect(reverb, to: engine.mainMixerNode, format: nil)
    }

    func start() {
        guard !running else { return }
        do {
            try engine.start()
            running = true
            for (ch, prog) in Self.programs { synth.sendProgramChange(prog, onChannel: UInt8(ch)) }
        } catch {
            NSLog("BANG! synthé interne indisponible : \(error)")
        }
    }

    func stop() {
        guard running else { return }
        engine.stop()
        running = false
    }

    func send(_ status: UInt8, _ d1: UInt8, _ d2: UInt8) {
        guard running else { return }
        synth.sendMIDIEvent(status, data1: d1, data2: d2)
    }
}
