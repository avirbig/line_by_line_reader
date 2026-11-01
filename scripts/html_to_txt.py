#!/usr/bin/env python3
"""Extract <p> paragraphs from HTML file(s) into source/chNN <title>.txt.
--split h3 starts a new chapter at each <h3> and uses its text as the chapter title."""
import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Extract(HTMLParser):
    def __init__(self, split):
        super().__init__(convert_charrefs=True)
        self.split = split
        self.chapters = []              # list of (title, paragraphs)
        self.cur, self.title = [], ""
        self.in_p, self.buf = False, []
        self.in_h, self.hbuf = None, []

    def handle_starttag(self, tag, attrs):
        if tag in self.split:
            self.flush()
            self.in_h, self.hbuf = tag, []
        elif tag == "p":
            self.in_p, self.buf = True, []
        elif tag == "br" and self.in_p:
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag == self.in_h:
            self.title = re.sub(r"\s+", " ", "".join(self.hbuf)).strip()
            self.in_h = None
        elif tag == "p" and self.in_p:
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if t:
                self.cur.append(t)
            self.in_p = False

    def handle_data(self, data):
        if self.in_h:
            self.hbuf.append(data)
        elif self.in_p:
            self.buf.append(data)

    def flush(self):
        if self.cur:
            self.chapters.append((self.title, self.cur))
        self.cur, self.title = [], ""

    def close(self):
        super().close()
        self.flush()


def read(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1250"):  # cp1250 covers old Romanian encodings
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("--split", default="", help="comma-separated heading tags that start a new chapter, e.g. h3")
args = ap.parse_args()

out = ROOT / "source"
out.mkdir(exist_ok=True)
n = 0
for f in args.files:
    p = Extract(set(filter(None, args.split.split(","))))
    p.feed(read(Path(f)))
    p.close()
    for title, paras in p.chapters:
        n += 1
        safe = re.sub(r'[\\/:*?"<>|]', "", title)[:60].strip()
        name = f"ch{n:02d} {safe}.txt" if safe else f"ch{n:02d}.txt"
        (out / name).write_text("\n\n".join(paras), encoding="utf-8")
        print(f"{name}: {len(paras)} paragraphs")