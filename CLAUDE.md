# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository currently contains **no source code** — only [Konzept.md](Konzept.md), a German-language concept document. There is no build system, no dependency manifest, no tests, and no CI to run yet. Do not invent build/lint/test commands; none exist. When implementation begins, this file should be updated with the actual toolchain and commands.

## What this project is

The goal (per [Konzept.md](Konzept.md)) is an AI-assisted display-reading system for a calibration lab:

- A Raspberry Pi 5 with a Raspberry Pi AI Camera (Sony IMX500) optically reads the displays of changing measurement amplifiers (e.g. GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI, and AST devices from Dresden).
- Recognized values are continuously streamed over a serial interface to **GSVmulti** (ME-Systeme's data acquisition software).
- The device under test (DUT) and the calibration machine's reference must be time-correlated as closely as possible, even though devices, display types, camera positions, and framing change regularly.
- LLMs / generative AI are explicitly **not** part of the live measurement path — this is a computer-vision/OCR + classical rule-checking pipeline, operator-guided rather than fully autonomous (at least initially).

## Intended architecture (from the concept doc)

The proposed processing chain, in order:

1. Capture a camera frame plus its metadata.
2. Automatically localize the relevant display (small object detector).
3. Rectify perspective/rotation and enhance contrast (OpenCV) on the display crop.
4. Recognize digits, sign, decimal point, unit, and relevant status indicators (specialized OCR / small character model; classical 7-segment decoding as a complementary check).
5. Validate the result against readability, syntax, and allowed operating states.
6. Attach capture timestamp, sequence number, and quality/confidence status to the value.
7. Convert to the format GSVmulti accepts via a separate protocol adapter.
8. Stream continuously over serial and log diagnostics locally.

Localization and OCR are not expected to run at the same rate — after initial setup, the confirmed display region can be tracked, with re-localization triggered on position changes.

### Candidate tools/components (not yet chosen/validated)

| Concern | Candidate |
| --- | --- |
| Camera access | Picamera2, libcamera, rpicam-apps |
| Image processing | OpenCV, NumPy |
| Display localization | Small YOLO/SSD-family detector or corner-point model |
| OCR (prototyping) | Tesseract, PaddleOCR, or a specialized digit recognizer |
| Custom models | PyTorch or TensorFlow, runtime TBD |
| Serial output | Python + pyserial |
| Long-running operation | systemd, watchdog, bounded buffers, diagnostic logs |
| Device configuration | JSON profiles |

The IMX500 sensor can run compatible neural nets on-camera; the plan is to build/measure the pipeline on the Pi 5 first, then evaluate moving display localization (or another suitable stage) onto the IMX500. A generic OCR model cannot be transferred to the sensor unmodified — it needs proper quantization/conversion/packaging.

### Internal record fields (draft, not a confirmed GSVmulti telegram)

`frame_sequence`, `capture_timestamp`, `value`, `unit`, `status` (valid / transitioning / unreadable / stale), `confidence`, `profile_id`, `trigger_sequence`, `result_timestamp`.

### Key constraints to keep in mind when implementing

- **No silent smoothing/correction**: recognition must not use the reference value to "correct" the DUT reading, and real value jumps must not be smoothed away by plausibility rules.
- **Stale/invalid values must be marked, never carried forward silently** as current valid values when tracking/recognition is lost.
- **Timing is subtle**: a steady serial output rate does not by itself imply synchronism with the reference. Capture timestamp, display update/hold time, exposure/readout timing, OCR latency, and serial transmission delay are all distinct and need to be accounted for separately (see Konzept.md §6).
- **Model confidence ≠ error probability** — acceptance thresholds must be validated against real, including previously unseen, device types, and unreadable/unknown input must be explicitly rejected rather than guessed at.
- Physical serial connection must not tie Pi GPIO levels directly to RS-232; galvanic isolation needs evaluation for the lab setup.

### Open protocol/hardware questions (unresolved — check before implementing the serial adapter)

- Exact GSVmulti version and the serial format/telegram it accepts (baud rate, framing, delimiters, decimal separator, unit/channel handling, device identification/init commands).
- Whether GSVmulti honors an embedded capture timestamp or only records receive time.
- Physical link choice (USB-serial adapter vs. UART + RS-232/RS-485 transceiver vs. virtual USB-COM) — not guaranteed available on Pi 5 by default.

## Working in this repo

Since there is no code yet, early work here is likely to involve scaffolding a new Python project (per the candidate tool list: Picamera2/libcamera, OpenCV, pyserial). When you add the first source files, also add to this CLAUDE.md: how to install dependencies, how to run the pipeline/tests, and any hardware-specific setup (camera enablement, serial device permissions) required on the Raspberry Pi.
