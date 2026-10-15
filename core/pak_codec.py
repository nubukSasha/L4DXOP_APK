# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  core.pak_codec
---------------------------------------------------------------------------------
  Чтение/разбор/сборка PAK-файлов Tencent (Unreal).

  Перенесено 1-в-1 из tool.py (строки 900-2471):
      Reader, PakInfo, TencentPakInfo, PakCompressedBlock, TencentPakEntry,
      TencentPakFile (+ dump / inject_files / detect_dominant_style),
      _sanitize_part, _get_all_dirs_and_mp,
      repack_pak_file_full, build_new_pak_from_template

  ОТЛИЧИЯ ОТ tool.py (только обвязка вывода):
      console.print(...)      -> log_callback(line)
      Progress / stdout.write -> progress_callback(done, total, msg)
  Сама логика байт-в-байт не менялась.

  ВАЖНО: этот модуль НЕ импортирует UI и не печатает в stdout.

  CREDIT: @L4DXOP
=================================================================================
"""

import itertools as it
import os
import re
import shutil
import struct
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import PurePath, Path
from typing import List

from .constants import (
    CM_MASK,
    CM_NAMES,
    CM_NONE,
    CM_ZLIB,
    CM_ZSTD,
    CM_ZSTD_DICT,
    DEFAULT_BLOCK_SIZE,
    SIMPLE1_DECRYPT_KEY,
    SM4_SECRET_NEW,
)
from .compression import (
    ZSTD_AVAILABLE,
    PakCompression,
    best_compress,
    compress_chunk_direct,
)
from .crypto import (
    CRYPTO_AVAILABLE,
    SHA1,
    SM4,
    PakCrypto,
    encrypt_plaintext,
)

if not hasattr(it, 'batched'):  # Python < 3.12 (см. crypto.py)
    def _batched(iterable, n):
        it_iter = iter(iterable)
        while True:
            chunk = list(it.islice(it_iter, n))
            if not chunk:
                break
            yield chunk
    it.batched = _batched


# ══════════════════════════════════════════════════════════════════════════════
#  БИНАРНЫЙ ЧИТАТЕЛЬ ИНДЕКСА
# ══════════════════════════════════════════════════════════════════════════════
class Reader:
    """Чтение примитивов индекса PAK (little-endian)."""

    def __init__(self, buffer, cursor=0):
        self._buffer = buffer
        self._cursor = cursor

    def u1(self, move_cursor=True) -> int:
        return self.unpack('B', move_cursor=move_cursor)[0]

    def u4(self, move_cursor=True) -> int:
        return self.unpack('<I', move_cursor=move_cursor)[0]

    def u8(self, move_cursor=True) -> int:
        return self.unpack('<Q', move_cursor=move_cursor)[0]

    def i1(self, move_cursor=True) -> int:
        return self.unpack('b', move_cursor=move_cursor)[0]

    def i4(self, move_cursor=True) -> int:
        return self.unpack('<i', move_cursor=move_cursor)[0]

    def i8(self, move_cursor=True) -> int:
        return self.unpack('<q', move_cursor=move_cursor)[0]

    def s(self, n: int, move_cursor=True) -> bytes:
        return self.unpack(f'{n}s', move_cursor=move_cursor)[0]

    def unpack(self, f: str, offset=0, move_cursor=True):
        x = struct.unpack_from(f, self._buffer, self._cursor + offset)
        if move_cursor:
            self._cursor += struct.calcsize(f)
        return x

    def string(self, move_cursor=True) -> str:
        length = self.i4(move_cursor=move_cursor)
        if length == 0:
            return str()
        else:
            assert length > 0
            offset = 0 if move_cursor else 4
            raw = self.unpack(f'{length}s', offset=offset, move_cursor=move_cursor)[0].rstrip(b'\x00')
            return raw.replace(b'\x00', b'').decode('utf-8', errors='replace')


# ══════════════════════════════════════════════════════════════════════════════
#  ЗАГОЛОВОК / ИНДЕКС / ЗАПИСИ
# ══════════════════════════════════════════════════════════════════════════════
class PakInfo:
    """Подвал PAK-файла (45 байт для базовой версии)."""

    def __init__(self, buffer, keystream: List[int]):
        def decrypt_index_encrypted(x: int) -> int:
            MASK_8 = 255
            return (x ^ keystream[3]) & MASK_8

        def decrypt_magic(x: int) -> int:
            return x ^ keystream[2]

        def decrypt_index_hash(x: bytes) -> bytes:
            key = struct.pack('<5I', *keystream[4:][:5])
            assert len(x) == len(key)
            return bytes((a ^ b for a, b in zip(x, key)))

        def decrypt_index_size(x: int) -> int:
            return x ^ (keystream[10] << 32 | keystream[11])

        def decrypt_index_offset(x: int) -> int:
            return x ^ (keystream[0] << 32 | keystream[1])

        reader = Reader(buffer[-PakInfo._mem_size((-1)):])
        self.index_encrypted = decrypt_index_encrypted(reader.u1()) == 1
        self.magic = decrypt_magic(reader.u4())
        self.version = reader.u4()
        self.index_hash = decrypt_index_hash(reader.s(20)) if self.version >= 6 else bytes()
        self.index_size = decrypt_index_size(reader.u8())
        self.index_offset = decrypt_index_offset(reader.u8())
        if self.version <= 3:
            self.index_encrypted = False

    @staticmethod
    def _mem_size(_: int) -> int:
        return 45


class TencentPakInfo(PakInfo):
    """Подвал Tencent PAK — версии >= 7 добавляют поля."""

    def __init__(self, buffer, keystream: List[int]):
        def decrypt_unk(x: bytes) -> bytes:
            key = struct.pack('<8I', *keystream[7:][:8])
            assert len(x) == len(key)
            return bytes((a ^ b for a, b in zip(x, key)))

        def decrypt_stem_hash(x: int) -> int:
            return x ^ keystream[8]

        def decrypt_unk_hash(x: int) -> int:
            return x ^ keystream[9]

        super().__init__(buffer, keystream)
        reader = Reader(buffer[-TencentPakInfo._mem_size(self.version):])
        self.unk1 = decrypt_unk(reader.s(32)) if self.version >= 7 else bytes()
        self.packed_key = reader.s(256) if self.version >= 8 else bytes()
        self.packed_iv = reader.s(256) if self.version >= 8 else bytes()
        self.packed_index_hash = reader.s(256) if self.version >= 8 else bytes()
        self.stem_hash = decrypt_stem_hash(reader.u4()) if self.version >= 9 else 0
        self.unk2 = decrypt_unk_hash(reader.u4()) if self.version >= 9 else 0
        self.content_org_hash = reader.s(20) if self.version >= 12 else bytes()

    @staticmethod
    def _mem_size(version: int) -> int:
        size_for_7 = 32 if version >= 7 else 0
        size_for_8 = 768 if version >= 8 else 0
        size_for_9 = 8 if version >= 9 else 0
        size_for_12 = 20 if version >= 12 else 0
        return PakInfo._mem_size(version) + size_for_7 + size_for_8 + size_for_9 + size_for_12


class PakCompressedBlock:
    """Один сжатый блок внутри записи индекса: [start, end)."""

    def __init__(self, reader: Reader):
        self.start = reader.u8()
        self.end = reader.u8()


@dataclass
class TencentPakEntry:
    """Одна запись индекса PAK = один файл внутри архива."""

    def __init__(self, reader: Reader, version: int):
        self.content_hash = reader.s(20)
        if version <= 1:
            _ = reader.u8()
        self.offset = reader.u8()
        self.uncompressed_size = reader.u8()
        self.compression_method = reader.u4() & CM_MASK
        self.size = reader.u8()
        self.unk1 = reader.u1() if version >= 5 else 0
        self.unk2 = reader.s(20) if version >= 5 else bytes()
        if self.compression_method != 0 and version >= 3:
            self.compressed_blocks = [PakCompressedBlock(reader) for _ in range(reader.u4())]
        else:
            self.compressed_blocks = []
        self.compression_block_size = reader.u4() if version >= 4 else 0
        self.encrypted = reader.u1() == 1 if version >= 4 else False
        self.encryption_method = reader.u4() if version >= 12 else 0
        self.index_new_sep = reader.u4() if version >= 12 else 0


# ══════════════════════════════════════════════════════════════════════════════
#  ХЕЛПЕРЫ
# ══════════════════════════════════════════════════════════════════════════════
_INVALID_FN_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*\x7f]')


def _sanitize_part(name) -> str:
    """Убрать из имени файла недопустимые символы Android."""
    if name is None:
        return '_'
    s = str(name)
    s = s.replace('\x00', '')
    s = _INVALID_FN_CHARS.sub('', s)
    s = s.rstrip('. ')
    if not s or s in ('.', '..'):
        s = '_'
    return s


def _pw_string(s):
    """Сериализация строки в формате индекса PAK (длина + байты + \\0)."""
    if not s:
        return struct.pack('<i', 0)
    b = s.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(b)) + b


def _pw_entry(e, v):
    """Сериализация записи индекса PAK для версии v."""
    w = bytearray(e.content_hash)
    w += struct.pack('<Q', e.offset)
    w += struct.pack('<Q', e.uncompressed_size)
    w += struct.pack('<I', e.compression_method)
    w += struct.pack('<Q', e.size)
    if v >= 5:
        w += bytes([e.unk1])
        w += e.unk2
    if e.compression_method != CM_NONE and v >= 3:
        w += struct.pack('<I', len(e.compressed_blocks))
        for b in e.compressed_blocks:
            w += struct.pack('<QQ', b.start, b.end)
    if v >= 4:
        w += struct.pack('<I', e.compression_block_size)
        w += bytes([1 if e.encrypted else 0])
    if v >= 12:
        w += struct.pack('<II', e.encryption_method, e.index_new_sep)
    return bytes(w)


def _block_permutation(n_chunks: int, encryption_method: int):
    return PakCrypto.generate_block_indices(n_chunks, encryption_method)


def _get_all_dirs_and_mp(pak_file):
    """
    Быстрый обход сырого индекса без полной загрузки записей.
    Возвращает (mount_point_str, {dir_str: {file_name: (slot, entry)}}).
    """
    raw = bytes(pak_file._file_content[
        pak_file._pak_info.index_offset:][:pak_file._pak_info.index_size])
    if pak_file._pak_info.index_encrypted:
        try:
            raw = PakCrypto.decrypt_index(raw, pak_file._pak_info)
        except Exception:
            pass
    r = Reader(raw)
    mp = r.string()
    num_files = r.u4()
    for _ in range(num_files):
        TencentPakEntry(r, pak_file._pak_info.version)
    dirs = {}
    for _ in range(r.u8()):
        dp = r.string()
        cnt = r.u8()
        d = {}
        for _ in range(cnt):
            fname = r.string()
            idx = ~r.i4()
            if 0 <= idx < len(pak_file._files):
                d[fname] = (idx, pak_file._files[idx])
        dirs[dp] = d
    return mp, dirs


# ══════════════════════════════════════════════════════════════════════════════
#  ОСНОВНОЙ КЛАСС
# ══════════════════════════════════════════════════════════════════════════════
class TencentPakFile:
    """
    Чтение PAK и распаковка.

    log_callback(line: str)            — строка лога
    progress_callback(done, total, msg) — прогресс (0..total)
    """

    def __init__(self, file_path: PurePath, is_od=False,
                 log_callback=None, progress_callback=None):
        self._file_path = file_path
        self._log_cb = log_callback
        self._progress_cb = progress_callback
        # Результаты последней сборки (для отчёта в UI)
        self.last_file_rows = []

        self._file_handle = open(file_path, 'rb')
        try:
            import mmap
            self._file_mmap = mmap.mmap(self._file_handle.fileno(), 0, access=mmap.ACCESS_READ)
            self._file_content = memoryview(self._file_mmap)
        except Exception:
            self._file_content = memoryview(self._file_handle.read())
            self._file_mmap = None

        self._is_od = is_od
        self._mount_point = PurePath()
        self._is_zstd_with_dict = 'zsdic' in str(self._file_path)
        self._zstd_dict = None
        self._files = []
        self._index = {}

        self._pak_info = TencentPakInfo(self._file_content, PakCrypto.zuc_keystream())
        self._verify_stem_hash()
        self._tencent_load_index()

    # ─── callbacks ───────────────────────────────────────────────────────────
    def _log(self, line: str):
        if self._log_cb:
            try:
                self._log_cb(line)
            except Exception:
                pass

    def _progress(self, done, total, msg=""):
        if self._progress_cb:
            try:
                self._progress_cb(done, total, msg)
            except Exception:
                pass

    # ─── инфо о PAK ──────────────────────────────────────────────────────────
    def detect_dominant_style(self) -> dict:
        """Наиболее частые методы сжатия/шифрования внутри PAK."""
        from collections import Counter
        comp_counter = Counter()
        enc_counter = Counter()
        blk_counter = Counter()
        enc_flag_counter = Counter()
        total = len(self._files)
        if total == 0:
            return {'comp_method': CM_ZSTD, 'enc_method': 0,
                    'encrypted': False, 'block_size': DEFAULT_BLOCK_SIZE}
        for entry in self._files:
            comp_counter[entry.compression_method] += 1
            if entry.encrypted:
                enc_counter[entry.encryption_method] += 1
                enc_flag_counter['encrypted'] += 1
            else:
                enc_flag_counter['plain'] += 1
            if entry.compression_block_size:
                blk_counter[entry.compression_block_size] += 1
        non_none = [(m, c) for m, c in comp_counter.items() if m != CM_NONE]
        comp_method = max(non_none, key=lambda x: x[1])[0] if non_none else CM_NONE
        encrypted = enc_flag_counter.get('encrypted', 0) > enc_flag_counter.get('plain', 0)
        enc_method = enc_counter.most_common(1)[0][0] if encrypted and enc_counter else 0
        block_size = blk_counter.most_common(1)[0][0] if blk_counter else DEFAULT_BLOCK_SIZE
        return {'comp_method': comp_method, 'enc_method': enc_method,
                'encrypted': encrypted, 'block_size': block_size}

    def info(self) -> dict:
        """Краткая сводка по PAK — для шапки на экранах."""
        return {
            'name': Path(self._file_path).name,
            'version': self._pak_info.version,
            'mount_point': self._mount_point.as_posix(),
            'files': len(self._files),
            'dirs': len(self._index),
            'size': self._pak_info.index_size,
            'index_encrypted': self._pak_info.index_encrypted,
        }

    # ─── проверки ────────────────────────────────────────────────────────────
    def _get_method_str(self, method_int, is_encryption):
        if is_encryption:
            if PakCrypto._is_simple1_method(method_int):
                return "SIMPLE1"
            if PakCrypto._is_simple2_method(method_int):
                return "SIMPLE2"
            if PakCrypto._is_sm4_method(method_int):
                return f"SM4 (Type {method_int})"
            return "NONE" if method_int == 0 else "UNKNOWN"
        else:
            if method_int == CM_NONE:
                return "NONE"
            return CM_NAMES.get(method_int, "UNKNOWN")

    def _verify_stem_hash(self) -> None:
        if not self._is_od and self._pak_info.version >= 9:
            expected = zlib.crc32(self._file_path.stem.encode('utf-32le'))
            if self._pak_info.stem_hash != expected:
                self._log("WARN Stem hash mismatch (file may be renamed)")

    def _tencent_load_index(self) -> None:
        index_data = self._file_content[self._pak_info.index_offset:][:self._pak_info.index_size]
        if self._pak_info.index_encrypted:
            try:
                index_data = PakCrypto.decrypt_index(index_data, self._pak_info)
            except Exception:
                self._log("WARN Index decryption failed, trying raw")
        self._verify_index_hash(index_data)
        self._load_index(index_data)

    def _verify_index_hash(self, index_data) -> None:
        from .constants import RSA_MOD_2
        expected_hash = self._pak_info.index_hash
        if not self._is_od and self._pak_info.version >= 8:
            try:
                rsa_hash = PakCrypto.rsa_extract(self._pak_info.packed_index_hash, RSA_MOD_2)
                if expected_hash != rsa_hash:
                    self._log("WARN Index signature mismatch (secure VIP connection)")
            except Exception:
                pass
        actual = SHA1.new(index_data).digest()
        if expected_hash != actual:
            self._log("WARN Index hash mismatch (PAK modified?)")

    # ─── низкоуровневое чтение ───────────────────────────────────────────────
    @staticmethod
    def _construct_mount_point(mount_point: str) -> PurePath:
        result = PurePath()
        for part in PurePath(mount_point).parts:
            if part != '..':
                result /= part
        return result

    def _peek_content(self, offset: int, size: int, encryption_method: int) -> memoryview:
        size = PakCrypto.align_encrypted_content_size(size, encryption_method)
        end = min(offset + size, len(self._file_content))
        return self._file_content[offset:end]

    def _peek_block_content(self, block: PakCompressedBlock, encryption_method: int) -> memoryview:
        size = PakCrypto.align_encrypted_content_size(block.end - block.start, encryption_method)
        end = min(block.start + size, len(self._file_content))
        return self._file_content[block.start:end]

    def _construct_zstd_dict(self, dict_entry: TencentPakEntry) -> None:
        assert not self._zstd_dict
        assert not dict_entry.encrypted
        assert dict_entry.compression_method == CM_NONE
        reader = Reader(self._peek_content(dict_entry.offset, dict_entry.size, 0))
        dict_size = reader.u8()
        _ = reader.u4()
        assert dict_size == reader.u4()
        dict_data = reader.s(dict_size)
        self._zstd_dict = PakCompression.zstd_dictionary(dict_data)

    def _load_index(self, index_data) -> None:
        if self._pak_info.version <= 10:
            raise ValueError(f'Unsupported version: {self._pak_info.version}')
        else:
            reader = Reader(index_data)
            self._mount_point = self._construct_mount_point(reader.string())
            num_files = reader.u4()
            self._files = []
            for _ in range(num_files):
                self._files.append(TencentPakEntry(reader, self._pak_info.version))
            num_dirs = reader.u8()
            for _ in range(num_dirs):
                dir_path = PurePath(reader.string())
                num_entries = reader.u8()
                dir_content = {}
                for _ in range(num_entries):
                    entry_name = reader.string()
                    idx = reader.i4()
                    if idx < 0:
                        entry_idx = ~idx
                        if 0 <= entry_idx < len(self._files):
                            dir_content[entry_name] = self._files[entry_idx]
                if self._is_zstd_with_dict and dir_path.name == 'zstddic':
                    if len(dir_content) == 1:
                        try:
                            self._construct_zstd_dict(list(dir_content.values())[0])
                        except Exception as e:
                            self._log(f"WARN zstd dictionary unavailable: {e}")
                else:
                    if dir_content:
                        self._index[dir_path] = dir_content

    # ─── распаковка одного файла ─────────────────────────────────────────────
    def _write_to_disk(self, file_path: Path, entry: TencentPakEntry) -> None:
        encryption_method = entry.encryption_method
        compression_method = entry.compression_method
        total_blocks = len(entry.compressed_blocks)

        if compression_method == CM_NONE:
            data = self._peek_content(entry.offset, entry.size, encryption_method)
            if entry.encrypted:
                data = PakCrypto.decrypt_block(data, file_path, encryption_method)
            with open(file_path, 'wb') as f:
                f.write(data)
            return

        with open(file_path, 'wb') as f:
            for idx in PakCrypto.generate_block_indices(total_blocks, encryption_method):
                if idx >= len(entry.compressed_blocks):
                    continue
                block = entry.compressed_blocks[idx]
                data = self._peek_block_content(block, encryption_method)
                if entry.encrypted:
                    try:
                        data = PakCrypto.decrypt_block(data, file_path, encryption_method)
                    except Exception:
                        pass
                try:
                    decompressed = PakCompression.decompress_block(
                        data, self._zstd_dict, compression_method)
                except Exception:
                    decompressed = data
                f.write(decompressed)

    def dump(self, out_path: Path) -> None:
        """
        Распаковать все файлы PAK на диск.
        Прогресс идёт через self._progress(done, total, name).
        """
        mp_parts = [_sanitize_part(p) for p in self._mount_point.parts]
        out_path = out_path.joinpath(*mp_parts) if mp_parts else out_path
        out_path.mkdir(parents=True, exist_ok=True)
        total_files = sum(len(d) for d in self._index.values())

        done = 0
        self._progress(0, total_files, "Extracting files...")
        for dir_path, dir_content in self._index.items():
            dp_parts = [_sanitize_part(p) for p in dir_path.parts]
            current_out_path = out_path.joinpath(*dp_parts) if dp_parts else out_path
            current_out_path.mkdir(parents=True, exist_ok=True)
            for file_name, entry in dir_content.items():
                safe_name = _sanitize_part(file_name)
                try:
                    self._write_to_disk(current_out_path / safe_name, entry)
                except Exception as e:
                    self._log(f"WARN Skipped {safe_name}: {e}")
                done += 1
                self._progress(done, total_files, safe_name)
        self._progress(total_files, total_files, "Extraction complete")

    # ══════════════════════════════════════════════════════════════════════════
    #  ИНЖЕКТ — добавление новых файлов без пересборки существующих
    # ══════════════════════════════════════════════════════════════════════════
    def inject_files(self, inject_plan: list, output_pak: Path,
                     add_signature_marker: bool = True) -> None:
        """
        inject_plan: список словарей:
            {'src_path': Path|str, 'internal_path': str,
             'comp_method': int, 'enc_method': int,
             'encrypted': bool, 'block_size': int}
            (опционально 'plain_bytes': bytes и 'comp_level': int)
        Логика 1-в-1 из TencentPakFile.inject_files() в tool.py.
        """
        if not inject_plan:
            raise ValueError('inject_plan is empty — nothing to inject')

        self._log(f"INFO INJECT MODE — source PAK: {self._file_path.name}")
        self._log(f"INFO Output: {Path(output_pak).name}")
        self._log(f"INFO Injecting {len(inject_plan)} new file(s)")

        # ── STEP 1/5: загрузка файлов инжекта ────────────────────────────────
        self._log("INFO STEP 1/5 : LOADING INJECT FILES")
        work_items = []
        for i, item in enumerate(inject_plan):
            if item.get('plain_bytes') is not None:
                plain = item['plain_bytes']
            elif item.get('src_path') is not None:
                try:
                    plain = Path(item['src_path']).read_bytes()
                except Exception as e:
                    self._log(f"ERR Cannot read {item['src_path']}: {e} — skipping")
                    continue
            else:
                self._log(f"ERR Inject item {i} has no src_path or plain_bytes — skipping")
                continue

            internal = item['internal_path'].replace('\\', '/').lstrip('/')
            if not internal:
                self._log(f"ERR Empty internal_path for item {i} — skipping")
                continue

            parts = internal.rsplit('/', 1)
            if len(parts) == 2:
                dir_str, file_name = parts[0], parts[1]
            else:
                dir_str, file_name = '', parts[0]

            work_items.append({
                'dir_str': dir_str,
                'file_name': file_name,
                'internal_path': internal,
                'plain': plain,
                'comp_method': item['comp_method'],
                'enc_method': item['enc_method'],
                'encrypted': bool(item['encrypted']),
                'block_size': item['block_size'],
                'comp_level': item.get('comp_level', 19),
            })
            self._log(f"INFO + {internal} ({len(plain):,} bytes)")

        if not work_items:
            raise RuntimeError('No valid inject items after loading')
        self._log(f"OK Loaded {len(work_items)} file(s)")

        # ── STEP 2/5: кодирование ────────────────────────────────────────────
        self._log("INFO STEP 2/5 : ENCODING INJECT FILES")
        keystream = PakCrypto.zuc_keystream()
        version = self._pak_info.version
        PAK_MAGIC = self._pak_info.magic

        orig_index_offset = self._pak_info.index_offset
        current_new_offset = orig_index_offset
        new_data_region = bytearray()
        new_injected_entries = []

        def _encrypt_plaintext_local(plaintext, pak_relative_path, encryption_method):
            # используется общая реализация из crypto.py
            return encrypt_plaintext(plaintext, pak_relative_path, encryption_method)

        for idx, item in enumerate(work_items):
            plain = item['plain']
            comp_method = item['comp_method']
            enc_method = item['enc_method']
            encrypted = item['encrypted']
            block_size_val = item['block_size']
            file_path_for_crypto = PurePath(item['file_name'])

            if len(plain) == 0:
                new_injected_entries.append({
                    'content_hash': SHA1.new(b'').digest(),
                    'offset': current_new_offset,
                    'uncompressed_size': 0, 'size': 0,
                    'comp_method': CM_NONE, 'enc_method': 0, 'encrypted': False,
                    'block_size_val': 0, 'compressed_blocks': [],
                    'unk1': 0, 'unk2': b'\x00' * 20, 'index_new_sep': 0,
                    '_dir_path': PurePath(item['dir_str']) if item['dir_str'] else PurePath(),
                    '_file_name': item['file_name'],
                })
                self._progress(idx + 1, len(work_items), item['internal_path'])
                continue

            if comp_method == CM_NONE:
                if encrypted:
                    aligned_size = PakCrypto.align_encrypted_content_size(len(plain), enc_method)
                    padded = plain + b'\x00' * (aligned_size - len(plain))
                    stored_data = _encrypt_plaintext_local(padded, file_path_for_crypto, enc_method)
                else:
                    stored_data = plain
                new_size = len(stored_data)
                new_compressed_blocks = []
            else:
                chunks = [plain[i:i + block_size_val] for i in range(0, len(plain), block_size_val)]
                if not chunks:
                    chunks = [b'']
                compressed_chunks = []
                for chunk in chunks:
                    comp = compress_chunk_direct(chunk, comp_method,
                                                 self._zstd_dict if comp_method == CM_ZSTD_DICT else None)
                    compressed_chunks.append(comp)

                encrypted_chunks = []
                for comp_data in compressed_chunks:
                    if encrypted:
                        comp_data = _encrypt_plaintext_local(comp_data, file_path_for_crypto, enc_method)
                    encrypted_chunks.append(comp_data)

                n_blocks = len(encrypted_chunks)
                indices = PakCrypto.generate_block_indices(n_blocks, enc_method)
                physical_blocks = [None] * n_blocks
                for j, chunk_data in enumerate(encrypted_chunks):
                    physical_blocks[indices[j]] = chunk_data

                physical_offsets = []
                block_cursor = current_new_offset
                for phys_block in physical_blocks:
                    physical_offsets.append((block_cursor, block_cursor + len(phys_block)))
                    block_cursor += len(phys_block)
                new_compressed_blocks = physical_offsets
                stored_data = b''.join(physical_blocks)
                new_size = len(stored_data)
                if encrypted:
                    aligned_total = PakCrypto.align_encrypted_content_size(new_size, enc_method)
                    if aligned_total > new_size:
                        stored_data = stored_data + b'\x00' * (aligned_total - new_size)
                        new_size = aligned_total

            new_content_hash = SHA1.new(stored_data).digest()
            new_data_region.extend(stored_data)

            new_injected_entries.append({
                'content_hash': new_content_hash,
                'offset': current_new_offset,
                'uncompressed_size': len(plain),
                'size': new_size,
                'comp_method': comp_method,
                'enc_method': enc_method if encrypted else 0,
                'encrypted': encrypted,
                'block_size_val': block_size_val,
                'compressed_blocks': new_compressed_blocks,
                'unk1': 0, 'unk2': b'\x00' * 20, 'index_new_sep': 0,
                '_dir_path': PurePath(item['dir_str']) if item['dir_str'] else PurePath(),
                '_file_name': item['file_name'],
            })
            current_new_offset += new_size
            self._progress(idx + 1, len(work_items), item['internal_path'])

        self._log(f"OK Encoded {len(new_injected_entries)} file(s)")

        # ── Сборка нового списка записей ─────────────────────────────────────
        new_entries = []
        entry_to_path = {}
        for dir_path, files in self._index.items():
            for fname, entry in files.items():
                entry_to_path[id(entry)] = (dir_path, fname)
        for i, entry in enumerate(self._files):
            dir_path, fname = entry_to_path.get(id(entry), (PurePath(), f'unknown_{i}'))
            new_entries.append({
                'content_hash': entry.content_hash,
                'offset': entry.offset,
                'uncompressed_size': entry.uncompressed_size,
                'size': entry.size,
                'comp_method': entry.compression_method,
                'enc_method': entry.encryption_method if entry.encrypted else 0,
                'encrypted': entry.encrypted,
                'block_size_val': entry.compression_block_size,
                'compressed_blocks': [(b.start, b.end) for b in entry.compressed_blocks],
                'unk1': entry.unk1, 'unk2': entry.unk2,
                'index_new_sep': entry.index_new_sep,
            })
        new_entries.extend(new_injected_entries)

        # Маркер-подпись PATCHED.txt
        if add_signature_marker:
            marker_already_present = False
            for dp, files_dict in self._index.items():
                if dp.name == 'HR_DHAMA' and 'PATCHED.txt' in files_dict:
                    marker_already_present = True
                    break
            if not marker_already_present:
                empty_hash = SHA1.new(b'').digest()
                new_entries.append({
                    'content_hash': empty_hash,
                    'offset': current_new_offset,
                    'uncompressed_size': 0, 'size': 0,
                    'comp_method': CM_NONE, 'enc_method': 0, 'encrypted': False,
                    'block_size_val': 0, 'compressed_blocks': [],
                    'unk1': 0, 'unk2': b'\x00' * 20, 'index_new_sep': 0,
                    '_dir_path': PurePath('L4DXOPxPUBG'),
                    '_file_name': 'PATCHED.txt',
                })

        # ── STEP 3/5: сборка индекса ─────────────────────────────────────────
        self._log("INFO STEP 3/5 : BUILDING INDEX")
        index_data = bytearray()
        raw_orig_index = self._file_content[self._pak_info.index_offset:][:self._pak_info.index_size]
        orig_index_decoded = PakCrypto.decrypt_index(bytes(raw_orig_index), self._pak_info)
        orig_reader = Reader(orig_index_decoded)
        orig_mount_len = orig_reader.i4()
        orig_mount_bytes = bytes(orig_reader.s(orig_mount_len))
        index_data.extend(struct.pack('<I', orig_mount_len))
        index_data.extend(orig_mount_bytes)
        index_data.extend(struct.pack('<I', len(new_entries)))

        for item in new_entries:
            index_data.extend(item['content_hash'])
            if version <= 1:
                index_data.extend(struct.pack('<Q', 0))
            index_data.extend(struct.pack('<Q', item['offset']))
            index_data.extend(struct.pack('<Q', item['uncompressed_size']))
            index_data.extend(struct.pack('<I', item['comp_method'] & CM_MASK))
            index_data.extend(struct.pack('<Q', item['size']))
            if version >= 5:
                index_data.extend(struct.pack('<B', item['unk1']))
                index_data.extend(item['unk2'] if item['unk2'] else b'\x00' * 20)
            if item['comp_method'] != CM_NONE and version >= 3:
                index_data.extend(struct.pack('<I', len(item['compressed_blocks'])))
                for (start, end) in item['compressed_blocks']:
                    index_data.extend(struct.pack('<Q', start))
                    index_data.extend(struct.pack('<Q', end))
            if version >= 4:
                index_data.extend(struct.pack('<I', item['block_size_val']))
                index_data.extend(struct.pack('<B', 1 if item['encrypted'] else 0))
            if version >= 12:
                index_data.extend(struct.pack('<I', item['enc_method']))
                index_data.extend(struct.pack('<I', item['index_new_sep']))

        file_to_dirname = {}
        for dir_path, files_dict in self._index.items():
            dir_str = dir_path.as_posix()
            for fname, entry in files_dict.items():
                for i, fe in enumerate(self._files):
                    if id(fe) == id(entry):
                        file_to_dirname[i] = (dir_str, fname)
                        break
        for i, item in enumerate(new_entries):
            if i not in file_to_dirname:
                if '_dir_path' in item:
                    file_to_dirname[i] = (item['_dir_path'].as_posix(), item['_file_name'])
                else:
                    file_to_dirname[i] = ('', f'file_{i}')

        all_dirs = []
        dir_to_files = {}
        for dir_path in self._index.keys():
            ds = dir_path.as_posix()
            all_dirs.append(ds)
            dir_to_files[ds] = []
        for i, item in enumerate(new_entries):
            ds, fn = file_to_dirname[i]
            if ds not in dir_to_files:
                dir_to_files[ds] = []
                all_dirs.append(ds)
            dir_to_files[ds].append((fn, i))

        index_data.extend(struct.pack('<Q', len(all_dirs)))
        for dir_str in all_dirs:
            files_list = dir_to_files[dir_str]
            if not dir_str or dir_str == '.':
                index_data.extend(struct.pack('<I', 0))
            else:
                dir_str_with_slash = dir_str if dir_str.endswith('/') else dir_str + '/'
                dir_bytes = dir_str_with_slash.encode('utf-8') + b'\x00'
                index_data.extend(struct.pack('<I', len(dir_bytes)))
                index_data.extend(dir_bytes)
            index_data.extend(struct.pack('<Q', len(files_list)))
            for file_name, fi in files_list:
                name_bytes = file_name.encode('utf-8') + b'\x00'
                index_data.extend(struct.pack('<I', len(name_bytes)))
                index_data.extend(name_bytes)
                index_data.extend(struct.pack('<i', -fi - 1))
        index_data.extend(b'\x1d\x00\x00\x00\x2e\x2e')

        index_hash = SHA1.new(bytes(index_data)).digest()

        # ── Шифрование индекса ───────────────────────────────────────────────
        if version > 7 and self._pak_info.index_encrypted:
            from .constants import RSA_MOD_1
            from Crypto.Cipher import AES
            from Crypto.Cipher.AES import MODE_CBC
            from Crypto.Util.Padding import pad
            # В tool.py здесь стоял assert: при неверном key/iv операция падала.
            # Мы падаем явно и понятно, а не молча пишем битый PAK.
            try:
                key = PakCrypto.rsa_extract(self._pak_info.packed_key, RSA_MOD_1)
                iv = PakCrypto.rsa_extract(self._pak_info.packed_iv, RSA_MOD_1)
            except Exception as e:
                raise RuntimeError(f"Cannot extract index key/IV from PAK: {e}")
            if len(key) != 32 or len(iv) != 32:
                raise RuntimeError(
                    f"Bad index key/IV from PAK (key={len(key)}B, iv={len(iv)}B, "
                    f"expected 32/32) — this PAK cannot be re-signed")
            padded = pad(bytes(index_data), AES.block_size)
            aes = AES.new(key, MODE_CBC, iv[:16])
            encrypted_index = aes.encrypt(padded)
        elif self._pak_info.index_encrypted:
            encrypted_index = bytes(b ^ SIMPLE1_DECRYPT_KEY for b in bytes(index_data))
        else:
            encrypted_index = bytes(index_data)

        # ── STEP 4/5: запись PAK ─────────────────────────────────────────────
        self._log("INFO STEP 4/5 : WRITING PAK")
        index_size = len(encrypted_index)
        new_index_offset = orig_index_offset + len(new_data_region)

        encrypted_magic = PAK_MAGIC ^ keystream[2]
        key_stream_hash = struct.pack('<5I', *keystream[4:][:5])
        encrypted_index_hash = bytes(a ^ b for a, b in zip(index_hash, key_stream_hash))
        encrypted_index_size = index_size ^ ((keystream[10] << 32) | keystream[11])
        encrypted_index_offset = new_index_offset ^ ((keystream[0] << 32) | keystream[1])
        encrypted_flag_byte = (1 if self._pak_info.index_encrypted else 0) ^ (keystream[3] & 0xFF)

        orig_data_region = bytearray(self._file_content[0:orig_index_offset])
        output_pak = Path(output_pak)
        output_pak.parent.mkdir(parents=True, exist_ok=True)
        with open(output_pak, 'wb') as f:
            f.write(bytes(orig_data_region))
            f.write(bytes(new_data_region))
            f.write(encrypted_index)
            if version >= 7:
                key_unk1 = struct.pack('<8I', *keystream[7:][:8])
                unk1_plain = self._pak_info.unk1 if self._pak_info.unk1 else b'\x00' * 32
                encrypted_unk1 = bytes(a ^ b for a, b in zip(unk1_plain, key_unk1))
                f.write(encrypted_unk1)
            if version >= 8:
                f.write(self._pak_info.packed_key if self._pak_info.packed_key else b'\x00' * 256)
                f.write(self._pak_info.packed_iv if self._pak_info.packed_iv else b'\x00' * 256)
                f.write(self._pak_info.packed_index_hash
                        if self._pak_info.packed_index_hash else b'\x00' * 256)
            if version >= 9:
                f.write(struct.pack('<I', (self._pak_info.stem_hash or 0) ^ keystream[8]))
                f.write(struct.pack('<I', (self._pak_info.unk2 or 0) ^ keystream[9]))
            if version >= 12:
                f.write(self._pak_info.content_org_hash
                        if self._pak_info.content_org_hash else b'\x00' * 20)
            f.write(struct.pack('<B', encrypted_flag_byte))
            f.write(struct.pack('<I', encrypted_magic))
            f.write(struct.pack('<I', version))
            if version >= 6:
                f.write(encrypted_index_hash)
            else:
                f.write(b'\x00' * 20)
            f.write(struct.pack('<Q', encrypted_index_size))
            f.write(struct.pack('<Q', encrypted_index_offset))

        # ── STEP 5/5 ─────────────────────────────────────────────────────────
        self._log("INFO STEP 5/5 : DONE")
        try:
            sz = output_pak.stat().st_size
            self._log(f"OK INJECT COMPLETE — {output_pak.name} ({sz:,} bytes)")
        except Exception:
            self._log(f"OK INJECT COMPLETE — {output_pak.name}")

    def __del__(self):
        if hasattr(self, '_file_handle'):
            try:
                self._file_handle.close()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  REPACK — замена файлов внутри существующего PAK
# ══════════════════════════════════════════════════════════════════════════════
def repack_pak_file_full(pak_file, edited_root, output_path, target_path=None,
                         force_add=False, path_map=None,
                         log_callback=None, progress_callback=None):
    """
    Полная пересборка PAK с заменой файлов из edited_root.

    Сигнатура 1-в-1 с tool.py, добавлены log_callback / progress_callback.
    Возвращает количество обработанных файлов (0 — нечего repack'ить).
    Список обработанных файлов — в pak_file.last_file_rows.
    """
    import copy as _cp

    def _log(msg):
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    def _progress(done, total, msg=""):
        if progress_callback:
            try:
                progress_callback(done, total, msg)
            except Exception:
                pass

    edit_files = [p for p in Path(edited_root).rglob('*') if p.is_file()]
    if not edit_files:
        _log(f"ERR No files in EDIT folder: {edited_root}")
        return 0

    version = pak_file._pak_info.version
    keystream = PakCrypto.zuc_keystream()
    orig_fc = pak_file._file_content
    mp_str, all_dirs = _get_all_dirs_and_mp(pak_file)

    def _norm_dir(tp):
        if not tp:
            return None
        tp = tp.replace('\\', '/')
        matched_dir = None
        for existing_dir in all_dirs.keys():
            if existing_dir.strip('/').lower() == tp.strip('/').lower():
                matched_dir = existing_dir
                break
        return matched_dir if matched_dir else (tp.strip('/') + '/')

    if target_path:
        target_path = _norm_dir(target_path)
    norm_path_map = {}
    if path_map:
        for _name, _tp in path_map.items():
            norm_path_map[_name] = _norm_dir(_tp)

    pak_name_map = {}
    for dp_str, dir_files in all_dirs.items():
        for name, (slot, entry) in dir_files.items():
            full_path = str(PurePath(dp_str) / name).replace('\\', '/')
            pak_name_map.setdefault(name.lower(), []).append((full_path, slot, entry))

    # ── Сопоставление файлов из EDIT с записями PAK ──────────────────────────
    edited = {}
    for p in edit_files:
        fl = p.name.lower()
        found_match = False
        if path_map is not None:
            tp = norm_path_map.get(p.name)
        else:
            tp = target_path

        if not found_match:
            rel_path = p.relative_to(edited_root).as_posix()
            mp_norm = mp_str.strip('/')
            if mp_norm and rel_path.startswith(mp_norm + '/'):
                rel_path = rel_path[len(mp_norm) + 1:]
            for dp_str, dir_files in all_dirs.items():
                for name, (slot, entry) in dir_files.items():
                    full_path = str(PurePath(dp_str) / name).replace('\\', '/')
                    if full_path == rel_path or full_path.endswith('/' + rel_path) or rel_path.endswith('/' + name):
                        edited[full_path] = (p, slot, entry, False)
                        found_match = True
                        break
                if found_match:
                    break

        if fl in pak_name_map:
            cands = pak_name_map[fl]
            if tp:
                target_cands = [(fp, s, e) for fp, s, e in cands if tp.strip('/') in fp]
                if target_cands:
                    sz = p.stat().st_size
                    sm = [(fp, s, e) for fp, s, e in target_cands if e.uncompressed_size == sz]
                    fp, s, e = sm[0] if sm else target_cands[0]
                    edited[fp] = (p, s, e, False)
                    found_match = True
            if not found_match:
                sz = p.stat().st_size
                sm = [(fp, s, e) for fp, s, e in cands if e.uncompressed_size == sz]
                if sm:
                    fp, s, e = sm[0]
                else:
                    fp, s, e = cands[0]
                if tp and force_add:
                    new_fp = f"{tp.rstrip('/')}/{p.name}"
                    edited[new_fp] = (p, s, e, True)
                else:
                    edited[fp] = (p, s, e, False)
                found_match = True

        if not found_match:
            stem = p.stem.lower()
            ext = p.suffix.lower()
            for dp_str, dir_files in all_dirs.items():
                for name, (slot, entry) in dir_files.items():
                    if Path(name).stem.lower() == stem and Path(name).suffix.lower() == ext:
                        full_path = str(PurePath(dp_str) / name).replace('\\', '/')
                        if tp and force_add:
                            new_fp = f"{tp.rstrip('/')}/{p.name}"
                            edited[new_fp] = (p, slot, entry, True)
                        else:
                            edited[full_path] = (p, slot, entry, False)
                        found_match = True
                        break
                if found_match:
                    break

        if not found_match and force_add:
            template_entry = None
            for dp_str, dir_files in all_dirs.items():
                for _n, (_s, e) in dir_files.items():
                    if Path(_n).suffix.lower() == p.suffix.lower():
                        template_entry = e
                        break
                if template_entry:
                    break
            if not template_entry:
                for dp_str, dir_files in all_dirs.items():
                    for _n, (_s, e) in dir_files.items():
                        template_entry = e
                        break
                    if template_entry:
                        break
            rel_path = p.relative_to(edited_root).as_posix()
            mp_norm = mp_str.strip('/')
            if mp_norm and rel_path.startswith(mp_norm + '/'):
                rel_path = rel_path[len(mp_norm) + 1:]
            if tp:
                new_fp = f"{tp.rstrip('/')}/{p.name}"
            else:
                new_fp = rel_path
            if template_entry:
                edited[new_fp] = (p, -1, template_entry, True)
                found_match = True
            else:
                _log(f"WARN Skipped (no entry in PAK): {p.name}")

    if not edited:
        _log("ERR No files to repack!")
        return 0

    _log(f"INFO Repacking {len(edited)} file(s) into {Path(output_path).name}")

    slot_to_new = {}
    for i, e in enumerate(pak_file._files):
        ne = _cp.copy(e)
        ne.compressed_blocks = [_cp.copy(b) for b in e.compressed_blocks]
        slot_to_new[i] = ne

    _tmpfd, _tmppath = tempfile.mkstemp(suffix='.pak')
    _outf = open(_tmpfd, 'r+b')
    _pos = [0]

    file_rows = []
    new_added = []
    processed_count = 0
    total_to_process = sum(len(files) for files in all_dirs.values())

    def _out_append(data: bytes):
        start = _pos[0]
        _outf.write(data)
        _pos[0] += len(data)
        return start

    def _out_len() -> int:
        return _pos[0]

    # ── Обработка существующих записей ──────────────────────────────────────
    for dp_str, dir_files in list(all_dirs.items()):
        for name, (slot, old_entry) in list(dir_files.items()):
            full_path = str(PurePath(dp_str) / name).replace('\\', '/')
            ne = slot_to_new[slot]
            em = old_entry.encryption_method
            cm = old_entry.compression_method

            if full_path in edited:
                p, _s, template, is_new = edited[full_path]
                new_raw = p.read_bytes()
                pak_rel = PurePath(full_path)

                ne.uncompressed_size = len(new_raw)
                ne.compression_method = cm
                ne.encryption_method = em
                ne.encrypted = old_entry.encrypted
                ne.unk1 = old_entry.unk1
                ne.index_new_sep = old_entry.index_new_sep

                if is_new and (target_path or path_map):
                    full_path_str = mp_str + full_path
                    ne.unk2 = SHA1.new(full_path_str.lower().encode('utf-8')).digest()
                else:
                    ne.unk2 = old_entry.unk2

                stored_start = _out_len()
                if cm == CM_NONE:
                    cipher = (encrypt_plaintext(new_raw, pak_rel, em) if ne.encrypted else new_raw)
                    ne.offset = _out_len()
                    ne.size = len(new_raw)
                    _out_append(cipher)
                else:
                    cs = old_entry.compression_block_size if old_entry.compression_block_size > 0 else 65536
                    chunks = [new_raw[i:i + cs] for i in range(0, len(new_raw), cs)]
                    order = _block_permutation(len(chunks), em)
                    cipher_by_logical = []
                    for chunk in chunks:
                        compressed = best_compress(chunk, cm, pak_file._zstd_dict)
                        cipher = (encrypt_plaintext(compressed, pak_rel, em) if ne.encrypted else compressed)
                        cipher_by_logical.append(cipher)
                    inv = [0] * len(chunks)
                    for logical_i, phys_i in enumerate(order):
                        inv[phys_i] = logical_i
                    new_blks = [None] * len(chunks)
                    for phys_i in range(len(chunks)):
                        blk = PakCompressedBlock.__new__(PakCompressedBlock)
                        blk.start = _out_len()
                        _out_append(cipher_by_logical[inv[phys_i]])
                        blk.end = _out_len()
                        new_blks[phys_i] = blk
                    ne.compressed_blocks = new_blks
                    ne.offset = new_blks[0].start if new_blks else _out_len()
                    ne.size = sum(b.end - b.start for b in new_blks)

                _outf.seek(stored_start)
                stored_bytes = _outf.read(ne.size)
                _outf.seek(0, 2)
                ne.content_hash = SHA1.new(stored_bytes).digest()

                file_rows.append((full_path, len(new_raw), ne.size))
                processed_count += 1
                _progress(processed_count, total_to_process, f"Processing Assets... [{processed_count}/{total_to_process}]")
            else:
                if cm == CM_NONE:
                    read_sz = (PakCrypto.align_encrypted_content_size(old_entry.size, em)
                               if old_entry.encrypted else old_entry.size)
                    ne.offset = _out_len()
                    _out_append(bytes(orig_fc[old_entry.offset: old_entry.offset + read_sz]))
                elif old_entry.compressed_blocks:
                    new_blks = []
                    for ob in old_entry.compressed_blocks:
                        unc = ob.end - ob.start
                        enc = (PakCrypto.align_encrypted_content_size(unc, em)
                               if old_entry.encrypted else unc)
                        nb = PakCompressedBlock.__new__(PakCompressedBlock)
                        nb.start = _out_len()
                        _out_append(bytes(orig_fc[ob.start: ob.start + enc]))
                        nb.end = _out_len()
                        new_blks.append(nb)
                    ne.compressed_blocks = new_blks
                    ne.offset = new_blks[0].start if new_blks else _out_len()

    _progress(processed_count, total_to_process, f"All {processed_count} assets processed")

    # ── Добавление НОВЫХ записей ────────────────────────────────────────────
    if force_add:
        for fp, (p, slot, template, is_new) in edited.items():
            if not is_new or slot >= 0:
                continue
            already = False
            for dp_str, dir_files in all_dirs.items():
                for _n, (_s, _e) in dir_files.items():
                    if str(PurePath(dp_str) / _n).replace('\\', '/') == fp:
                        already = True
                        break
                if already:
                    break
            if already:
                continue

            ne = _cp.copy(template)
            new_raw = p.read_bytes()
            pak_rel = PurePath(fp)
            ne.uncompressed_size = len(new_raw)
            ne.compression_method = template.compression_method
            ne.compressed_blocks = []
            ne.compression_block_size = template.compression_block_size
            ne.encryption_method = template.encryption_method
            ne.encrypted = template.encrypted
            ne.unk1 = template.unk1
            full_path_str = mp_str + fp
            ne.unk2 = SHA1.new(full_path_str.lower().encode('utf-8')).digest()
            ne.index_new_sep = template.index_new_sep

            stored_start = _out_len()
            if ne.compression_method == CM_NONE:
                cipher = (encrypt_plaintext(new_raw, pak_rel, ne.encryption_method)
                          if ne.encrypted else new_raw)
                ne.offset = _out_len()
                ne.size = len(new_raw)
                _out_append(cipher)
            else:
                cs = template.compression_block_size if template.compression_block_size > 0 else 65536
                chunks = [new_raw[i:i + cs] for i in range(0, len(new_raw), cs)]
                order = _block_permutation(len(chunks), ne.encryption_method)
                cipher_by_logical = []
                for chunk in chunks:
                    compressed = best_compress(chunk, ne.compression_method, pak_file._zstd_dict)
                    cipher = (encrypt_plaintext(compressed, pak_rel, ne.encryption_method)
                              if ne.encrypted else compressed)
                    cipher_by_logical.append(cipher)
                inv = [0] * len(chunks)
                for logical_i, phys_i in enumerate(order):
                    inv[phys_i] = logical_i
                new_blks = [None] * len(chunks)
                for phys_i in range(len(chunks)):
                    blk = PakCompressedBlock.__new__(PakCompressedBlock)
                    blk.start = _out_len()
                    _out_append(cipher_by_logical[inv[phys_i]])
                    blk.end = _out_len()
                    new_blks[phys_i] = blk
                ne.compressed_blocks = new_blks
                ne.offset = new_blks[0].start if new_blks else _out_len()
                ne.size = sum(b.end - b.start for b in new_blks)

            _outf.seek(stored_start)
            stored_bytes = _outf.read(ne.size)
            _outf.seek(0, 2)
            ne.content_hash = SHA1.new(stored_bytes).digest()

            if path_map is not None:
                _nk = norm_path_map.get(p.name)
                _dir_key = _nk if _nk else ''
            else:
                _dir_key = target_path
            new_slot = len(slot_to_new) + len(new_added)
            new_added.append((_dir_key, p.name, ne, new_slot))
            file_rows.append((fp, len(new_raw), ne.size))

    max_slot = max(slot_to_new.keys()) if slot_to_new else -1
    new_files = [slot_to_new[i] for i in range(max_slot + 1)]
    dir_to_added = {}
    for dir_key, name, ne, new_slot in new_added:
        new_files.append(ne)
        dir_to_added.setdefault(dir_key, []).append((name, ne, new_slot))

    for dir_key, items in dir_to_added.items():
        if dir_key not in all_dirs:
            all_dirs[dir_key] = {}
        for name, ne, new_slot in items:
            all_dirs[dir_key][name] = (new_slot, ne)

    # ── Индекс ──────────────────────────────────────────────────────────────
    idx = bytearray(_pw_string(mp_str))
    idx += struct.pack('<I', len(new_files))
    for ne in new_files:
        idx += _pw_entry(ne, version)
    idx += struct.pack('<Q', len(all_dirs))
    for dp_str, dir_files in all_dirs.items():
        idx += _pw_string(dp_str)
        idx += struct.pack('<Q', len(dir_files))
        for name, (slot, _old_e) in dir_files.items():
            idx += _pw_string(name)
            idx += struct.pack('<i', ~slot)

    index_plain = bytes(idx)
    new_sha1 = SHA1.new(index_plain).digest()

    if pak_file._pak_info.index_encrypted:
        index_bytes = _encrypt_index_aes(index_plain, pak_file._pak_info)
    else:
        index_bytes = index_plain

    new_idx_offset = _out_len()
    new_idx_size = len(index_bytes)
    _out_append(index_bytes)

    footer_sz = TencentPakInfo._mem_size(version)
    new_footer = bytearray(orig_fc[-footer_sz:])
    h_key = struct.pack('<5I', *keystream[4:9])
    new_footer[-36:-16] = bytes(a ^ b for a, b in zip(new_sha1, h_key))
    new_footer[-16:-8] = ((new_idx_size ^ (keystream[10] << 32 | keystream[11])).to_bytes(8, 'little'))
    new_footer[-8:] = ((new_idx_offset ^ (keystream[0] << 32 | keystream[1])).to_bytes(8, 'little'))
    _out_append(new_footer)

    _outf.flush()
    _outf.close()
    shutil.copy2(_tmppath, output_path)
    os.unlink(_tmppath)

    pak_file.last_file_rows = file_rows
    for fp, orig_sz, stored_sz in file_rows:
        _log(f"INFO   {fp}  {orig_sz:,} -> {stored_sz:,}")

    return len(edited)


def _encrypt_index_aes(index_plain: bytes, pak_info) -> bytes:
    """Шифрование индекса AES-CBC при index_encrypted (для repack/build)."""
    from .constants import RSA_MOD_1
    try:
        from Crypto.Cipher import AES
        from Crypto.Cipher.AES import MODE_CBC
        key = PakCrypto.rsa_extract(pak_info.packed_key, RSA_MOD_1)
        iv = PakCrypto.rsa_extract(pak_info.packed_iv, RSA_MOD_1)
        if key and iv and len(key) == 32 and len(iv) >= 16:
            aes = AES.new(key, MODE_CBC, iv[:16])
            p = (-len(index_plain)) % AES.block_size or AES.block_size
            return aes.encrypt(index_plain + bytes([p] * p))
        else:
            return index_plain
    except Exception:
        return index_plain


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD — новый PAK из шаблона
# ══════════════════════════════════════════════════════════════════════════════
def build_new_pak_from_template(template_pak_path: Path, edit_dir: Path, output_path: Path,
                                target_path: str = None, path_map: dict = None,
                                log_callback=None, progress_callback=None):
    """
    Собрать новый PAK, взяв настройки (сжатие/шифрование/блоки) из шаблона.
    Возвращает количество добавленных файлов (0 — ошибка).
    Логика 1-в-1 из tool.py.
    """
    import copy as _cp

    def _log(msg):
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    def _progress(done, total, msg=""):
        if progress_callback:
            try:
                progress_callback(done, total, msg)
            except Exception:
                pass

    _log(f"INFO Building NEW PAK using template: {Path(template_pak_path).name}")
    pak_file = TencentPakFile(template_pak_path, is_od=True,
                              log_callback=log_callback, progress_callback=progress_callback)
    version = pak_file._pak_info.version
    keystream = PakCrypto.zuc_keystream()
    mp_str, _all_dirs_orig = _get_all_dirs_and_mp(pak_file)

    template_entry = None
    for _dir_path, files in pak_file._index.items():
        for _name, entry in files.items():
            template_entry = entry
            break
        if template_entry:
            break
    if template_entry is None:
        _log("ERR No file found in the Template PAK to copy settings from!")
        return 0

    edit_files = [p for p in Path(edit_dir).rglob('*') if p.is_file()]
    if not edit_files:
        _log(f"ERR No file found in the EDIT folder: {edit_dir}")
        return 0

    out_buf = bytearray()
    new_files = []
    all_dirs = {}
    file_rows = []

    for i, p in enumerate(edit_files):
        rel = p.relative_to(edit_dir).as_posix()
        if path_map is not None:
            tp_for_file = path_map.get(p.name)
            if tp_for_file is None:
                tp_for_file = ''
            if tp_for_file == '':
                parent = str(PurePath(rel).parent).replace('\\', '/')
                dir_key = '' if parent == '.' else parent + '/'
                fp = rel
            else:
                dir_key = tp_for_file.rstrip('/') + '/'
                fp = f"{tp_for_file.rstrip('/')}/{p.name}"
        elif target_path:
            fp = f"{target_path.rstrip('/')}/{p.name}"
            dir_key = target_path.rstrip('/') + '/'
        else:
            parent = str(PurePath(rel).parent).replace('\\', '/')
            dir_key = '' if parent == '.' else parent + '/'
            fp = rel

        ne = _cp.copy(template_entry)
        new_raw = p.read_bytes()
        pak_rel = PurePath(fp)

        ne.uncompressed_size = len(new_raw)
        ne.compression_method = template_entry.compression_method
        ne.encryption_method = template_entry.encryption_method
        ne.encrypted = template_entry.encrypted
        ne.unk1 = template_entry.unk1
        full_path_str = mp_str + fp
        ne.unk2 = SHA1.new(full_path_str.lower().encode('utf-8')).digest()
        ne.index_new_sep = template_entry.index_new_sep

        stored_start = len(out_buf)
        if ne.compression_method == CM_NONE:
            cipher = (encrypt_plaintext(new_raw, pak_rel, ne.encryption_method)
                      if ne.encrypted else new_raw)
            ne.offset = len(out_buf)
            ne.size = len(new_raw)
            out_buf += cipher
        else:
            cs = template_entry.compression_block_size if template_entry.compression_block_size > 0 else 65536
            chunks = [new_raw[i:i + cs] for i in range(0, len(new_raw), cs)]
            order = _block_permutation(len(chunks), ne.encryption_method)
            cipher_by_logical = []
            for chunk in chunks:
                compressed = best_compress(chunk, ne.compression_method, pak_file._zstd_dict)
                cipher = (encrypt_plaintext(compressed, pak_rel, ne.encryption_method)
                          if ne.encrypted else compressed)
                cipher_by_logical.append(cipher)
            inv = [0] * len(chunks)
            for logical_i, phys_i in enumerate(order):
                inv[phys_i] = logical_i
            new_blks = [None] * len(chunks)
            for phys_i in range(len(chunks)):
                blk = PakCompressedBlock.__new__(PakCompressedBlock)
                blk.start = len(out_buf)
                blk.end = blk.start + len(cipher_by_logical[inv[phys_i]])
                out_buf += cipher_by_logical[inv[phys_i]]
                new_blks[phys_i] = blk
            ne.compressed_blocks = new_blks
            ne.offset = new_blks[0].start if new_blks else len(out_buf)
            ne.size = sum(b.end - b.start for b in new_blks)

        stored_bytes = bytes(out_buf[ne.offset:ne.offset + ne.size])
        ne.content_hash = SHA1.new(stored_bytes).digest()

        new_files.append(ne)
        all_dirs.setdefault(dir_key, {})[p.name] = ne
        file_rows.append((fp, ne.uncompressed_size, ne.size))
        _progress(i + 1, len(edit_files), p.name)

    for fp, orig_sz, stored_sz in file_rows:
        _log(f"INFO   {fp}  {orig_sz:,} -> {stored_sz:,}")

    id_to_idx = {id(ne): i for i, ne in enumerate(new_files)}

    idx = bytearray(_pw_string(mp_str))
    idx += struct.pack('<I', len(new_files))
    for ne in new_files:
        idx += _pw_entry(ne, version)
    idx += struct.pack('<Q', len(all_dirs))
    for dp_str, dir_files in all_dirs.items():
        idx += _pw_string(dp_str)
        idx += struct.pack('<Q', len(dir_files))
        for name, e in dir_files.items():
            idx += _pw_string(name)
            idx += struct.pack('<i', ~id_to_idx[id(e)])

    index_plain = bytes(idx)
    new_sha1 = SHA1.new(index_plain).digest()

    if pak_file._pak_info.index_encrypted:
        index_bytes = _encrypt_index_aes(index_plain, pak_file._pak_info)
    else:
        index_bytes = index_plain

    new_idx_offset = len(out_buf)
    new_idx_size = len(index_bytes)
    out_buf += index_bytes

    orig_fc = pak_file._file_content
    footer_sz = TencentPakInfo._mem_size(version)
    new_footer = bytearray(orig_fc[-footer_sz:])

    h_key = struct.pack('<5I', *keystream[4:9])
    new_footer[-36:-16] = bytes(a ^ b for a, b in zip(new_sha1, h_key))
    new_footer[-16:-8] = ((new_idx_size ^ (keystream[10] << 32 | keystream[11])).to_bytes(8, 'little'))
    new_footer[-8:] = ((new_idx_offset ^ (keystream[0] << 32 | keystream[1])).to_bytes(8, 'little'))
    out_buf += new_footer

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(out_buf)

    _log(f"OK New PAK written: {output_path}")
    _log(f"OK Files included: {len(new_files)}")

    # Верификация
    try:
        TencentPakFile(output_path, is_od=True,
                       log_callback=lambda l: _log(f"INFO verify: {l}"))
        _log("OK Verification passed")
    except AssertionError:
        _log("ERR VERIFICATION FAILED (index hash mismatch)")
    except Exception as e:
        _log(f"ERR VERIFICATION FAILED: {e}")

    pak_file.last_file_rows = file_rows
    return len(new_files)


# ══════════════════════════════════════════════════════════════════════════════
#  ВЫСОКОУРОВНЕВЫЕ ДЕЙСТВИЯ (без UI — вызываются из экранов)
# ══════════════════════════════════════════════════════════════════════════════
def unpack_pak(pak_path, out_dir=None, log_callback=None, progress_callback=None):
    """
    action_unpack_pak() из tool.py, но без консоли.
    Возвращает (ok, out_path_or_error).
    """
    from . import paths

    pak_path = Path(pak_path)
    if out_dir is None:
        out_dir = paths.PAK_UNPACK_DIR / pak_path.stem
    out_dir = Path(out_dir)

    def _log(m):
        if log_callback:
            log_callback(m)

    try:
        _log(f"INFO Loading {pak_path.name} ...")
        pak = TencentPakFile(pak_path, log_callback=log_callback,
                             progress_callback=progress_callback)
        info = pak.info()
        _log(f"INFO version={info['version']} mount={info['mount_point'] or '/'} "
             f"files={info['files']} dirs={info['dirs']}")
        out_dir.mkdir(parents=True, exist_ok=True)
        _log(f"INFO Extracting to {out_dir}")
        pak.dump(out_dir)
        _log(f"OK Extracted to {out_dir}")
        return True, str(out_dir)
    except Exception as e:
        _log(f"ERR {e}")
        return False, str(e)


def repack_to_path(pak_path, target_path, log_callback=None, progress_callback=None):
    """action_repack_inject() из tool.py: файлы из COMPILED -> target_path."""
    from . import paths

    pak_path = Path(pak_path)
    edit_dir = paths.COMPILED_DIR
    result_dir = paths.RESULT_DIR

    def _log(m):
        if log_callback:
            log_callback(m)

    if not edit_dir.exists() or not any(edit_dir.iterdir()):
        _log(f"ERR No files in COMPILED folder: {edit_dir}")
        return False, "COMPILED folder is empty"

    target_path = (target_path or paths_default_target()).replace('\\', '/').strip('/')
    if not target_path:
        _log("ERR Invalid target path")
        return False, "Invalid target path"

    try:
        _log(f"INFO Adding files to {target_path} in {pak_path.name}")
        pak = TencentPakFile(pak_path, log_callback=log_callback)
        result_dir.mkdir(parents=True, exist_ok=True)
        output_pak = result_dir / pak_path.name
        count = repack_pak_file_full(pak, edit_dir, output_pak, target_path,
                                     force_add=True,
                                     log_callback=log_callback,
                                     progress_callback=progress_callback)
        if count > 0:
            _log(f"OK Processed {count} files to {target_path} -> {output_pak}")
            return True, str(output_pak)
        _log("ERR No files were processed")
        return False, "No files were processed"
    except Exception as e:
        _log(f"ERR Repack failed: {e}")
        return False, str(e)


def build_new_pak(template_pak_path, target_path="", log_callback=None, progress_callback=None):
    """action_build_new_pak() из tool.py: новый PAK из шаблона + COMPILED."""
    from . import paths

    template_pak_path = Path(template_pak_path)
    edit_dir = paths.COMPILED_DIR
    result_dir = paths.RESULT_DIR

    def _log(m):
        if log_callback:
            log_callback(m)

    if not edit_dir.exists() or not any(edit_dir.iterdir()):
        _log(f"ERR No files in COMPILED folder: {edit_dir}")
        return False, "COMPILED folder is empty"

    target_path = (target_path or '').replace('\\', '/').strip('/')
    output_pak = result_dir / template_pak_path.name
    result_dir.mkdir(parents=True, exist_ok=True)

    try:
        count = build_new_pak_from_template(template_pak_path, edit_dir, output_pak,
                                            target_path,
                                            log_callback=log_callback,
                                            progress_callback=progress_callback)
        if count > 0:
            _log(f"OK New PAK built with {count} files!")
            _log(f"OK Output: {output_pak}")
            return True, str(output_pak)
        _log("ERR Build failed - no files processed")
        return False, "no files processed"
    except Exception as e:
        _log(f"ERR Build failed: {e}")
        return False, str(e)


def inject_lua_into_pak(pak_path, target_path="", log_callback=None, progress_callback=None):
    """action_inject_lua() из tool.py: инжект COMPILED в PAK без пересборки."""
    from . import paths

    pak_path = Path(pak_path)
    edit_dir = paths.COMPILED_DIR
    out_path = paths.RESULT_DIR

    def _log(m):
        if log_callback:
            log_callback(m)

    files_in_edit = paths.get_compiled_files(recursive=True)
    if not files_in_edit:
        _log(f"ERR COMPILED folder is empty: {edit_dir}")
        return False, "COMPILED folder is empty"

    base_path = (target_path or '').replace('\\', '/').strip('/')
    if base_path and not base_path.endswith('/'):
        base_path += '/'

    _log(f"INFO {len(files_in_edit)} file(s) will be injected")

    # Бэкап оригинала (как в tool.py)
    bak = paths.make_backup(pak_path, log=log_callback)

    try:
        out_path.mkdir(parents=True, exist_ok=True)
        _log(f"INFO Loading PAK file {pak_path.name} ...")
        pak = TencentPakFile(pak_path, log_callback=log_callback)

        output_name = f"{pak_path.stem}_MODIFIED.pak"
        output_pak = out_path / output_name

        dominant = pak.detect_dominant_style()
        _log(f"INFO Dominant style: comp={dominant['comp_method']} "
             f"enc={dominant['enc_method']} encrypted={dominant['encrypted']} "
             f"block={dominant['block_size']}")

        inject_plan = []
        for f in files_in_edit:
            internal_path = f"{base_path}{f.name}" if base_path else f.name
            if internal_path.startswith('/'):
                internal_path = internal_path[1:]
            inject_plan.append({
                'src_path': f,
                'internal_path': internal_path,
                'comp_method': dominant['comp_method'],
                'enc_method': dominant['enc_method'],
                'encrypted': dominant['encrypted'],
                'block_size': dominant['block_size'],
            })

        _log(f"INFO Plan: {len(inject_plan)} file(s)")
        pak.inject_files(inject_plan, Path(output_pak))
        _log(f"OK Repack complete! Output: {output_pak}")
        return True, str(output_pak)
    except Exception as e:
        _log(f"ERR {e}")
        return False, str(e)


def paths_default_target():
    from .constants import DEFAULT_REPACK_TARGET_PATH
    return DEFAULT_REPACK_TARGET_PATH