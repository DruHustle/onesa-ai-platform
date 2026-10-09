# Node runtime

Container builds use Node 24.21.0, selected from the [official Node release metadata](https://nodejs.org/dist/index.json) (Node 24 LTS) on 2026-10-09. Host checks also passed with the installed Node 20.20.1; prefer the pinned container runtime or Node 24 for new environments. The final container build/browser checks validate the selected runtime.
