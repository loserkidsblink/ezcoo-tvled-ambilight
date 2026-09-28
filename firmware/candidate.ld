SECTIONS {
 .ratio_hook 0x08009462 : { *(.ratio_hook) }
 .route_hook 0x0800966c : { *(.route_hook) }
 .avi_hook 0x08013d44 : { *(.avi_hook) }
 .filter_hook 0x0801635e : { *(.filter_hook) }
 .extension 0x0801ee6c : { *(.extension) }
}
route_continue = 0x08009670;
ratio_continue = 0x08009466;
read_vendor_packet = 0x0800b799;
stock_disable = 0x08016376;
stock_continue = 0x08016362;
avi_continue = 0x08013d48;
ASSERT(SIZEOF(.extension) <= 404, "Extension exceeds verified unused tail")
