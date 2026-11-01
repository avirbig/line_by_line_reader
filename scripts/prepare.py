#!/usr/bin/env python3
"""Offline preparation: split text -> translate + gloss with a local Ollama model -> data/book.json.

Usage (from the project root, venv active):
    python scripts/prepare.py --limit 5     # quick test on 5 new sentences
    python scripts/prepare.py               # full run; safe to stop (Ctrl+C) and resume
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = {
    "type": "object",
    "properties": {
        "translation": {"type": "string"},
        "gloss": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"src": {"type": "string"}, "tgt": {"type": "string"}},
                "required": ["src", "tgt"],
            },
        },
    },
    "required": ["translation", "gloss"],
}


def normalize(text, cfg):
    text = text.replace("\r\n", "\n")
    for a, b in cfg.get("char_map", {}).items():
        text = text.replace(a, b)
    return text


def paragraphs(text):
    paras = re.split(r"\n\s*\n", text)
    if len(paras) == 1:  # no blank lines: treat each line as a paragraph
        paras = text.split("\n")
    paras = [re.sub(r"\s+", " ", p).strip() for p in paras]
    return [p for p in paras if p]


def unbalanced(s):
    return s.count('"') % 2 == 1 or s.count("„") > s.count("”") or s.count("«") > s.count("»")


def split_sentences(par, code):
    try:
        import pysbd
        sents = pysbd.Segmenter(language=code, clean=False).segment(par)
    except Exception:  # unsupported language or pysbd missing: simple fallback
        sents = re.findall(r'[^.!?…]+[.!?…]+["»”)]*|[^.!?…]+$', par)
    out = []
    for s in (x.strip() for x in sents):
        if not s:
            continue
        if out and unbalanced(out[-1]):  # don't cut inside a quotation
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def squash(s):
    return re.sub(r"\s+", "", s)


def valid(sentence, res):
    try:
        gloss = res["gloss"]
        return (
            bool(res["translation"].strip())
            and len(gloss) > 0
            and squash("".join(x["src"] for x in gloss)) == squash(sentence)
        )
    except (KeyError, TypeError, AttributeError):
        return False


def ask(cfg, paragraph, sentence, note=""):
    src, tgt = cfg["source_lang"], cfg["target_lang"]
    prompt = f"""You are a {src}-to-{tgt} translator and dictionary for language learners.

Paragraph (context only):
{paragraph}

Sentence to process:
{sentence}

Return JSON with:
- "translation": a natural {tgt} translation of the sentence.
- "gloss": the sentence split into consecutive segments, in order. Each segment is {{"src": exact text taken from the sentence, "tgt": its {tgt} meaning in this context}}.
Rules: one word per segment, EXCEPT group words into a single segment when they only make sense together (idioms, phrasal, reflexive or auxiliary verb constructions, particles, and conjunctions or function words that lose their meaning alone). Keep punctuation attached to the neighbouring word. Joining all "src" values with spaces must reproduce the sentence exactly; skip nothing. {note}"""
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0.2, "num_ctx": cfg.get("num_ctx", 8192)},
    }
    if cfg.get("think"):
        body["think"] = cfg["think"]
    req = urllib.request.Request(
        cfg["ollama_url"].rstrip("/") + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.load(r)
    return json.loads(data["message"]["content"])


def process(cfg, para, sent, out_dir):
    """Translate + gloss one sentence. Returns a dict; 'c': 1 marks it for manual review."""
    note, res = "", {}
    for _ in range(3):
        try:
            res = ask(cfg, para, sent, note)
            if valid(sent, res):
                return {
                    "s": sent,
                    "t": res["translation"].strip(),
                    "g": [[x["src"], x["tgt"]] for x in res["gloss"]],
                }
            note = "The previous answer did not reproduce the sentence exactly from the segments. Copy the sentence text exactly."
        except urllib.error.URLError:
            raise  # Ollama not reachable: stop instead of burning through the book
        except Exception as e:
            print("  error:", e, file=sys.stderr)
            time.sleep(2)
    with open(out_dir / "failures.log", "a", encoding="utf-8") as fh:
        fh.write(sent + "\n")
    t = res.get("translation", "") if isinstance(res, dict) else ""
    return {"s": sent, "t": t, "g": [[w, ""] for w in sent.split()], "c": 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="process at most N new sentences (for testing)")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(exist_ok=True)
    cache_path = out_dir / "cache.jsonl"
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                cache[d["k"]] = d["v"]

    files = sorted((ROOT / cfg["input_dir"]).glob("*.txt"))
    if not files:
        sys.exit(f"No .txt files found in {cfg['input_dir']}/")

    chapters, new, start, stop = [], 0, time.time(), False
    try:
        for f in files:
            ch = {"title": f.stem, "sentences": []}
            chapters.append(ch)
            text = normalize(f.read_text(encoding="utf-8-sig"), cfg)
            for para in paragraphs(text):
                for sent in split_sentences(para, cfg["source_code"]):
                    key = hashlib.sha1(
                        f"{cfg['source_code']}|{cfg['target_lang']}|{sent}".encode("utf-8")
                    ).hexdigest()
                    if key not in cache:
                        if args.limit and new >= args.limit:
                            stop = True
                            break
                        cache[key] = process(cfg, para, sent, out_dir)
                        if not cache[key].get("c"):  # failed sentences are retried on the next run
                            with open(cache_path, "a", encoding="utf-8") as fh:
                                fh.write(json.dumps({"k": key, "v": cache[key]}, ensure_ascii=False) + "\n")
                        new += 1
                        print(f"[{f.stem}] {new} done, {(time.time() - start) / new:.1f}s/sentence", flush=True)
                    ch["sentences"].append(cache[key])
                if stop:
                    break
            if stop:
                break
    finally:
        book = {
            "title": cfg["title"],
            "source_lang": cfg["source_lang"],
            "source_code": cfg["source_code"],
            "target_lang": cfg["target_lang"],
            "chapters": [c for c in chapters if c["sentences"]],
        }
        (out_dir / "book.json").write_text(json.dumps(book, ensure_ascii=False), encoding="utf-8")
        total = sum(len(c["sentences"]) for c in book["chapters"])
        print(f"Wrote {out_dir / 'book.json'} ({total} sentences)")


if __name__ == "__main__":
    main()
