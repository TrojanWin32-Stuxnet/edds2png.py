from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from edds2png.converter import decompress_edds, find_edds_inputs


class ConverterTests(unittest.TestCase):
    def test_find_edds_inputs_expands_top_level_directory_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "nested"
            nested.mkdir()
            first = root / "first.edds"
            second = root / "second.EDDS"
            ignored = root / "ignored.txt"
            nested_file = nested / "nested.edds"

            for path in (first, second, ignored, nested_file):
                path.write_bytes(b"")

            self.assertEqual(find_edds_inputs([root]), [first, second])

    def test_decompress_edds_rebuilds_copy_blocks_in_reverse_payload_order(self) -> None:
        dds_header = _dds_header()
        first = b"abcdefgh"
        second = b"ijklmnop"
        edds = (
            dds_header
            + b"COPY"
            + struct.pack("<i", len(first))
            + b"COPY"
            + struct.pack("<i", len(second))
            + first
            + second
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "image.edds"
            image_path.write_bytes(edds)

            self.assertEqual(decompress_edds(image_path), dds_header + second + first)

    def test_decompress_edds_preserves_dx10_header(self) -> None:
        dds_header = bytearray(_dds_header())
        dds_header[84:88] = b"DX10"
        dx10_header = b"0123456789abcdefghij"
        payload = b"abcdefgh"
        edds = (
            bytes(dds_header)
            + dx10_header
            + b"COPY"
            + struct.pack("<i", len(payload))
            + payload
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "image.edds"
            image_path.write_bytes(edds)

            self.assertEqual(decompress_edds(image_path), bytes(dds_header) + dx10_header + payload)


def _dds_header() -> bytes:
    header = bytearray(128)
    header[:4] = b"DDS "
    return bytes(header)


if __name__ == "__main__":
    unittest.main()
