import BangCore
import Foundation
import Network

/// Journal des messages OSC (entrée / sortie) pour le moniteur.
struct OSCLogEntry: Identifiable, Equatable {
    let id = UUID()
    let time: Date
    let incoming: Bool
    let text: String
}

/// OSC bidirectionnel en UDP : émission vers `host:txPort`, réception sur
/// `rxPort`. Thread-safe (file série), utilisable depuis l'horloge.
final class OSCLink: @unchecked Sendable {
    private let queue = DispatchQueue(label: "bang.osc")
    private var tx: NWConnection?
    private var txKey = ""
    private var listener: NWListener?
    private var rxPort: UInt16 = 0
    private let lock = NSLock()
    private var _log: [OSCLogEntry] = []
    /// Noms des voix (index → label), pour /bang/<voix> pendant la lecture.
    private var labels: [String] = []
    private var txOn = false

    /// Message reçu (appelé sur la file OSC).
    var onReceive: (@Sendable (OSCMessage) -> Void)?

    var log: [OSCLogEntry] { lock.lock(); defer { lock.unlock() }; return _log }

    private func append(_ incoming: Bool, _ m: OSCMessage) {
        let text = m.address + (m.args.isEmpty ? "" : " " + m.args.map(\.text).joined(separator: " "))
        lock.lock()
        _log.insert(OSCLogEntry(time: Date(), incoming: incoming, text: text), at: 0)
        if _log.count > 80 { _log.removeLast(_log.count - 80) }
        lock.unlock()
    }

    func setLabels(_ l: [String]) { lock.lock(); labels = l; lock.unlock() }
    func label(_ i: Int) -> String? { lock.lock(); defer { lock.unlock() }; return labels.indices.contains(i) ? labels[i] : nil }

    /// Configure l'émission (nil = coupée).
    func configureTX(host: String?, port: UInt16) {
        queue.async { [self] in
            let key = host.map { "\($0):\(port)" } ?? ""
            lock.lock(); txOn = host != nil; lock.unlock()
            guard key != txKey else { return }
            tx?.cancel(); tx = nil; txKey = key
            guard let host, !host.isEmpty, let p = NWEndpoint.Port(rawValue: port) else { return }
            let c = NWConnection(host: NWEndpoint.Host(host), port: p, using: .udp)
            c.start(queue: queue)
            tx = c
        }
    }

    var transmitting: Bool { lock.lock(); defer { lock.unlock() }; return txOn }

    /// Configure la réception (0 = coupée). Retourne via `done` une erreur éventuelle.
    func configureRX(port: UInt16, done: (@Sendable (String?) -> Void)? = nil) {
        queue.async { [self] in
            guard port != rxPort || (port != 0 && listener == nil) else { done?(nil); return }
            listener?.cancel(); listener = nil; rxPort = port
            guard port != 0, let p = NWEndpoint.Port(rawValue: port) else { done?(nil); return }
            do {
                let params = NWParameters.udp
                params.allowLocalEndpointReuse = true
                let l = try NWListener(using: params, on: p)
                l.newConnectionHandler = { [weak self] conn in
                    conn.start(queue: self?.queue ?? .main)
                    self?.receive(on: conn)
                }
                l.stateUpdateHandler = { [weak self, weak l] state in
                    if case .failed(let e) = state {
                        // Port occupé, etc. : on oublie cet écouteur pour qu'une
                        // nouvelle activation retente au lieu de rester bloquée.
                        if let self, self.listener === l { self.listener = nil; self.rxPort = 0 }
                        l?.cancel()
                        done?("port \(port) : \(e.localizedDescription)")
                    }
                    if case .ready = state { done?(nil) }
                }
                l.start(queue: queue)
                listener = l
            } catch {
                done?("port \(port) : \(error.localizedDescription)")
            }
        }
    }

    private func receive(on conn: NWConnection) {
        conn.receiveMessage { [weak self] data, _, _, error in
            guard let self else { return }
            if let data {
                for m in OSCMessage.decode(data) {
                    self.append(true, m)
                    self.onReceive?(m)
                }
            }
            if error == nil { self.receive(on: conn) }
        }
    }

    func send(_ m: OSCMessage, log: Bool = true) {
        queue.async { [self] in
            guard let tx else { return }
            tx.send(content: m.encode(), completion: .contentProcessed { _ in })
            if log { append(false, m) }
        }
    }
}

/// Pont vers Ableton Live via AbletonOSC (port 11000). On émet depuis le
/// port local 11001 : les réponses d'AbletonOSC y arrivent, qu'elles soient
/// renvoyées à l'expéditeur ou au port 11001 par défaut.
final class AbletonLink: @unchecked Sendable {
    private let queue = DispatchQueue(label: "bang.ableton")
    private var conn: NWConnection?
    private var key = ""
    private var waiting: [String: (OSCMessage) -> Void] = [:]
    /// Échec de la liaison (ex. port local 11001 déjà pris) — appelé sur la file Ableton.
    var onFailure: (@Sendable (String) -> Void)?

    private func connection(host: String, port: UInt16) -> NWConnection? {
        let k = "\(host):\(port)"
        if k == key, let conn { return conn }
        conn?.cancel()
        guard let p = NWEndpoint.Port(rawValue: port) else { return nil }
        let params = NWParameters.udp
        params.allowLocalEndpointReuse = true
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "0.0.0.0", port: 11001)
        let c = NWConnection(host: NWEndpoint.Host(host), port: p, using: params)
        c.stateUpdateHandler = { [weak self, weak c] state in
            guard let self, case .failed(let e) = state else { return }
            // On oublie la liaison morte : le prochain envoi en recrée une.
            if self.conn === c { self.conn = nil; self.key = "" }
            c?.cancel()
            self.onFailure?("liaison impossible (port local 11001 déjà utilisé ?) : \(e.localizedDescription)")
        }
        c.start(queue: queue)
        conn = c
        key = k
        listen(c)
        return c
    }

    private func listen(_ c: NWConnection) {
        c.receiveMessage { [weak self] data, _, _, error in
            guard let self else { return }
            if let data {
                for m in OSCMessage.decode(data) {
                    if let cb = self.waiting.removeValue(forKey: m.address) { cb(m) }
                }
            }
            if error == nil, c === self.conn { self.listen(c) }
        }
    }

    func send(_ messages: [OSCMessage], host: String, port: UInt16) {
        queue.async { [self] in
            guard let c = connection(host: host, port: port) else { return }
            for m in messages { c.send(content: m.encode(), completion: .contentProcessed { _ in }) }
        }
    }

    /// Demande le tempo de Live ; `done(nil)` si pas de réponse.
    func queryTempo(host: String, port: UInt16, timeout: Double = 1.0, done: @escaping @Sendable (Double?) -> Void) {
        queue.async { [self] in
            guard let c = connection(host: host, port: port) else { done(nil); return }
            var answered = false
            waiting["/live/song/get/tempo"] = { m in
                answered = true
                done(m.args.first?.number)
            }
            c.send(content: OSCMessage("/live/song/get/tempo").encode(), completion: .contentProcessed { _ in })
            queue.asyncAfter(deadline: .now() + timeout) { [self] in
                if !answered { waiting["/live/song/get/tempo"] = nil; done(nil) }
            }
        }
    }
}
