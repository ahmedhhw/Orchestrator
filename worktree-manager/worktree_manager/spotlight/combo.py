"""
Pure (zero Qt / Carbon imports) combo-string parser.

parse_combo(seq: str) -> (keycode: int, modmask: int)

Carbon modifier masks:
  cmdKey    = 0x100
  shiftKey  = 0x200
  optionKey = 0x800
  controlKey= 0x1000

Note: Qt uses "Ctrl" to mean Cmd on macOS in QKeySequence.  We follow the same
convention: "Ctrl" in a combo string → cmdKey in the Carbon mask.
"""

# Carbon modifier bit-masks
_CMD_KEY    = 0x100
_SHIFT_KEY  = 0x200
_OPTION_KEY = 0x800
_CTRL_KEY   = 0x1000

MODIFIERS: dict[str, int] = {
    "Ctrl":   _CMD_KEY,    # Qt "Ctrl" → macOS Cmd (Cmd/⌘)
    "Meta":   _CMD_KEY,    # Qt "Meta" → macOS Cmd on some platforms
    "Cmd":    _CMD_KEY,
    "Shift":  _SHIFT_KEY,
    "Alt":    _OPTION_KEY,
    "Option": _OPTION_KEY,
}

# kVK_ANSI_* virtual key codes (from <Carbon/Events.h>)
KEYCODES: dict[str, int] = {
    "A":      0x00,
    "S":      0x01,
    "D":      0x02,
    "F":      0x03,
    "H":      0x04,
    "G":      0x05,
    "Z":      0x06,
    "X":      0x07,
    "C":      0x08,
    "V":      0x09,
    "B":      0x0B,
    "Q":      0x0C,
    "W":      0x0D,
    "E":      0x0E,
    "R":      0x0F,
    "Y":      0x10,
    "T":      0x11,
    "1":      0x12,
    "2":      0x13,
    "3":      0x14,
    "4":      0x15,
    "6":      0x16,
    "5":      0x17,
    "Equal":  0x18,
    "9":      0x19,
    "7":      0x1A,
    "Minus":  0x1B,
    "8":      0x1C,
    "0":      0x1D,
    "P":      0x23,
    "L":      0x25,
    "J":      0x26,
    "K":      0x28,
    "N":      0x2D,
    "M":      0x2E,
    "O":      0x1F,
    "U":      0x20,
    "I":      0x22,
    "Return": 0x24,
    "Tab":    0x30,
    "Space":  0x31,
    "Delete": 0x33,
    "Escape": 0x35,
}


def parse_combo(seq: str) -> tuple[int, int]:
    """Parse a Qt-style shortcut string into a (keycode, modmask) pair.

    >>> parse_combo("Ctrl+K")
    (40, 256)
    >>> parse_combo("Ctrl+Shift+Space")
    (49, 512)

    Raises ValueError if no modifier is present or if a token is unrecognised.
    """
    parts = seq.split("+")
    *mod_parts, key_part = parts

    if not mod_parts:
        raise ValueError(
            f"shortcut needs a modifier (e.g. Ctrl+K), got: {seq!r}"
        )

    mask = 0
    for m in mod_parts:
        if m not in MODIFIERS:
            raise ValueError(f"unknown modifier {m!r} in combo {seq!r}")
        mask |= MODIFIERS[m]

    if key_part not in KEYCODES:
        raise ValueError(f"unknown key {key_part!r} in combo {seq!r}")

    return KEYCODES[key_part], mask
