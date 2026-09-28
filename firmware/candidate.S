/* Experimental TV-led transport test. Never flash section fragments.
 * LLDV stays eligible; standard DV additionally requires RGB8 source video.
 * No pixel/color decoder, EDID change, or HDCP change.
 */
.syntax unified
.cpu cortex-m3
.thumb
.section .route_hook,"ax"
 b.w route_candidate
.section .ratio_hook,"ax"
 b.w ratio_candidate
.section .filter_hook,"ax"
 b.w filter_candidate
.section .avi_hook,"ax"
 b.w avi_candidate
.section .extension,"ax"
.thumb_func
route_candidate:
 push {r0-r3,r12,lr}
 mov r0,r2
 bl eligible
 cmp r0,#0
 pop {r0-r3,r12,lr}
 beq 1f
 movs r3,#3
1:
 ldrh r0,[r1,#6]
 cmp r0,#5
 b.w route_continue
.thumb_func
ratio_candidate:
 push {r0-r3,r12,lr}
 mov r1,r2
 bl eligible
 cmp r0,#0
 pop {r0-r3,r12,lr}
 beq 1f
 movw r0,#0x101
 bx lr
1:
 push.w {r4-r11,lr}
 b.w ratio_continue
.thumb_func
filter_candidate:
 cmp.w sl,#9
 bne filter_pass
 ldrb r0,[r4,#0x6c]
 cbnz r0,filter_pass
 mov r0,r7
 mov r1,r4
 bl eligible
 cbz r0,filter_pass
 b.w stock_disable
filter_pass:
 movs r3,#1
 mov r2,r9
 b.w stock_continue
.thumb_func
avi_candidate:
 /* Stock writer's frame is 0x48 bytes incl saved regs, SP is aligned.
  * Preserve all registers; its local packet starts at original SP+4.
  */
 push {r0-r3,r12,lr}
 ldr r1,[r4,#0x3c]
 ldrh r2,[r1]
 cmp r2,#24             /* destination still RGB8 */
 bne avi_done
 ldr r0,=0x200030d8
 ldr r0,[r0,#0x3c]
 ldr r0,[r0,#0x14]
 ldr r1,[r1,#0x14]
 cmp r0,r1            /* same active width/height */
 bne avi_done
 mov r1,r4
 ldr r0,=0x200030d8
 bl eligible
 cmp r0,#2
 bne avi_done
 ldrh r0,[sp,#28]
 movw r1,#0x0282
 cmp r0,r1
 bne avi_done
 ldrb r0,[sp,#30]
 cmp r0,#13
 bne avi_done
 ldrb r0,[sp,#32]     /* original SP+8 = AVI DB1 */
 tst r0,#0xe0
 bne avi_done
 orr r0,r0,#0x20
 strb r0,[sp,#32]
 /* Recompute checksum across header and 13 payload bytes. */
 movs r0,#0
 strb r0,[sp,#31]
 add r1,sp,#28
 movs r2,#17
1:
 ldrb r3,[r1],#1
 adds r0,r0,r3
 subs r2,r2,#1
 bne 1b
 rsbs r0,r0,#0
 strb r0,[sp,#31]
avi_done:
 pop {r0-r3,r12,lr}
 subs r0,r0,#3        /* replay overwritten instructions */
 uxth r2,r0
 b.w avi_continue

/* r0 source, r1 destination; returns 0 (reject), 2 (STD RGB8), 3 (LLDV).
 * Callee-saved registers retained. No persistent RAM allocation.
 * Re-read vendor packet to avoid relying on stale cached mode state.
 */
.thumb_func
eligible:
 push {r4,lr}
 sub sp,#32
 mov r4,r0
 ldrh r0,[r1,#6]
 cmp r0,#6
 bne reject
 ldr r0,=0x200003b0
 ldrh r0,[r0]
 cbnz r0,reject
 ldr r0,=0x2000314c
 ldrb r0,[r0,#0x6c]
 cmp r0,#255
 bne reject
 ldr r0,[r4,#0x3c]
 ldrh r0,[r0,#0x2a]
 tst r0,#0x200
 beq reject
 movs r0,#0
 mov r2,sp
 movs r1,#8
1:
 str r0,[r2],#4
 subs r1,r1,#1
 bne 1b
 mov r0,r4
 movs r1,#9
 mov r2,sp
 bl read_vendor_packet
 ldr r0,[sp]
 bic r0,r0,#0xff000000
 ldr r1,=0x001b0181
 cmp r0,r1
 bne reject
 ldr r0,[sp,#4]
 bic r0,r0,#0xff000000
 ldr r1,=0x0000d046
 cmp r0,r1
 bne reject
 ldrb r0,[sp,#7]
 ands r0,r0,#3
 cmp r0,#2
 blo reject
 bne eligible_done      /* preserve old LLDV format eligibility */
 ldr r1,[r4,#0x3c]
 ldrh r1,[r1]          /* video total bits/pixel byte0 (24=8bpc), format byte1 */
 cmp r1,#24
 bne reject
 /* Require a valid incoming checksum for the new STD-DV path. */
 movs r1,#0
 movs r2,#31
 mov r3,sp
1:
 ldrb r12,[r3],#1
 add r1,r1,r12
 subs r2,r2,#1
 bne 1b
 uxtb r1,r1
 cbz r1,eligible_done
reject:
 movs r0,#0
eligible_done:
 add sp,#32
 pop {r4,pc}
.ltorg
