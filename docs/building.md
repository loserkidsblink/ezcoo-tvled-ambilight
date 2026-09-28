# Firmware build inputs

The source patch is specific to this exact application image and address layout. Renaming an incompatible image does not make it compatible. Do not remove hash/address assertions to make a build succeed.

Place your independently obtained application image at `firmware/STOCK-readback.bin `:

- Size: 0x1b000 bytes (110,592).
- Application address: 0x08004000 through0x0801f000 exclusive.
- SHA256: `ad3bd3805885527a0aadb092e520a2c3c408dc3251385411a4fc5dd8f7ca59df `.

```sh
python firmware/build.py
```

Expected output SHA256: `efc27e3ef3079c346f8afcc6df5dd524077163770647f0b84c5b0e2d0ca7084d `.

The assembler inserts four branch hooks and a bounded extension into verified unused space; overwritten bytes and image identity are checked. Building never opens USB. A manifest records the exact patch bytes and comparison baseline. Generated binaries are ignored by Git.

For historical regression tests, also supply:

| File | SHA256 |
|---|---|
| WORKING-lldv-rollback.bin | b6f8cc855f3a6db106c1c9b32acbf4a44f54b953cb18864def3fae64e616ec0c |
| INSTALLED-tvled-v1.bin | 43c9edf1cadb4e5866bd531c3dc971222929fa8262606de25690b3200c4fe48b |

Both are 110,592-byte application images from the tested development history. They are not distributed in this source repository. The builder uses the working LLDV image as an optional page-comparison baseline when present; otherwise it compares against stock.

```sh
python firmware/test_candidate.py
python firmware/test_depth_regression.py
FIRMWARE_REAL_IMAGES=1 python firmware/test_dfu_install.py
```

The hook suite executes linked ARM instructions with modeled hardware and board state. It does not emulate the HDMI processing chip, link training, color reconstruction or a whole firmware boot. Archived scoped results are in docs/.
