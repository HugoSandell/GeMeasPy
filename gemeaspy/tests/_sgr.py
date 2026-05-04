"""Contains a function to apply ANSI Select Graphic Rendition (SGR) escape codes to a string for printing to a terminal"""
from collections.abc import Collection, Iterable
import os
import sys

if sys.platform == "win32":
    os.system("")  # To ensure ANSI colours work

USE_COLOR = sys.stdout.isatty()

CLR_BLACK_FG = 30
CLR_RED_FG = 31
CLR_GREEN_FG = 32
CLR_YELLOW_FG = 33
CLR_BLUE_FG = 34
CLR_MAGENTA_FG = 35
CLR_CYAN_FG = 36
CLR_WHITE_FG = 37

STYLE_REGULAR = 0
STYLE_BOLD = 1
STYLE_DIM = 2
STYLE_ITALIC = 3
STYLE_UNDERLINE = 4
STYLE_STRIKETHROUGH = 9

def with_sgr(text: str, style: Iterable[int] | int | None = None) -> str:
    ESC = "\033["
    if not USE_COLOR:
        return text
    
    code = STYLE_REGULAR
    if isinstance(style, int):
        code = str(style)
    elif isinstance(style, str):
        code = style
    elif isinstance(style, Iterable):
        code = ";".join(map(lambda x: str(x), style))
    
    return f"{ESC}{code}m{text}{ESC}0m"

if __name__ == "__main__":
    # Demo / test
    def print_ansi(text: str, style: Iterable[int] | int | None = None):
        print("This is " + with_sgr(text, style) + ", right?")

    colors = {
        "Black": CLR_BLACK_FG,
        "Red": CLR_RED_FG,
        "Green": CLR_GREEN_FG,
        "Yellow": CLR_YELLOW_FG,
        "Blue": CLR_BLUE_FG,
        "Magenta": CLR_MAGENTA_FG,
        "Cyan": CLR_CYAN_FG,
        "White": CLR_WHITE_FG,
    }

    styles = {"Bold": STYLE_BOLD, 
              "Dim": STYLE_DIM, 
            "Italic": STYLE_ITALIC, 
            "Underlined": STYLE_UNDERLINE, 
            "Strikethrough": STYLE_STRIKETHROUGH}

    print_ansi("Plain")
    
    for c in colors:
        print_ansi(c, colors[c])
        
    for s in styles:
        print_ansi(s, styles[s])
    
    for i in range(min(len(colors), len(styles))):
        c = list(colors.keys())[i]
        s = list(styles.keys())[i]
        print_ansi(f"{c} and {s}", (styles[s], colors[c]))