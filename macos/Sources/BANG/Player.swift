import BangCore
import Foundation

/// Horloge temps réel — l'équivalent natif de live_clock.LiveClock.
///
/// Un thread haute priorité rend un cycle complet du pattern à la fois
/// (aléa frais à chaque cycle : les `?`, le Markov et les drops varient d'un
/// tour à l'autre comme en live), puis envoie chaque évènement à son heure.
///
/// La position est une « tick » absolue (480 par noire) déduite d'une ancre :
/// - mode interne : l'ancre avance au BPM de la session ;
/// - mode synchro : chaque impulsion MIDI clock (24 par noire = 20 ticks)
///   recale l'ancre, et le tempo est la moyenne des derniers intervalles.
///
/// Modifications :
/// - `update` : effet immédiat (le reste du cycle est re-rendu) — éditions ;
/// - `queue(_:forCycle:)` : effet au début du cycle donné — actions de fin de
///   cycle (évolution, Song, morph…) demandées par `onCycle`, appelé un peu
///   avant chaque fin de cycle pour que le changement tombe sur le 1er temps.
final class Player: @unchecked Sendable {
    typealias Output = @Sendable (UInt8, UInt8, UInt8) -> Void

    private let lock = NSLock()
    private var pending: RenderInput?
    private var queued: (input: RenderInput, cycle: Int)?
    private var running = false
    private var generation = 0
    private var thread: Thread?

    // État lu par l'UI
    private var step = 0
    private var steps = 1
    private var cycle = 0
    private var hits: [Int: Double] = [:]

    // Synchro MIDI clock
    private var syncEnabled = false
    private var pulseCount = -1
    private var lastPulse: Double?
    private var intervals: [Double] = []
    private var anchor: (time: Double, tick: Double)?

    let output: Output
    /// Appelé (sur le thread de l'horloge) un peu avant la fin de chaque cycle,
    /// avec le numéro du cycle qui va commencer.
    var onCycle: (@Sendable (Int) -> Void)?

    init(output: @escaping Output) { self.output = output }

    var isRunning: Bool { lock.lock(); defer { lock.unlock() }; return running }

    func start(_ input: RenderInput) {
        lock.lock()
        guard !running else { lock.unlock(); return }
        running = true
        generation += 1
        let gen = generation
        pending = input
        queued = nil
        cycle = 0
        lock.unlock()
        let t = Thread { [weak self] in self?.loop(gen) }
        t.qualityOfService = .userInteractive
        t.name = "BANG! clock"
        thread = t
        t.start()
    }

    func stop() {
        lock.lock(); running = false; lock.unlock()
        thread = nil
    }

    func update(_ input: RenderInput) {
        lock.lock(); pending = input; lock.unlock()
    }

    /// Entrée à appliquer au début du cycle `c` (immédiatement si on y est déjà).
    func queue(_ input: RenderInput, forCycle c: Int) {
        lock.lock()
        if cycle >= c { pending = input } else { queued = (input, c) }
        lock.unlock()
    }

    /// (step courant, nb de steps, cycle, dernier hit par voix)
    func status() -> (Int, Int, Int, [Int: Double]) {
        lock.lock(); defer { lock.unlock() }
        return (step, steps, cycle, hits)
    }

    // MARK: - Synchro MIDI clock

    func setSync(_ on: Bool) {
        lock.lock()
        syncEnabled = on
        resetClockLocked()
        lock.unlock()
    }

    private func resetClockLocked() {
        pulseCount = -1
        lastPulse = nil
        intervals = []
        anchor = nil
    }

    /// Start (0xFA) : la prochaine impulsion sera le 1er temps.
    func clockStart() {
        lock.lock(); resetClockLocked(); lock.unlock()
    }

