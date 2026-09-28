# Color conversion: established math, unverified source assumptions

The generic IPT matrix and HPE LMS basis follow libplacebo's IPT helpers, with 4% crosstalk. The pipeline subtracts 128 from captured chroma, normalizes 8-bit components by 255, converts IPT to nonlinear LMS, applies ST2084 PQ, converts linear LMS to Rec.709 RGB, clips negative channels, applies per-channel `x/(x+100)` tone compression in nits, and sRGB-encodes the result.

This is **not libplacebo's complete Dolby decoder**. That decoder consumes metadata-provided matrices, offsets and reshaping. Dolby's published IPT-PQ examples also include 2% crosstalk. A fixed generic IPT helper alone does not prove the Shield HDMI transport's exact matrix, range or reshaping behavior. This implementation consumes no dynamic Dolby metadata.

Direct raw Elgato captures compared with LG DISPLAY screenshots show correction of large hue substitutions across observed scenes. However, the LG PNGs have no color profile/transfer metadata. Earlier Shield screenshots were tagged DisplayP3 with an sRGB transfer curve; treating their RGB values as sRGB primaries gave misleading comparison scores. Asynchronous capture, scaling and motion processing also limit pixel correspondence. None of these screenshot comparisons constitute calibrated Delta E or emitted-light measurements.

The 8-bit USB feed and chroma subsampling lose information. The fixed tone curve, per-channel clipping and lamp gamut/brightness adjustments prevent exact reproduction. Existing HyperHDR/Hue calibration must be measured separately; do not assume a good preview proves a 1:1 lamp match.

The LUT file contains three 50,331,648-byte segments: HDR-RGB, HDR-YUV and SDR-YUV. Only the middle segment is replaced. Its byte index is `3*(Y +256*U +65536*V)`, with RGB output bytes. The original outer segments are preserved byte-for-byte.
