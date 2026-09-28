# Experimental TV-led Dolby Vision ambilight

Keep standard **TV-led Dolby Vision** on the TV while using the same HDMI source for ambilight through an **EZCOO SP12H21**, **Elgato 4K X**, and **HyperHDR**.

One tested setup produced moving capture with substantially corrected colors. This is an experimental transport patch plus an approximate software color conversion. It is not a complete Dolby Vision decoder, a Dolby-certified implementation, or a universal splitter firmware release.

## Tested setup

```text
NVIDIA Shield TV Pro 2019 → Onkyo TX-NR7100 → EZCOO SP12H21
                                             ├─ OUT1 → LG C1 (TV-led DV)
                                             └─ OUT2 → Elgato 4K X → HyperHDR → Hue
```

- Shield movie output: 3840×2160 at 23.976Hz; low-latency DV preference off.
- Splitter: COPY EDID (reported preset 37); both physical scalers off.
- Receiver: HDMI4/SLI11, HSF02, MAIN output.
- Capture: Linux V4L2 NV12,1920×1080 at 60 fps; HyperHDR quarter-frame mode.
- TV reported standard DV (`Dolby HDR Info[2]`, RGB8 tunnel); the receiver independently reported Dolby Vision with RGB24 total bits.

The full observed boundaries and pending checks are in [validation.md](docs/validation.md). No other hardware revision, capture card, 4K120/VRR path or source device is claimed supported.

## What changes

**Firmware transport:** the patch routes capture output 2 through a unity processing path, suppresses Dolby vendor signalling there, and relabels the capture-facing AVI transport as YCbCr4:2:2. Output 1 continues carrying standard DV. The patch does not implement pixel color decoding, change EDID, or change HDCP handling.

**Software color:** the captured components are interpreted using a fixed IPT/PQ→RGB model rather than ordinary YUV. A generated HyperHDR LUT replaces only the HDR-YUV segment. SDR-YUV and HDR-RGB segments are preserved exactly. The live experiment uses HPE LMS with 4% crosstalk, PQ, Rec.709 output, per-channel Reinhard tone compression and sRGB encoding. Exact source matrix/range and dynamic metadata handling remain unresolved; see [color limitations](docs/color.md).

A key firmware bug was a depth-unit mismatch: the stock RX routine stores24/30/36/48 total bits per pixel, not8/10/12/16 bits per component. Comparing the RGB8 tunnel against 8 rejected it. The final patch compares 24, with a regression test executing the actual stock ARM routine under modeled hardware I/O.

## Offline setup and tests

Python 3.10+ and GNU Arm embedded binutils (`arm-none-eabi-as `, `ld `, `objcopy `) are required for firmware builds. NumPy, Unicorn and PyUSB are listed in requirements.txt.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python color/test_color.py
python color/test_mode_guard.py
python firmware/test_dfu_install.py
```

These commands do not contact devices. Firmware-image integration tests require local verified image files; see [building](docs/building.md). No vendor firmware dumps, bootloader images, prebuilt flashable release, personal configurations or film captures are included.

## Generate a color LUT offline

Supply a backup of an existing uncompressed three-segment HyperHDR LUT (150,994,944 bytes):

```sh
OPENBLAS_NUM_THREADS=1 python color/build_lut.py   --input /path/to/original-lut.3d --output /path/to/new-ipt-lut.3d
```

Verify the entire generated table independently with:

```sh
OPENBLAS_NUM_THREADS=1 python color/verify_lut.py --original /path/to/original-lut.3d --generated /path/to/new-ipt-lut.3d
```

The output must not already exist. Generation does not install the LUT or change HyperHDR. Preserve your original LUT before any manual deployment. The HDR-YUV segment is now specific to this experiment; enabling it for ordinary HDR10 or LLDV is incorrect.

## Optional LG mode guard

`color/mode_guard.py ` is an example for a rooted LG exposing the tested HDMI status format. It polls TV status and changes only HyperHDR's runtime HDR component. It requires two positive observations before enabling IPT and disables it on nonmatching or unavailable status. It does not turn the grabber or lights on.

Set these environment variables before running:

- `TVLED_SSH_HOST `: an SSH alias with existing trusted-host authentication.
- `TVLED_LG_PORT `: internal proc port, default2. Internal and physical port numbering may differ; verify on your TV.
- `TVLED_LUT_PATH `: installed LUT path, default `~/.hyperhdr/lut_lin_tables.3d `.
- `TVLED_LUT_SHA256`: SHA256 of your generated/installed full LUT.
- `HYPERHDR_URL `: JSON-RPC URL, default `http://127.0.0.1:8090/json-rpc `.

```sh
python color/mode_guard.py
```

The example expects a locally accessible API without token authentication. Stopping it normally disables runtime HDR. It is not a general TV detection service. See [recovery](docs/recovery.md) before any firmware work.

## Evidence and collaboration

Physical observations, simulation results and numerical checks are distinguished in [validation.md](docs/validation.md). The LUT math was independently checked over 16,777,216 entries within one rounding step; that establishes implementation consistency, not source-format conformance or lamp calibration.

Development and reverse-engineering work were AI-assisted, with physical device measurements, verified readbacks and retained tests. Please provide exact hardware/firmware identities and reproducible observations when reporting results. Do not include credentials or full personal configuration dumps.

Thanks and references: [xnappo's EZCOO firmware tools](https://github.com/xnappo/ez_dv_edid_fw), [HyperHDR](https://github.com/awawa-dev/HyperHDR), and [libplacebo](https://github.com/haasn/libplacebo). Detailed provenance is in [REFERENCES.md](REFERENCES.md).
