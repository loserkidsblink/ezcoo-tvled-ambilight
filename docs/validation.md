# Validation status — 2026-09-28

## Physically observed

On the README's exact stack, output 1 preserved standard TV-led Dolby Vision and output 2 provided moving Elgato capture. The final firmware was read back twice after flashing and matched the built image. The RGB8 eligibility correction changed two bytes from the earlier rejected v1 image.

Receiver: Dolby Vision,3840×2160 at 23 Hz reported (Shield23.976Hz), RGB24 total bits. LG: Dolby HDR Info2, R444,8BIT, locked link. In a temporary diagnostic connection, output 2 independently showed Y422 without Dolby signalling; it was subsequently restored to Elgato.

The installed LUT corrected the major green/magenta hue errors. The observer reported better lamp colors. Six live-preview/TV comparisons and six raw-capture/TV comparisons sampled multiple scenes from one animated film. Raw capture samples were read without stopping the capture process; buffers changing during reads were rejected. Screenshots and raw film frames are intentionally not published here.

## Offline checks

- 1291 linked-ARM hook cases, with modeled packet/register I/O.
- Actual stock RX routine returns 24/30/36/48 for the four modeled hardware depth codes. Regression reproduces v1 rejection and corrected routing/filtering/AVI behavior.
- Nine NOR/DFU simulator tests, including interrupted programming and rollback.
- Independent numerical evaluation of all 16,777,216 LUT cells: maximum one output-code difference due to coefficient rounding. Neutral ramp is neutral and monotonic; PQ neutral landmarks pass.
- Original SDR-YUV and HDR-RGB LUT segments preserved exactly.
- Mode guard unit tests reject non-DV, LLDV, wrong format/depth, disconnected/unlocked/muted status.

Archived numerical summaries are adjacent JSON files. Software simulation is not physical hardware validation. Generic matrix consistency is not evidence of exact Dolby decoding.

## Still unverified

- Other source devices, splitter firmware/board revisions and capture cards.
- Different DV profiles/titles, other refresh rates, 4K120 and VRR.
- Controlled physical SDR/HDR10/LLDV↔standard-DV transitions and restart/recovery endurance.
- Exact source color matrix/range/reshape assumptions and TV screenshot color encoding.
- Calibrated panel-to-lamp accuracy and dynamic Dolby metadata processing.

Initial publication is an experimental source package. It is not a broadly validated flashable release.
