#!/usr/bin/env python3
"""Repack a Nokia 7 Plus boot image with a new gzip kernel.

The stock boot image is header v0 with the DTB appended to the gzip kernel
blob.  We keep the stock ramdisk and stock appended DTB, replace only the gzip
part with the newly built Image.gz, and recompute the header SHA1 checksum
using the same algorithm as Magiskboot.
"""
import argparse
import hashlib
import struct
import sys
import zlib


def align(value, page):
    return (value + page - 1) // page * page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock", required=True, help="stock boot image")
    parser.add_argument("--kernel", required=True, help="new Image.gz")
    parser.add_argument("--output", required=True, help="output boot image")
    args = parser.parse_args()

    stock = open(args.stock, "rb").read()
    new_gz = open(args.kernel, "rb").read()

    if stock[:8] != b"ANDROID!":
        sys.exit("stock image is not an Android boot image")
    if new_gz[:2] != b"\x1f\x8b":
        sys.exit("new kernel is not gzip-compressed")

    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr = struct.unpack_from("<4I", stock, 8)
    second_size, second_addr, tags_addr, page_size, header_version, os_version = struct.unpack_from("<6I", stock, 24)
    if header_version != 0:
        sys.exit("only header v0 is supported (got %d)" % header_version)
    if page_size < 2048 or page_size > 65536 or page_size & (page_size - 1):
        sys.exit("bad page size: %d" % page_size)

    hdr_space = page_size
    stock_kernel = stock[hdr_space:hdr_space + kernel_size]
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    d.decompress(stock_kernel)
    stock_dtb = d.unused_data
    if stock_dtb[:4] != b"\xd0\x0d\xfe\xed":
        sys.exit("stock kernel has no appended FDT (unused_data=%d)" % len(stock_dtb))

    ramdisk_off = hdr_space + align(kernel_size, page_size)
    stock_ramdisk = stock[ramdisk_off:ramdisk_off + ramdisk_size]
    second_off = ramdisk_off + align(ramdisk_size, page_size)
    stock_second = stock[second_off:second_off + second_size] if second_size else b""

    new_kernel = new_gz + stock_dtb
    new_kernel_size = len(new_kernel)
    if new_kernel_size > 0xFFFFFFFF:
        sys.exit("kernel too large")

    header = bytearray(stock[:page_size])
    struct.pack_into("<I", header, 8, new_kernel_size)

    # Same checksum layout as Magiskboot for header v0:
    # SHA1(kernel || kernel_size || ramdisk || ramdisk_size || second || second_size)
    ctx = hashlib.sha1()
    ctx.update(new_kernel)
    ctx.update(struct.pack("<I", new_kernel_size))
    ctx.update(stock_ramdisk)
    ctx.update(struct.pack("<I", ramdisk_size))
    ctx.update(stock_second)
    ctx.update(struct.pack("<I", second_size))
    digest = ctx.digest()
    header[0x240:0x260] = digest + b"\x00" * (32 - len(digest))

    out = bytearray()
    out += header
    out += new_kernel
    out += b"\x00" * (align(new_kernel_size, page_size) - new_kernel_size)
    out += stock_ramdisk
    out += b"\x00" * (align(ramdisk_size, page_size) - ramdisk_size)
    if second_size:
        out += stock_second
        out += b"\x00" * (align(second_size, page_size) - second_size)

    # Match the stock image's partition-sized dump (64 MiB on B2N).
    if len(out) < len(stock):
        out += b"\x00" * (len(stock) - len(out))

    open(args.output, "wb").write(out)

    print("stock kernel       :", kernel_size)
    print("stock appended DTB :", len(stock_dtb))
    print("new Image.gz       :", len(new_gz))
    print("new kernel blob    :", new_kernel_size)
    print("ramdisk            :", ramdisk_size)
    print("second             :", second_size)
    print("output             :", len(out))
    print("checksum           :", digest.hex())


if __name__ == "__main__":
    main()
