# INV4048 - Accessible Video Description Research

This repository brings together the software prototypes, experiments, evaluation materials, and research artifacts developed for **INV4048**. The work explores accessible audiovisual experiences through automatic video segmentation, speaker diarization, prosodic analysis, and AI-generated audio descriptions in Spanish and English.

> **Note:** This is a research workspace that contains several independent prototypes. Each module has its own dependencies, configuration, and level of maturity.

## Project scope

The repository supports an end-to-end research workflow:

1. Upload and manage videos through web applications.
2. Extract audio, identify speakers, and locate speech and silence intervals.
3. Segment videos using diarization and scene-change detection.
4. Generate visual descriptions with multiple AI providers.
5. Enrich descriptions with prosodic and emotional information.
6. Evaluate outputs using spreadsheets, annotations, figures, and comparison documents.

## Repository map

| Folder | Contents |
| --- | --- |
| `Back_taller/` | Python/Flask backend for the Video Segments Player. It provides authentication, project management, and video-segment REST endpoints backed by MongoDB. |
| `Back_tallerjs/` | JavaScript/Node.js serverless backend variant, prepared for deployment on Vercel. |
| `Taller_Front/` | React frontend for the video-segment player and its user interface. |
| `Testfront/` | Frontend prototypes and tests for video-segment playback and interaction. |
| `back integracion/` | Integrated processing service that combines video upload, diarization, segmentation, descriptions, Google Drive storage, and MongoDB metadata. |
| `clip/` | Experimental video segmentation, scene-detection, keyframe, and CLIP-based analysis scripts, including several model and workflow variants. |
| `descripciones/` | Video-description experiments, HTML prototypes, XML/CSV utilities, notebooks, input segments, and generated outputs for OpenAI, Gemini, Claude, and Grok. |
| `Codigos descripciones/` | Focused Spanish- and English-language description-generation scripts for OpenAI, Gemini, Claude, and Grok, including prosodic narration support. |
| `Prueba de TTS Association/` | Text-to-speech association experiments, diarization/transcription tests, dialogue extraction, audio samples, and spreadsheets. |
| `pyanntoe final/` | Speaker-diarization and scene-aware silence-detection pipeline, with a notebook, source code, JSON annotations, and its own README. |
| `INV4048 EXCELS/` | Evaluation workbooks, model-comparison data, annotations, research documents, diagrams, and figures. |

## Main technologies

- **Python:** Flask, MoviePy, PyDub, OpenCV, PySceneDetect, PyTorch, pyannote, and related analysis libraries.
- **JavaScript:** Node.js, React, Vite, Express/serverless functions, and Vercel.
- **AI services:** OpenAI, Google Gemini, Anthropic Claude, xAI Grok, and pyannoteAI.
- **Storage and services:** MongoDB, Google Drive, and FFmpeg-based media processing.
- **Research artifacts:** Jupyter notebooks, JSON annotations, XLSX workbooks, DOCX documents, CSV files, XML exports, and figures.

## Running the components

There is no single installation command for the entire workspace. Start from the module you need:

- Python services and scripts use their local `requirements.txt` files.
- JavaScript applications use their local `package.json` files.
- Detailed setup information is available in the READMEs inside `Back_taller/`, `Back_tallerjs/`, `back integracion/`, `descripciones/`, `Codigos descripciones/`, and `pyanntoe final/`.

Most media-processing workflows require **FFmpeg**. Cloud-backed workflows also require valid API credentials and, where applicable, access to MongoDB and Google Drive.

## Data, outputs, and security

Some folders contain large videos, audio, model outputs, Python virtual environments, Node.js dependencies, and generated build files. These are useful locally but should normally **not** be committed to GitHub.

Before publishing, exclude at least:

```text
.env
credentials.json
node_modules/
env/
.venv/
__pycache__/
dist/
*.mp4
*.mov
*.avi
*.wav
*.mp3
```

Do not upload API keys, Google credentials, tokens, database connection strings, or participant/source media without the appropriate authorization. Keep only source code, lightweight sample data, configuration templates such as `.env.example`, documentation, and selected evaluation artifacts in the public repository.

## Related documentation

- The diarization pipeline is documented in [`pyanntoe final/README.md`](pyanntoe%20final/README.md).
- The Flask API is documented in [`Back_taller/README.md`](Back_taller/README.md).
- The Vercel backend is documented in [`Back_tallerjs/README-VERCEL.md`](Back_tallerjs/README-VERCEL.md).
- The integrated workflow is documented in [`back integracion/README.md`](back%20integracion/README.md).

## Status

The repository is a collection of research and development artifacts. Individual folders represent different experiments, prototypes, and implementation stages rather than one production-ready application.
