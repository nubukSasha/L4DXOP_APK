# -*- coding: utf-8 -*-
"""
=================================================================================
  L4DXOP UNLIMITED LUA TOOL  ·  core.lua_codec
---------------------------------------------------------------------------------
  Конвертация BGMI-байткода <-> стандартный Lua 5.3 байткод.

  Перенесено 1-в-1 из tool.py (строки 358-555):
      BinaryReader, BinaryWriter, _convert_function,
      bgmi_to_std, std_to_bgmi, convert_file, repack_to_pubg

  Никаких print()/input() — чистые функции, возвращают данные.

  CREDIT: @L4DXOP
=================================================================================
"""

import os
import shutil
import struct
from typing import Optional, Tuple

from .constants import (
    BGMI_TO_STD,
    STD_TO_BGMI,
    STD_FMT,
    STRING_XOR_KEY,
    HEADER_SIZE,
    LUA_MAGIC,
    iABC, iABx, iAsBx, iAx,
)


# ══════════════════════════════════════════════════════════════════════════════
#  ЧИТАЕТ / ПИСАТЕЛЬ БИНАРНЫХ ДАННЫХ
# ══════════════════════════════════════════════════════════════════════════════
class BinaryReader:
    """Чтение примитивов Lua-чанка. data[pos:] — текущая позиция."""

    def __init__(self, data: bytes, sizet: int = 4):
        self.data = bytearray(data)
        self.pos = 0
        self.sizet = sizet

    def byte(self) -> int:
        if self.pos >= len(self.data):
            raise EOFError()
        v = self.data[self.pos]
        self.pos += 1
        return v

    def int32(self) -> int:
        if self.pos + 4 > len(self.data):
            raise EOFError()
        v = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += 4
        return v

    def uint32(self) -> int:
        if self.pos + 4 > len(self.data):
            raise EOFError()
        v = struct.unpack_from('<I', self.data, self.pos)[0]
        self.pos += 4
        return v

    def double(self) -> float:
        if self.pos + 8 > len(self.data):
            raise EOFError()
        v = struct.unpack_from('<d', self.data, self.pos)[0]
        self.pos += 8
        return v

    def int64(self) -> int:
        if self.pos + 8 > len(self.data):
            raise EOFError()
        v = struct.unpack_from('<q', self.data, self.pos)[0]
        self.pos += 8
        return v

    def bytes(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError()
        v = self.data[self.pos:self.pos + n]
        self.pos += n
        return bytes(v)

    def pubg_string(self) -> Optional[str]:
        """Строка с XOR-шифрованием (формат PUBG/BGMI)."""
        sz = self.byte()
        if sz == 0xFF:
            sz = self.uint32()
        if sz == 0:
            return None
        sz -= 1
        enc = self.bytes(sz)
        dec = bytes(enc[i] ^ STRING_XOR_KEY[i % 32] for i in range(len(enc)))
        try:
            return dec.decode('utf-8', errors='replace')
        except Exception:
            return dec.decode('latin-1')

    def std_string(self) -> Optional[str]:
        """Обычная строка без шифрования (формат std Lua)."""
        sz = self.byte()
        if sz == 0xFF:
            if self.sizet == 8:
                if self.pos + 8 > len(self.data):
                    raise EOFError()
                sz = struct.unpack_from('<Q', self.data, self.pos)[0]
                self.pos += 8
            else:
                sz = self.uint32()
        if sz == 0:
            return None
        sz -= 1
        raw = self.bytes(sz)
        try:
            return raw.decode('utf-8', errors='replace')
        except Exception:
            return raw.decode('latin-1')


class BinaryWriter:
    """Запись примитивов Lua-чанка."""

    def __init__(self):
        self.buf = bytearray()

    def byte(self, v):
        self.buf.append(v & 0xFF)

    def int32(self, v):
        self.buf.extend(struct.pack('<i', v))

    def uint32(self, v):
        self.buf.extend(struct.pack('<I', v))

    def int64(self, v):
        self.buf.extend(struct.pack('<q', v))

    def double(self, v):
        self.buf.extend(struct.pack('<d', v))

    def raw(self, data):
        self.buf.extend(data)

    def lua_string(self, s: Optional[str], is_pubg: bool = False):
        if s is None:
            self.byte(0)
            return
        e = s.encode('utf-8') if isinstance(s, str) else s
        sz = len(e) + 1
        if sz < 0xFF:
            self.byte(sz)
        else:
            self.byte(0xFF)
            self.uint32(sz)
        if is_pubg:
            enc = bytes(e[i] ^ STRING_XOR_KEY[i % 32] for i in range(len(e)))
            self.raw(enc)
        else:
            self.raw(e)

    def lua_inst(self, op, A, B, C, Bx, sBx, Ax, fmt):
        op &= 0x3F
        if fmt == iABC:
            r = op | ((A & 0xFF) << 6) | ((C & 0x1FF) << 14) | ((B & 0x1FF) << 23)
        elif fmt == iABx:
            r = op | ((A & 0xFF) << 6) | ((Bx & 0x3FFFF) << 14)
        elif fmt == iAsBx:
            r = op | ((A & 0xFF) << 6) | (((sBx + 131071) & 0x3FFFF) << 14)
        elif fmt == iAx:
            r = op | ((Ax & 0x3FFFFFF) << 6)
        else:
            r = 0
        self.uint32(r)

    def get_data(self) -> bytes:
        return bytes(self.buf)


# ══════════════════════════════════════════════════════════════════════════════
#  КОНВЕРТАЦИЯ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════════════════
def _convert_function(reader: BinaryReader, writer: BinaryWriter, to_std: bool = True):
    """
    Рекурсивный обход прототипа функции с перестановкой опкодов.
    to_std=True  : BGMI -> std Lua
    to_std=False : std Lua -> BGMI
    """
    src = reader.pubg_string() if to_std else reader.std_string()
    writer.lua_string(src, is_pubg=(not to_std))

    linedefined = reader.int32()
    writer.int32(linedefined)

    writer.int32(reader.int32())
    writer.byte(reader.byte())
    writer.byte(reader.byte())
    writer.byte(reader.byte())

    csz = reader.uint32()
    writer.uint32(csz)
    opmap = BGMI_TO_STD if to_std else STD_TO_BGMI
    for _ in range(csz):
        raw = reader.uint32()
        bop = raw & 0x3F
        A = (raw >> 6) & 0xFF
        B = (raw >> 23) & 0x1FF
        C = (raw >> 14) & 0x1FF
        Bx = (raw >> 14) & 0x3FFFF
        sBx = Bx - 131071
        Ax = (raw >> 6) & 0x3FFFFFF
        sop = opmap[bop] if bop < len(opmap) else bop
        fmt = STD_FMT[sop] if sop < len(STD_FMT) else iABC
        writer.lua_inst(sop, A, B, C, Bx, sBx, Ax, fmt)

    nk = reader.uint32()
    writer.uint32(nk)
    for _ in range(nk):
        t = reader.byte()
        writer.byte(t)
        if t == 0:
            pass
        elif t == 1:
            writer.byte(reader.byte())
        elif t == 3:
            writer.double(reader.double())
        elif t == 19:
            writer.int64(reader.int64())
        elif t in (4, 20):
            s = reader.pubg_string() if to_std else reader.std_string()
            writer.lua_string(s, is_pubg=(not to_std))
        else:
            raise ValueError(f"Unknown constant type 0x{t:02X}")

    nups = reader.uint32()
    writer.uint32(nups)
    for _ in range(nups):
        writer.byte(reader.byte())
        writer.byte(reader.byte())

    npts = reader.uint32()
    writer.uint32(npts)
    for _ in range(npts):
        _convert_function(reader, writer, to_std)

    nln = reader.uint32()
    if to_std:
        # BGMI: дельта-байты -> абсолютные номера строк
        lines = []
        cur = linedefined
        for _ in range(nln):
            d = reader.byte()
            cur += d if d <= 127 else d - 256
            lines.append(cur)
        writer.uint32(len(lines))
        for ln in lines:
            writer.int32(ln)
        nab = reader.uint32()
        for _ in range(nab):
            reader.uint32()
            reader.uint32()
    else:
        # std: абсолютные номера -> дельта-байты
        lines = [reader.int32() for _ in range(nln)]
        writer.uint32(len(lines))
        prev = linedefined
        for ln in lines:
            delta = ln - prev
            if -128 <= delta <= 127:
                writer.byte(delta & 0xFF)
            else:
                writer.byte(0x00)
                writer.int32(delta)
            prev = ln
        writer.uint32(0)

    nloc = reader.uint32()
    writer.uint32(nloc)
    for _ in range(nloc):
        s = reader.pubg_string() if to_std else reader.std_string()
        writer.lua_string(s, is_pubg=(not to_std))
        writer.int32(reader.int32())
        writer.int32(reader.int32())

    nupn = reader.uint32()
    writer.uint32(nupn)
    for _ in range(nupn):
        s = reader.pubg_string() if to_std else reader.std_string()
        writer.lua_string(s, is_pubg=(not to_std))


# ══════════════════════════════════════════════════════════════════════════════
#  ПУБЛИЧНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════════════════
def is_lua_bytecode(path) -> bool:
    """Быстрая проверка сигнатуры 0x1B 'Lua'."""
    try:
        with open(path, 'rb') as f:
            return f.read(4) == LUA_MAGIC
    except Exception:
        return False


def bgmi_to_std(data: bytes) -> bytes:
    """BGMI-байткод -> std Lua 5.3 байткод."""
    if data[:4] != LUA_MAGIC:
        raise ValueError("Not a valid Lua bytecode file")
    reader = BinaryReader(data, sizet=4)
    writer = BinaryWriter()
    hdr = bytearray(data[:HEADER_SIZE])
    hdr[13] = 4
    writer.raw(hdr)
    reader.pos = HEADER_SIZE
    nibble_flag = reader.byte()
    writer.byte(nibble_flag)
    _convert_function(reader, writer, to_std=True)
    return writer.get_data()


def std_to_bgmi(data: bytes) -> bytes:
    """std Lua 5.3 байткод -> BGMI-байткод."""
    if data[:4] != LUA_MAGIC:
        raise ValueError("Not a valid Lua bytecode file")
    sizet = data[13] if data[13] in (4, 8) else 4
    reader = BinaryReader(data, sizet=sizet)
    writer = BinaryWriter()
    hdr = bytearray(data[:HEADER_SIZE])
    hdr[13] = 4
    writer.raw(hdr)
    reader.pos = HEADER_SIZE
    nibble_flag = reader.byte()
    writer.byte(nibble_flag)
    _convert_function(reader, writer, to_std=False)
    return writer.get_data()


def convert_file(inp: str, outp: str = None) -> Tuple[bool, str]:
    """
    BGMI .luac/.slua -> .std.luac.
    Если это не Lua-байткод — просто копирует файл (как в tool.py).
    """
    if not outp:
        outp = os.path.splitext(inp)[0] + '.std.luac'
    try:
        with open(inp, 'rb') as f:
            data = f.read()
    except Exception as e:
        return False, f"Cannot read input file: {e}"

    if len(data) < 34 or data[:4] != LUA_MAGIC:
        try:
            shutil.copy2(inp, outp)
            return True, outp
        except Exception:
            return False, "Failed to copy non-Lua file"

    # nibble-флаг: >2 -> сброс, >1 -> побайтовый обмен нибблов
    nibble_flag = data[33]
    if nibble_flag > 2:
        nibble_flag = 0
        data = bytearray(data)
        data[33] = 0
        data = bytes(data)
    if nibble_flag > 1:
        fixed = bytearray(data[:34])
        for i in range(34, len(data)):
            b = data[i]
            fixed.append(((b << 4) & 0xF0) | ((b >> 4) & 0x0F))
        data = bytes(fixed)

    try:
        std_data = bgmi_to_std(data)
        with open(outp, 'wb') as f:
            f.write(std_data)
        return True, outp
    except Exception:
        # как в tool.py: не смогли — отдаём копию, чтобы файл не потерялся
        try:
            shutil.copy2(inp, outp)
            return True, outp
        except Exception:
            return False, "Conversion failed"


def repack_to_pubg(std_luac_path: str, original_pubg_path: str,
                   outp: str = None, pad_to_size: int = None) -> Tuple[bool, str]:
    """
    std .luac -> BGMI .luac с восстановлением заголовка и nibble-флага оригинала.
    pad_to_size — дописать нулями до размера оригинала (обход хеш- проверок).
    """
    if not outp:
        outp = os.path.splitext(std_luac_path)[0] + '.pubg.luac'
    try:
        with open(original_pubg_path, 'rb') as f:
            orig_data = f.read()
    except Exception as e:
        return False, f"Cannot read original: {e}"

    if len(orig_data) < 34 or orig_data[:4] != LUA_MAGIC:
        return False, "Original not valid Lua bytecode"

    header = orig_data[:33]
    nibble_flag = orig_data[33]
    if nibble_flag > 2:
        nibble_flag = 0

    try:
        with open(std_luac_path, 'rb') as f:
            std_data = f.read()
    except Exception as e:
        return False, f"Cannot read std luac: {e}"

    try:
        bgmi_data = std_to_bgmi(std_data)
        bgmi_data = header + bytes([nibble_flag]) + bgmi_data[34:]
        if nibble_flag > 1:
            data_list = bytearray(bgmi_data[:34])
            for i in range(34, len(bgmi_data)):
                b = bgmi_data[i]
                data_list.append(((b << 4) & 0xF0) | ((b >> 4) & 0x0F))
            bgmi_data = bytes(data_list)
        if pad_to_size is not None and len(bgmi_data) < pad_to_size:
            bgmi_data += b'\x00' * (pad_to_size - len(bgmi_data))
        with open(outp, 'wb') as f:
            f.write(bgmi_data)
        return True, outp
    except Exception as e:
        return False, f"Repack failed: {e}"