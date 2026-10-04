# Screenshots

Save terminal captures here, then reference them from the main
[README](../../README.md).

## Shots to capture

Take these three. Use **Win + Shift + S** on Windows, drag over the terminal,
then paste into Paint and save as PNG with the exact filename listed.

| Filename | What to capture | Why it matters |
| --- | --- | --- |
| `memory-and-reset.png` | Telling the bot your name, it answering correctly, then `/reset`, then it failing to recall — with the `tokens in` numbers visible on both | The single best piece of evidence in the project. Shows memory is re-sending, not recalling. |
| `session-stats.png` | The `/stats` output, including the line reporting what share of tokens were input | Demonstrates the cost tracking the brief asks for. |
| `error-handling.png` | Any handled failure, e.g. running with an invalid `GEMINI_API_KEY` and getting the HTTP 401 message | Shows the tool degrades gracefully instead of dumping a traceback. |

## Before you capture

Make the output readable and safe:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cls
```

- Increase the terminal font with **Ctrl + Shift + +** a few times. Text that looks
  slightly too big on screen reads correctly in an image.
- **Close your `.env` tab.** If your API key appears in a screenshot, it is
  effectively public and must be rotated.
- Check no file tree or tab bar in the shot exposes anything private.

## Adding them to the README

Once saved, add to the Demo section of the main README:

```markdown
![Memory and reset](docs/screenshots/memory-and-reset.png)
![Session stats](docs/screenshots/session-stats.png)
![Error handling](docs/screenshots/error-handling.png)
```
