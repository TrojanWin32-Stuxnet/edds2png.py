from __future__ import annotations

import argparse
import io
import struct
import sys
from pathlib import Path
from typing import BinaryIO, Iterable, Sequence


COPY_BLOCK = b"COPY"
LZ4_BLOCK = b"LZ4 "
DDS_HEADER_SIZE = 128
DDS_DX10_HEADER_SIZE = 20
LZ4_WINDOW_SIZE = 65536


class EddsFormatError(ValueError):
    """Raised when an EDDS file is truncated or structurally invalid."""


def find_edds_inputs(paths: Iterable[str | Path]) -> list[Path]:
    """Expand CLI arguments into top-level .edds files.

    Directory arguments are scanned only at the top level, matching the .NET
    implementation's SearchOption.TopDirectoryOnly behavior.
    """

    image_paths: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            image_paths.extend(
                sorted(child for child in path.iterdir() if child.is_file() and _is_edds(child))
            )
        elif _is_edds(path):
            image_paths.append(path)
    return image_paths


def convert_file(image_path: str | Path) -> Path:
    """Convert one .edds file to a sibling .png file and return the output path."""

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "DDS decoding requires Pillow. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    source = Path(image_path)
    output = source.with_suffix(".png")
    dds_bytes = decompress_edds(source)

    with Image.open(io.BytesIO(dds_bytes)) as image:
        image.load()
        if image.mode not in {"RGBA", "RGB", "L", "LA"}:
            image = image.convert("RGBA")
        image.save(output, "PNG")

    return output


def decompress_edds(image_path: str | Path) -> bytes:
    """Unpack an EDDS file and return the reconstructed DDS byte stream."""

    decoded_parts: list[bytes] = []

    with Path(image_path).open("rb") as reader:
        dds_header = _read_exact(reader, DDS_HEADER_SIZE, "DDS header")
        dds_header_dx10 = b""

        if dds_header[84:88] == b"DX10":
            dds_header_dx10 = _read_exact(reader, DDS_DX10_HEADER_SIZE, "DDS DX10 header")

        copy_blocks, lz4_blocks = _read_block_table(reader)

        for size in copy_blocks:
            if size < 0:
                raise EddsFormatError(f"COPY block has invalid negative size {size}")
            decoded_parts.append(_read_exact(reader, size, "COPY payload"))

        for compressed_length in lz4_blocks:
            decoded_parts.append(_decode_lz4_payload(reader, compressed_length))

    return b"".join([dds_header, dds_header_dx10, *reversed(decoded_parts)])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert .edds texture files to .png.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="EDDS files, or directories containing top-level .edds files.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Stop after the first failed conversion instead of trying remaining files.",
    )
    args = parser.parse_args(argv)

    image_paths = find_edds_inputs(args.paths)
    if not image_paths:
        return 0

    failures: list[tuple[Path, Exception]] = []
    for image_path in image_paths:
        full_path = image_path.resolve(strict=False)
        try:
            output_path = convert_file(full_path)
            print(f"{full_path} -> {output_path}")
        except Exception as exc:
            failures.append((full_path, exc))
            print(f"{full_path}: {exc}", file=sys.stderr)
            if args.strict:
                break

    return 1 if failures else 0


def _is_edds(path: Path) -> bool:
    return path.suffix.lower() == ".edds"


def _read_block_table(reader: BinaryIO) -> tuple[list[int], list[int]]:
    copy_blocks: list[int] = []
    lz4_blocks: list[int] = []

    while True:
        start = reader.tell()
        header = reader.read(8)
        if len(header) != 8:
            raise EddsFormatError("EDDS block table ended unexpectedly")

        block_type = header[:4]
        size = struct.unpack("<i", header[4:])[0]

        if block_type == COPY_BLOCK:
            copy_blocks.append(size)
        elif block_type == LZ4_BLOCK:
            lz4_blocks.append(size)
        else:
            reader.seek(start)
            return copy_blocks, lz4_blocks


def _decode_lz4_payload(reader: BinaryIO, compressed_length: int) -> bytes:
    if compressed_length < 4:
        raise EddsFormatError(f"LZ4 block has invalid length {compressed_length}")

    try:
        import lz4.block
    except ImportError as exc:
        raise RuntimeError(
            "LZ4 EDDS blocks require the lz4 package. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    target_size = struct.unpack("<I", _read_exact(reader, 4, "LZ4 output size"))[0]
    bytes_remaining = compressed_length - 4
    consumed = 0
    target = bytearray()
    history = bytearray()

    while consumed < bytes_remaining:
        count = struct.unpack("<i", _read_exact(reader, 4, "LZ4 chunk size"))[0]
        consumed += 4
        chunk_size = count & 0x7FFFFFFF
        if chunk_size > bytes_remaining - consumed:
            raise EddsFormatError(
                f"LZ4 chunk size {chunk_size} exceeds remaining block length "
                f"{bytes_remaining - consumed}"
            )

        chunk = _read_exact(reader, chunk_size, "LZ4 chunk")
        consumed += chunk_size

        if history:
            decoded = lz4.block.decompress(
                chunk,
                uncompressed_size=LZ4_WINDOW_SIZE,
                dict=bytes(history[-LZ4_WINDOW_SIZE:]),
            )
        else:
            decoded = lz4.block.decompress(chunk, uncompressed_size=LZ4_WINDOW_SIZE)

        target.extend(decoded)
        if len(target) > target_size:
            raise EddsFormatError(
                f"LZ4 block decoded to {len(target)} bytes, expected {target_size}"
            )

        history.extend(decoded)
        if len(history) > LZ4_WINDOW_SIZE:
            del history[:-LZ4_WINDOW_SIZE]

    if len(target) < target_size:
        target.extend(b"\x00" * (target_size - len(target)))

    return bytes(target)


def _read_exact(reader: BinaryIO, size: int, label: str) -> bytes:
    data = reader.read(size)
    if len(data) != size:
        raise EddsFormatError(f"Expected {size} bytes for {label}, got {len(data)}")
    return data
