# Line by Line Language Study

Read a book in a foreign language on your phone, one sentence per screen: the original sentence, its translation, and a word-by-word (or phrase-by-phrase) gloss underneath. All AI work happens once, offline, on your own PC with a free local model. The phone app is a static page with no AI, no backend, and no subscription.

> **Short description (for the GitHub "About" field):**
> Offline PWA for learning a language by reading books sentence by sentence, with translation and per-word gloss. Content is prepared once with a local LLM (Ollama); no cloud AI, no fees.

## How it works

```
book.html / .txt  ->  scripts/prepare.py (local Ollama model)  ->  data/book.json
                                                                       |
                                  copy the file to your phone (USB / Drive / Quick Share)
                                                                       v
                         app/ (static PWA hosted on GitHub Pages)  ->  Import book.json
```

1. **Prepare (PC, one time per book):** split the text into sentences, translate each one with a local model, and generate a gloss (single words, or multi-word phrases when words only make sense together).
2. **Read (phone):** the app stores the book in the phone's own storage, works offline, and remembers your position.

## Features

- One sentence per screen, font size auto-fits so there is no scrolling (a scroll fallback exists only for extremely long sentences)
- Original sentence, full translation, and aligned gloss pairs
- Neutral colors, centered text, light and dark mode
- Swipe or tap to move; reading position is saved between sessions
- Source and target languages set in one config file (default target: English)
- Resumable preparation: every finished sentence is cached, so you can stop and continue at any time

## Requirements

- Windows PC (other systems should work, but the commands below are for Windows)
- [Python 3.10+](https://www.python.org/downloads/)
- [Ollama](https://ollama.com) with a model pulled, for example `ollama pull gpt-oss:20b`
- An Android or iOS phone with Chrome or Safari
- A GitHub account (for free hosting with GitHub Pages)

## Project layout

```
config.json              languages, model, folders
requirements.txt         Python dependencies (pysbd)
scripts/
  prepare.py             split + translate + gloss -> data/book.json
  html_to_txt.py         optional: extract <p> paragraphs from an HTML book into source/
  count_sentences.py     optional: count sentences to estimate run time
app/                     the reader (static PWA)
  index.html  manifest.json  sw.js  icon-192.png  icon-512.png
source/                  your book as .txt files, one per chapter (not committed)
data/                    cache and output (not committed)
```

## Setup

```powershell
cd C:\work\code\line_by_line_language_study
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Preparing a book

1. Put the text in `source/` as `.txt` files, one per chapter, with blank lines between paragraphs. If your book is HTML with `<p>` paragraphs and chapter headings in `<h3>`:
   ```powershell
   python scripts\html_to_txt.py "C:\path\to\book.html" --split h3
   ```
   Check the first file: title pages and copyright notices are extracted too, so delete what is not part of the story.
2. Edit `config.json` (see below).
3. Make sure Ollama is running, then test on a few sentences:
   ```powershell
   python scripts\prepare.py --limit 5
   ```
4. Run everything: `python scripts\prepare.py`. Press Ctrl+C at any time; running the same command again continues where it stopped.
5. The result is `data/book.json`. It is only written when the run finishes or is interrupted.

To process only some chapters, temporarily move the other `.txt` files out of `source/`. Finished sentences stay cached.

**Speed:** each sentence is a separate model call. Measure with `--limit 20` and multiply by the number of sentences. With a 20B reasoning model it can be tens of seconds per sentence, so a full book may take many hours. It is safe to run overnight (disable Windows sleep while it runs).

### config.json

| Key | Meaning |
|---|---|
| `title` | Book title stored in `book.json` |
| `source_lang`, `source_code` | Source language name (used in the prompt) and its ISO code (used by the sentence splitter) |
| `target_lang` | Translation language (default `English`) |
| `model`, `ollama_url` | Local model name and Ollama address |
| `num_ctx` | Context window passed to Ollama |
| `think` | Reasoning effort for models that support it; delete the key if your model rejects it |
| `input_dir`, `output_dir` | Folders for source text and results |
| `char_map` | Character replacements applied to the text (default fixes Romanian diacritics; empty it for other languages) |

Sentences that fail validation after three attempts are listed in `data/failures.log` and shown in the app without a gloss. They are retried on the next run.

### data/book.json

```json
{
  "title": "...", "source_lang": "Romanian", "source_code": "ro", "target_lang": "English",
  "chapters": [
    { "title": "ch01 ...", "sentences": [
      { "s": "original sentence", "t": "translation", "g": [["word", "meaning"], ["...", "..."]] }
    ] }
  ]
}
```

A sentence with `"c": 1` failed validation and should be reviewed.

## Using the app

1. **Test on your PC:** `copy data\book.json app\book.json`, then
   ```powershell
   cd app
   python -m http.server 8000
   ```
   Open `http://localhost:8000`. Delete `app\book.json` afterwards.
2. **Publish the app** (see below), open the site on your phone, choose ☰ then **Import book.json**, and pick the file you copied to the phone. The book is stored on the phone and works offline.
3. Install it: Chrome menu, **Add to Home screen**.

**Controls:** swipe left or tap the left side to go forward; swipe right or tap the right side to go back. Arrow keys work on a PC. To flip the tap and key direction, change `NEXT_SIDE` at the top of the script in `app/index.html`. The menu (☰) has chapter and sentence jump, a gloss on/off switch, and import.

## Publishing to GitHub Pages

PWAs need HTTPS, which GitHub Pages provides for free. GitHub Pages serves the repository root or a `/docs` folder, so choose one:

- **Option A: separate repository for the app only.** Create a public repo, push only the contents of `app/`, then enable Pages on the `main` branch, `/ (root)`.
- **Option B: one repository for the whole project.** Rename `app/` to `docs/`, push everything, and enable Pages on the `main` branch, `/docs`.

Either way, the site will be at `https://USERNAME.github.io/REPO-NAME/`. If you later change the app, commit and push again. If the phone still shows the old version, close the app completely and reopen it.

## Copyright

Do not publish book text that is protected by copyright. The `.gitignore` excludes `source/`, `data/`, and `book.json`. Keep it that way: the public repository should contain code only, and the book travels to your phone privately as a file.

## Troubleshooting

- **`CUDA error` or crash in Ollama:** update Ollama and the NVIDIA driver, and try a smaller model.
- **Very slow:** run `ollama ps` while it works and check that the model is on the GPU; close browsers to free video memory, or try a smaller model without a reasoning phase.
- **The app shows an old version:** close it fully and reopen, or clear the site data in Chrome (this also removes the imported book, so import it again).
- **Wrong sentence splits:** check the text for stray line breaks and for quote characters that do not match; fix them in `source/` and delete `data/cache.jsonl` to redo the affected sentences.
