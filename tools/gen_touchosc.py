#!/usr/bin/env python3
"""
Génère le fichier TouchOSC (.tosc) pour contrôler BANG!

Format : ZIP archive contenant index.xml (TouchOSC v2+ / Hexler)
Usage  : python3 gen_touchosc.py [--host IP] [--tx-port N] [--rx-port N] [--out fichier.tosc]
"""
import zipfile
import uuid
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Dimensions (points iPad Pro 12.9" landscape) ──────────────────────────
W, H = 1366, 1024

# ── Couleurs RGBA 0.0–1.0 ─────────────────────────────────────────────────
AMBER  = (1.00, 0.67, 0.00, 1.0)
DIM    = (1.00, 0.67, 0.00, 0.45)
BG     = (0.05, 0.05, 0.03, 1.0)
BG2    = (0.10, 0.10, 0.06, 1.0)
GREEN  = (0.18, 0.78, 0.45, 1.0)
RED    = (0.95, 0.35, 0.35, 1.0)
GREY   = (0.35, 0.35, 0.35, 1.0)


def uid() -> str:
    return str(uuid.uuid4()).upper()


# ── Helpers propriétés ────────────────────────────────────────────────────

def prop_s(parent, name, val):
    p = ET.SubElement(parent, "property", name=name, type="s")
    ET.SubElement(p, "value").text = str(val)


def prop_i(parent, name, val):
    p = ET.SubElement(parent, "property", name=name, type="i")
    ET.SubElement(p, "value").text = str(int(val))


def prop_f(parent, name, val):
    p = ET.SubElement(parent, "property", name=name, type="f")
    ET.SubElement(p, "value").text = f"{float(val):.6f}"


def prop_b(parent, name, val):
    p = ET.SubElement(parent, "property", name=name, type="b")
    ET.SubElement(p, "value").text = "1" if val else "0"


def prop_r(parent, name, x, y, w, h):
    p = ET.SubElement(parent, "property", name=name, type="r")
    for k, v in (("x", x), ("y", y), ("w", w), ("h", h)):
        ET.SubElement(p, k).text = f"{float(v):.6f}"


def prop_c(parent, name, rgba):
    r, g, b, a = rgba
    p = ET.SubElement(parent, "property", name=name, type="c")
    for k, v in (("r", r), ("g", g), ("b", b), ("a", a)):
        ET.SubElement(p, k).text = f"{float(v):.6f}"


# ── Message OSC ───────────────────────────────────────────────────────────

def osc_msg(node, path, send=True, receive=False, feedback=False):
    msgs = node.find("messages")
    if msgs is None:
        msgs = ET.SubElement(node, "messages")
    msg = ET.SubElement(msgs, "message", type="OSC")
    ET.SubElement(msg, "enabled").text  = "1"
    ET.SubElement(msg, "send").text     = "1" if send     else "0"
    ET.SubElement(msg, "receive").text  = "1" if receive  else "0"
    ET.SubElement(msg, "feedback").text = "1" if feedback else "0"
    path_el = ET.SubElement(msg, "path")
    ET.SubElement(path_el, "pathPart", type="constant").text = path
    args = ET.SubElement(msg, "arguments")
    ET.SubElement(args, "argument", type="auto")
    return msg


# ── Contrôles ─────────────────────────────────────────────────────────────

def _node(children, ntype, name, x, y, w, h):
    n = ET.SubElement(children, "node", ID=uid(), type=ntype)
    p = ET.SubElement(n, "properties")
    prop_r(p, "frame", x, y, w, h)
    prop_s(p, "name", name)
    prop_b(p, "visible", True)
    prop_b(p, "interactive", True)
    return n, p


def add_label(children, text, x, y, w, h, size=24, color=AMBER):
    n, p = _node(children, "LABEL", text, x, y, w, h)
    prop_s(p, "text", text)
    prop_f(p, "textSize", size)
    prop_i(p, "textAlignH", 1)   # 0=left 1=center 2=right
    prop_c(p, "color", color)
    prop_b(p, "background", False)
    prop_b(p, "outline", False)
    return n


def add_fader(children, name, path, x, y, w, h,
              mn=0.0, mx=1.0, horiz=True, color=AMBER):
    n, p = _node(children, "FADER", name, x, y, w, h)
    prop_i(p, "orientation", 0 if horiz else 1)
    prop_f(p, "valueRange.x", mn)
    prop_f(p, "valueRange.y", mx)
    prop_f(p, "value.default", mn)
    prop_c(p, "color", color)
    prop_c(p, "colorBackground", BG2)
    osc_msg(n, path)
    return n


def add_button(children, name, path, x, y, w, h,
               toggle=False, color=GREEN):
    n, p = _node(children, "BUTTON", name, x, y, w, h)
    prop_i(p, "buttonType", 1 if toggle else 0)  # 0=momentary 1=toggle
    prop_s(p, "text", name)
    prop_f(p, "textSize", 22.0)
    prop_c(p, "color", color)
    prop_c(p, "colorBackground", BG2)
    osc_msg(n, path)
    return n


def add_sep(children, x, y, w):
    n, p = _node(children, "LABEL", "_sep_", x, y, w, 2)
    prop_s(p, "text", "")
    prop_c(p, "color", GREY)
    prop_b(p, "background", True)
    prop_b(p, "outline", False)


# ── Page 1 — PARAMS ───────────────────────────────────────────────────────

def build_page1(pager_ch):
    pg, pp = _node(pager_ch, "PAGE", "PARAMS", 0, 0, W, H)
    prop_s(pp, "tabLabel", "PARAMS")
    prop_c(pp, "colorBackground", BG)
    ch = ET.SubElement(pg, "children")

    add_label(ch, "BANG!  PARAMS", 0, 8, W, 54, size=38)
    add_sep(ch, 40, 68, W - 80)

    params = [
        ("BPM",     "/bang/param/bpm",        40,  200),
        ("CHAOS",   "/bang/param/chaos",        0,    1),
        ("GRAVITY", "/bang/param/gravity",      0,    1),
        ("SWING",   "/bang/param/swing",        0,    1),
        ("MICRO",   "/bang/param/microtiming",  0,    1),
        ("CC DEP.", "/bang/param/cc_depth",     0,    1),
    ]
    FH, GAP, LFT, TOP = 80, 12, 40, 80
    LW = 160
    FW = W - LFT - LW - 80

    for i, (name, path, mn, mx) in enumerate(params):
        y = TOP + i * (FH + GAP)
        add_label(ch, name, LFT, y + 24, LW, 32, size=20, color=DIM)
        add_fader(ch, name, path, LFT + LW, y, FW, FH, mn, mx)

    sep_y = TOP + len(params) * (FH + GAP) + 10
    add_sep(ch, 40, sep_y, W - 80)

    BW, BH = 280, 110
    by = sep_y + 20
    add_button(ch, "GENERER", "/bang/generate", LFT,           by, BW, BH, color=AMBER)
    add_button(ch, "VARIER",  "/bang/vary",     LFT + BW + 20, by, BW, BH, color=DIM)

    return pg


# ── Page 2 — VOIX ─────────────────────────────────────────────────────────

def build_page2(pager_ch):
    pg, pp = _node(pager_ch, "PAGE", "VOIX", 0, 0, W, H)
    prop_s(pp, "tabLabel", "VOIX")
    prop_c(pp, "colorBackground", BG)
    ch = ET.SubElement(pg, "children")

    add_label(ch, "BANG!  VOIX", 0, 8, W, 54, size=38)
    add_sep(ch, 40, 68, W - 80)

    voices = [
        ("Kick",   "/bang/density/Kick"),
        ("Snare",  "/bang/density/Snare"),
        ("HiHat",  "/bang/density/HiHat"),
        ("Bass",   "/bang/density/Bass"),
        ("Markov", "/bang/density/Markov"),
    ]
    FH, GAP, LFT, TOP = 96, 10, 40, 80
    LW = 140
    FW = 800

    add_label(ch, "DENSITY", LFT + LW, TOP - 2, FW, 32, size=18, color=DIM)

    for i, (name, path) in enumerate(voices):
        y = TOP + 34 + i * (FH + GAP)
        add_label(ch, name, LFT, y + 28, LW, 36, size=20, color=DIM)
        add_fader(ch, name, path, LFT + LW, y, FW, FH)

    TX = LFT + LW + FW + 30
    TW = W - TX - 30
    TH = FH
    add_label(ch, "LOCK", TX, TOP - 2, TW, 32, size=18, color=DIM)

    for i, (name, _) in enumerate(voices[:4]):
        y = TOP + 34 + i * (FH + GAP)
        add_button(ch, name, f"/bang/lock/{i}", TX, y, TW, TH,
                   toggle=True, color=RED)

    sep_y = TOP + 34 + len(voices) * (FH + GAP) + 10
    add_sep(ch, 40, sep_y, W - 80)
    add_label(ch, "STEPS", 0, sep_y + 14, W, 34, size=20, color=DIM)

    SW, SH, SGAP = 260, 120, 20
    total_sw = 4 * SW + 3 * SGAP
    sx = (W - total_sw) // 2
    sy = sep_y + 52
    for i, val in enumerate([16, 32, 64, 128]):
        x = sx + i * (SW + SGAP)
        add_button(ch, str(val), "/bang/param/steps", x, sy, SW, SH,
                   toggle=False, color=AMBER)

    return pg


# ── Racine ────────────────────────────────────────────────────────────────

def build(host: str, tx_port: int, rx_port: int) -> ET.Element:
    root = ET.Element("lexml", version="3.0.0")

    conn_el = ET.SubElement(root, "connections")
    ET.SubElement(conn_el, "connection",
                  type="OSC",
                  host=host,
                  sendPort=str(rx_port),    # TouchOSC sends TO BANG!'s rx port
                  receivePort=str(tx_port), # TouchOSC receives FROM BANG! on tx port
                  enabled="1")

    pager, pp = _node(root, "PAGER", "bang", 0, 0, W, H)
    prop_c(pp, "colorBackground", BG)
    prop_i(pp, "tabbar.visible", 1)
    prop_i(pp, "tabbar.size", 60)
    pager_ch = ET.SubElement(pager, "children")

    build_page1(pager_ch)
    build_page2(pager_ch)

    return root


# ── Écriture ZIP ──────────────────────────────────────────────────────────

def write_tosc(root: ET.Element, path: str):
    try:
        ET.indent(root, space="  ")
    except AttributeError:
        pass   # Python < 3.9
    xml_bytes = ET.tostring(root, encoding="unicode")
    xml_full  = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.xml", xml_full.encode("utf-8"))

    size = Path(path).stat().st_size
    print(f"✓ {path}  ({size:,} octets)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Génère le dashboard TouchOSC pour BANG!")
    ap.add_argument("--host",    default="192.168.1.100", help="IP du serveur BANG!")
    ap.add_argument("--tx-port", type=int, default=57120,  help="Port TX (BANG! → TouchOSC)")
    ap.add_argument("--rx-port", type=int, default=57121,  help="Port RX (TouchOSC → BANG!)")
    ap.add_argument("--out",     default="bang_control.tosc")
    a = ap.parse_args()

    root_el = build(a.host, a.tx_port, a.rx_port)
    write_tosc(root_el, a.out)
    print(f"  Host    : {a.host}")
    print(f"  TX port : {a.tx_port}  (BANG! clock → TouchOSC)")
    print(f"  RX port : {a.rx_port}  (TouchOSC → BANG!)")
    print("\n  Config TouchOSC :")
    print(f"    Settings → Connections → OSC")
    print(f"    Host={a.host}  Send port={a.rx_port}  Receive port={a.tx_port}")