    /// Une impulsion MIDI clock (0xF8) reçue à l'instant `t` (secondes, horloge `now()`).
    func clockPulse(at t: Double) {
        lock.lock()
        defer { lock.unlock() }
        guard syncEnabled else { return }
        if let last = lastPulse {
            let dt = t - last
            if dt > 0.004 && dt < 0.2 {          // 12,5 à 625 BPM : plage plausible
                intervals.append(dt)
                if intervals.count > 24 { intervals.removeFirst() }
            }
        }
        if Player.debugClock && pulseCount % 24 == 23 {
            print(String(format: "PULSE n=%d ts=%.4f now=%.4f retard=%.1fms", pulseCount + 1, t, Player.now(), (Player.now() - t) * 1000))
        }
        lastPulse = t
        pulseCount += 1
        anchor = (t, Double(pulseCount) * Double(Renderer.ppq / 24))
    }

    /// Tempo mesuré sur l'horloge entrante (nil tant qu'il n'y en a pas).
    var clockBPM: Double? {
        lock.lock(); defer { lock.unlock() }
        guard intervals.count >= 4 else { return nil }
        let avg = intervals.reduce(0, +) / Double(intervals.count)
        return 60 / (avg * 24)
    }

    static func now() -> Double { Double(DispatchTime.now().uptimeNanoseconds) / 1e9 }
    static let debugClock = ProcessInfo.processInfo.environment["BANG_DEBUG_CLOCK"] == "1"

    // MARK: - Boucle

    private func takePending() -> RenderInput? {
        lock.lock(); defer { lock.unlock() }
        let p = pending
        pending = nil
        return p
    }

    private static func sorted(_ e: [MIDIEvent]) -> [MIDIEvent] {
        e.sorted { ($0.tick, $0.kind == .noteOn ? 1 : 0) < ($1.tick, $1.kind == .noteOn ? 1 : 0) }
    }

