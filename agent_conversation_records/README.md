# Agent Conversation Records

This folder contains readable HTML/Markdown renderings of the two Codex sessions used for the dataset-augmented AI-agent analysis.

The raw Codex JSONL files are archived as `raw_codex_session_jsonl.zip`. The readable HTML/Markdown files are public-safe renderings for inspection, while `export_manifest.csv` and `checksums_sha256.csv` record the session ID, file size, line count, and SHA-256 checksum for each raw log.

Private workstation paths are replaced with placeholders in the public renderings:

- `[PUBLIC_REPO]`: this public repository root.
- `[ANALYSIS_WORKSPACE]`: local working folder used by the analysis agents.
- `[PROJECT_WORKSPACE]`: local project workspace used during manuscript preparation.
- `[CODEX_SESSION_LOGS]`: local Codex raw session log directory.
- `[USER_HOME]`: local user home directory.

Local figure references that appeared in the conversation are exported into `rendered_transcripts/assets/` and rewritten as relative links. Large raster figures are converted into browser-friendly display copies with white backgrounds and capped dimensions; the original source figures remain preserved in the raw analysis archive.

Ordinary local file references to CSV, Python, Markdown, PDF, or other analysis files are rendered as blue non-clickable local-file references. They are intentionally not copied into the HTML package, because the full raw analysis folder is preserved separately in the raw archive.

## Rendered Sessions

- `019e5a99-d4b4-7b33-9c00-74b8d0f6c184`: `rendered_transcripts/019e5a99-d4b4-7b33-9c00-74b8d0f6c184.html`
- `019eb222-0283-7721-a3de-1c69905a9035`: `rendered_transcripts/019eb222-0283-7721-a3de-1c69905a9035.html`
