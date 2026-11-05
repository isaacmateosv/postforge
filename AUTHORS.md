# Authors and acknowledgements

## Orchestration

- **Isaac Mateo Sarzosa Valencia** ([isaacmateosv](https://github.com/isaacmateosv)) — project
  orchestration, product direction, operational decisions, integration
  configuration, testing, and release ownership.

## AI-assisted collaboration

- **GitHub Copilot using Copilot SDK in VS Code** — implementation assistance,
  investigation, test design, documentation, and release-safety review.
- **Anthropic Claude** — collaborative implementation, review, and
  documentation assistance.

AI systems are collaborators and tools used by the orchestrator. They are not
copyright holders, legal authors, maintainers, or licensors of this repository.

- **OpenAI Codex** — implementation, debugging, verification and release assistance.

## Open-source components

PostForge is an orchestration layer around these independent projects.
Their names, source code, licenses, and trademarks remain theirs:

- [Postiz](https://github.com/gitroomhq/postiz) — social publishing UI,
  integrations, drafts, and scheduling surface.
- [Evolution API](https://github.com/EvolutionAPI/evolution-api) — WhatsApp
  gateway used by the local worker.
- [Baileys](https://github.com/WhiskeySockets/Baileys) — WhatsApp Web protocol
  library used by the Evolution stack.
- [Temporal](https://github.com/temporalio/temporal) — durable workflow
  scheduling.
- [PostgreSQL](https://www.postgresql.org/), [Redis](https://redis.io/), and
  [Ollama](https://github.com/ollama/ollama) — persistence, queue/session
  state, and local model serving.
- [ngrok](https://github.com/ngrok/ngrok) — optional public tunnel client.
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) — optional local
  voice-note transcription.

Consult each project’s repository and image metadata for the exact license and
version terms applicable to a deployment. This file is an acknowledgement, not
a claim that these projects endorse PostForge.
