# Firmware installation and recovery boundaries

Firmware flashing can leave the splitter unable to display video. This repository's DFU helper is retained for reproducibility of the specific tested development path; it is **not a general stock-to-patched installer**.

Before considering flashing, keep verified independent backups of your exact device's application and bootloader, identify its board/firmware revision, and confirm a physical recovery path. Do not flash while playing content. Bootloader images and device backups are not included here.

The helper requires the exact candidate and historical WORKING-lldv-rollback.bin identities in building.md. It accepts the known working LLDV image, previous v1 or candidate as the installed state. It will refuse arbitrary stock or other images. Do not bypass these checks.

For the tested stale flash-layout descriptor, it additionally requires bootloader SHA256`d73d694f4b7cab429047ea17e9d15b8989b349cc45705182be97bc2e05a7f55c `. The protected bootloader region is never written.

Only after the prerequisites above are met, a fresh physical UPDATE/DFU session and `python firmware/ezcoo_dfu_install.py --execute ` perform the tested install. `--execute --rollback ` selects the verified historical LLDV image. Without `--execute `, the helper only checks local files and never opens USB.

The tested bootloader locks flash after programming: every required erase must happen before programming, in a fresh DFU session. The helper verifies erasure, programs changed application pages and compares two full readbacks. It does not mass-erase, write option bytes, or automatically reset the device. If verification fails, remain in DFU and use the documented verified recovery image in a fresh DFU session; do not boot an unverified image.

For software rollback, stop the optional mode guard, turn HyperHDR runtime HDR off, restore the exact original LUT and reload it. That removes the color correction while leaving the splitter firmware unchanged; TV-led capture will again have incorrect colors under ordinary YUV interpretation.