    private func loop(_ gen: Int) {
        guard var input = takePending() else { return }
        let tps = Renderer.ticksPerStep
        func spt(_ bpm: Int) -> Double { 60.0 / (Double(max(1, bpm)) * Double(Renderer.ppq)) }

        // Ancre du mode interne
        var freeSPT = spt(input.params.bpm)
        var freeTime = Player.now() + 0.03
        var freeTick = 0.0

        /// Position courante (ticks) et secondes par tick ; nil = en attente
        /// de la 1re impulsion d'horloge.
        func position(_ now: Double) -> (tick: Double, spt: Double)? {
            lock.lock()
            let sync = syncEnabled, a = anchor, iv = intervals
            lock.unlock()
            if sync {
                guard let a else { return nil }
                let s = iv.isEmpty ? freeSPT : iv.reduce(0, +) / Double(iv.count) / Double(Renderer.ppq / 24)
                return (a.tick + max(0, now - a.time) / s, s)
            }
            return (freeTick + (now - freeTime) / freeSPT, freeSPT)
        }

        var cycleNo = 0
        var cycleBase = 0
        var cycleTicks = max(1, input.params.steps) * tps
        var hookFired = false

        func render(_ inp: RenderInput, cycle c: Int) -> [MIDIEvent] {
            var i = inp
            i.cycle = c
            return Renderer.render(i, numSteps: i.params.steps, rng: Dice(), gate: 0.75).map {
                var e = $0; e.tick += cycleBase; return e
            }
        }

        var events = render(input, cycle: 0)
        var idx = 0
        /// Position jusqu'où les évènements ont été envoyés : un re-rendu repart
        /// de là (et pas de la position courante), pour ne jamais perdre une
        /// note pas encore jouée — ex. le 1er temps quand une mise à jour arrive
        /// juste après le changement de cycle.
        var dispatchedUpTo = -1.0
        var sounding: [Int: Int] = [:]  // (canal<<8 | note) → nb de note-on actifs

        func dispatch(_ e: MIDIEvent) {
            let key = e.channel << 8 | e.data1
            switch e.kind {
            case .noteOn:
                if Player.debugClock {
                    let n = Player.now()
                    print(String(format: "NOTE tick=%d pos=%.1f now=%.4f", e.tick, position(n)?.tick ?? -1, n))
                }
                sounding[key, default: 0] += 1
                if e.voice >= 0 {
                    lock.lock(); hits[e.voice] = Player.now(); lock.unlock()
                }
            case .noteOff:
                guard let n = sounding[key] else { return }  // jamais joué : on ignore
                if n <= 1 { sounding[key] = nil } else { sounding[key] = n - 1 }
            case .cc:
                break
            }
            output(e.statusByte, UInt8(e.data1), UInt8(e.data2))
        }

        while true {
            lock.lock(); let alive = running && generation == gen; lock.unlock()
            if !alive { break }

            var now = Player.now()

            // Édition → re-rendu du reste du cycle, depuis la position courante.
            if let fresh = takePending() {
                if let pos = position(now), fresh.params.bpm != input.params.bpm {
                    freeTick = pos.tick; freeTime = now
                }
                freeSPT = spt(fresh.params.bpm)
                input = fresh
                cycleTicks = max(1, input.params.steps) * tps
                let releases = events[idx...].filter { $0.kind == .noteOff }
                let ahead = render(input, cycle: cycleNo).filter { Double($0.tick) > dispatchedUpTo }
                events = Player.sorted(releases + ahead)
                idx = 0
            }

            guard let pos = position(now) else {
                Thread.sleep(forTimeInterval: 0.002)  // synchro : on attend l'horloge
                continue
            }
            var tick = pos.tick

            // Gros saut (veille, horloge externe relancée) : on se recale sur un cycle.
            if tick - Double(cycleBase) > Double(cycleTicks) * 2 || tick < Double(cycleBase) - Double(cycleTicks) {
                cycleBase = (Int(tick) / cycleTicks) * cycleTicks
                events = render(input, cycle: cycleNo).filter { Double($0.tick) >= tick }
                dispatchedUpTo = tick
                idx = 0
                hookFired = false
            }

            while idx < events.count && Double(events[idx].tick) <= tick {
                dispatch(events[idx])
                idx += 1
            }
            dispatchedUpTo = max(dispatchedUpTo, tick)

            lock.lock()
            steps = cycleTicks / tps
            step = min(steps - 1, max(0, (Int(tick) - cycleBase) / tps))
            cycle = cycleNo
            lock.unlock()

            // Prévenir un peu avant la fin du cycle (~120 ms, au plus un demi-cycle).
            let look = min(Double(cycleTicks) / 2, 0.12 / pos.spt)
            if !hookFired && tick >= Double(cycleBase + cycleTicks) - look {
                hookFired = true
                onCycle?(cycleNo + 1)
            }

            if tick >= Double(cycleBase + cycleTicks) {
                // Fin de cycle : ce qui déborde (ratchets, jitter, note-off) est conservé.
                let carry = Array(events[idx...])
                cycleBase += cycleTicks
                cycleNo += 1
                hookFired = false
                dispatchedUpTo = Double(cycleBase) - 0.5   // rien du nouveau cycle n'est encore parti
                let oldBPM = input.params.bpm
                lock.lock()
                cycle = cycleNo
                if let q = queued, q.cycle <= cycleNo { input = q.input; queued = nil }
                lock.unlock()
                if let fresh = takePending() { input = fresh }
                if input.params.bpm != oldBPM {
                    // Recaler l'ancre avec l'ancien tempo avant de changer de tempo.
                    freeTick = position(now)?.tick ?? tick
                    freeTime = now
                    freeSPT = spt(input.params.bpm)
                }
                cycleTicks = max(1, input.params.steps) * tps
                events = Player.sorted(carry + render(input, cycle: cycleNo))
                idx = 0
                continue
            }

            let nextTick = idx < events.count
                ? min(Double(events[idx].tick), Double(cycleBase + cycleTicks))
                : Double(cycleBase + cycleTicks)
            now = Player.now()
            tick = position(now)?.tick ?? tick
            let wait = (nextTick - tick) * pos.spt
            if wait > 0 { Thread.sleep(forTimeInterval: min(wait, 0.003)) }
        }

        // Arrêt : on relâche tout ce qui sonne + All Notes Off.
        for key in sounding.keys {
            output(0x80 | UInt8((key >> 8) & 0x0F), UInt8(key & 0x7F), 0)
        }
        for ch in 0..<16 { output(0xB0 | UInt8(ch), 123, 0) }
        lock.lock(); step = 0; hits = [:]; lock.unlock()
    }
}
