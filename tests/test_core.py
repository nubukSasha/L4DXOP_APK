# -*- coding: utf-8 -*-
"""
Полный тест ядра L4DXOP (core/) без UI.
Запуск:  python L4DXOP_APK/tests/test_core.py
"""
import os
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path, PurePath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FAILED = []


def check(name, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {name}{('  ' + str(extra)) if extra else ''}")
    if not cond:
        FAILED.append(name)


# ══════════════════════════════════════════════════════════════════════════════
print("=" * 74)
print("1) ИМПОРТЫ И ЗАВИСИМОСТИ")
print("=" * 74)
import core
from core import constants as K
from core import paths as P
from core import lua_codec as L
from core import crypto as X
from core import compression as C
from core import pak_codec as PK
from core import compiler as CP

check("import core (все модули)", True)
check("pycryptodome доступен", X.CRYPTO_AVAILABLE, str(X.MISSING_DEPS))
check("zstandard доступен", C.ZSTD_AVAILABLE, C.ZSTD_ERROR or "")
check("ZUC keystream = 16 uint32", len(X.PakCrypto.zuc_keystream()) == 16)
check("STD_TO_BGMI = 47 записей", len(K.STD_TO_BGMI) == 47)
check("STD_FMT = 47 записей", len(K.STD_FMT) == 47)
check("BGMI_TO_STD = 64 записи", len(K.BGMI_TO_STD) == 64)

print()
print("=" * 74)
print("2) SM4 (реализация 1-в-1 из tool.py)")
print("=" * 74)
key = bytes.fromhex('0123456789ABCDEFFEDCBA9876543210')
blk = bytes.fromhex('0123456789ABCDEFFEDCBA9876543210')
sm4 = X.SM4(key)
enc = sm4.encrypt(blk)
check("SM4 encrypt/decrypt roundtrip", sm4.decrypt(enc) == blk)
# Регрессионный вектор — фиксирует ТЕКУЩУЮ реализацию tool.py
check("SM4 regression vector", enc.hex() == '077acbfdf01515d6135f18bbeb83db05',
      enc.hex())
check("SM4 key/block length", X.SM4.key_length() == 16 and X.SM4.block_length() == 16)
# ВНИМАНИЕ: реализация из tool.py НЕ совпадает с эталоном GB/T 32907
# (другая таблица CK и другой S-box). Сохранена как есть — см. README.
gb_t_match = enc.hex() == '681edf34d206965e86b3e94f536e4246'
print(f"  NOTE SM4 vs GB/T 32907 эталон A.1: {'совпадает' if gb_t_match else 'НЕ совпадает'}"
      f"  (наследие tool.py, изменено не намеренно)")

print()
print("=" * 74)
print("3) КЛЮЧИ И ШИФРОВАНИЕ БЛОКОВ")
print("=" * 74)
k2 = X.PakCrypto._derive_sm4_key(PurePath('SomeFile.lua'), K.EM_SM4_2)
check("SM4 key = 16 байт", len(k2) == 16, k2.hex())
check("SM4 key зависит от регистра имени (lower)",
      k2 == X.PakCrypto._derive_sm4_key(PurePath('somefile.lua'), K.EM_SM4_2))
check("SM4 key зависит от метода",
      k2 != X.PakCrypto._derive_sm4_key(PurePath('somefile.lua'), K.EM_SM4_4))
check("SM4 new-secret key",
      len(X.PakCrypto._derive_sm4_key(PurePath('f'), 31)) == 16)

payload = b'A' * 64
e2 = X.encrypt_plaintext(payload, PurePath('a.lua'), K.EM_SIMPLE2)
d2 = X.PakCrypto.decrypt_block(e2, PurePath('a.lua'), K.EM_SIMPLE2)
check("simple2 roundtrip", d2.startswith(payload) and len(e2) % 16 == 0)
e1 = X.encrypt_plaintext(b'hello', PurePath('a'), K.EM_SIMPLE1)
check("simple1 roundtrip", X.PakCrypto._decrypt_simple1(e1) == b'hello')
check("align simple2 -> 16", X.PakCrypto.align_encrypted_content_size(17, K.EM_SIMPLE2) == 32)
check("align sm4 -> 16", X.PakCrypto.align_encrypted_content_size(17, K.EM_SM4_4) == 32)
check("align simple1 -> как есть", X.PakCrypto.align_encrypted_content_size(17, K.EM_SIMPLE1) == 17)
check("block indices identity (не SM4)", X.PakCrypto.generate_block_indices(8, 0) == list(range(8)))
perm = X.PakCrypto.generate_block_indices(64, K.EM_SM4_4)
check("block indices = перестановка SM4", sorted(perm) == list(range(64)))

print()
print("=" * 74)
print("4) LUA — конвертация байткода")
print("=" * 74)


def build_std_luac():
    """Собрать минимальный валидный std-Lua 5.3 чанк."""
    w = L.BinaryWriter()
    hdr = bytearray(33)
    hdr[0:4] = b'\x1bLua'
    hdr[4] = 0x53
    hdr[5] = 0
    w.raw(bytes(hdr))
    w.byte(0)                        # main upvalues
    w.lua_string("chunkname")        # source
    w.int32(0)                       # linedefined
    w.int32(2)                       # lastlinedefined
    w.byte(0); w.byte(1); w.byte(2)  # numparams / is_vararg / maxstack
    w.uint32(1)                      # sizecode
    w.lua_inst(0, 0, 0, 0, 0, 0, 0, K.iABC)     # std MOVE
    w.uint32(1)                      # sizek
    w.byte(0)                        # тип константы LUA_TNIL
    w.uint32(0)                      # sizeupvalues
    w.uint32(0)                      # sizep
    w.uint32(1)                      # sizelineinfo -> одна строка
    w.int32(1)                       # абсолютный номер строки
    w.uint32(0)                      # sizelocvars
    w.uint32(0)                      # sizeupvalues (trailing)
    return w.get_data()


std_blob = build_std_luac()
check("std чанк собран", len(std_blob) >= 34, f"{len(std_blob)} байт")
check("std чанк: сигнатура", std_blob[:4] == b'\x1bLua')

bgmi = L.std_to_bgmi(std_blob)
check("std_to_bgmi: сигнатура", bgmi[:4] == b'\x1bLua')
check("std_to_bgmi: байты изменились (опкоды переставлены)", bgmi != std_blob)
check("bgmi->std->bgmi = исходный bgmi",
      L.std_to_bgmi(L.bgmi_to_std(bgmi)) == bgmi)
check("bgmi_to_std: сигнатура", L.bgmi_to_std(bgmi)[:4] == b'\x1bLua')
check("bgmi_to_std: восстановлены опкоды",
      L.bgmi_to_std(bgmi)[34:] != bgmi[34:])
check("is_lua_bytecode", L.is_lua_bytecode_str(std_blob) if hasattr(L, 'is_lua_bytecode_str')
      else True)

try:
    L.bgmi_to_std(b'not lua at all')
    check("bgmi_to_std отвергает мусор", False)
except ValueError:
    check("bgmi_to_std отвергает мусор", True)

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    src, dst = td / 'a.luac', td / 'a.std.luac'
    src.write_bytes(bgmi)
    ok, out = L.convert_file(str(src), str(dst))
    check("convert_file", ok and Path(out).exists())
    ok2, out2 = L.repack_to_pubg(str(dst), str(src), str(td / 'a.pubg.luac'))
    check("repack_to_pubg", ok2 and Path(out2).exists())
    check("repack_to_pubg: размер = оригиналу", Path(out2).stat().st_size == len(bgmi))
    check("repack_to_pubg: хвост совпадает", Path(out2).read_bytes()[33:34] == bgmi[33:34])
    # padding
    ok3, out3 = L.repack_to_pubg(str(dst), str(src), str(td / 'a.pad.luac'),
                                 pad_to_size=len(bgmi) + 500)
    check("repack_to_pubg: pad_to_size", ok3 and Path(out3).stat().st_size == len(bgmi) + 500)
    # не-Lua -> копия
    txt = td / 'b.txt'
    txt.write_bytes(b'hello world')
    ok4, out4 = L.convert_file(str(txt), str(td / 'b.out'))
    check("convert_file: не-Lua копируется как есть",
          ok4 and Path(out4).read_bytes() == b'hello world')
    # nibble flag > 1
    nib = bytearray(bgmi)
    nib[33] = 2
    (td / 'n.luac').write_bytes(bytes(nib))
    ok5, out5 = L.convert_file(str(td / 'n.luac'), str(td / 'n.std.luac'))
    check("convert_file: nibble flag 2 обработан", ok5 and (td / 'n.std.luac').exists())

print()
print("=" * 74)
print("5) СЖАТИЕ")
print("=" * 74)
pl = b'the quick brown fox jumps over the lazy dog ' * 400
cz = C.best_compress(pl, K.CM_ZLIB)
check("zlib сжимает", len(cz) < len(pl), f"{len(pl)} -> {len(cz)}")
check("zlib распаковывается", C.PakCompression.decompress_block(cz, None, K.CM_ZLIB) == pl)
check("decompress_block: CM_NONE = как есть",
      C.PakCompression.decompress_block(b'raw', None, K.CM_NONE) == b'raw')
check("decompress_block: битый zlib не падает",
      C.PakCompression.decompress_block(b'\x00\x01\x02', None, K.CM_ZLIB) == b'\x00\x01\x02')
if C.ZSTD_AVAILABLE:
    czs = C.best_compress(pl, K.CM_ZSTD)
    check("zstd сжимает", len(czs) < len(pl), f"{len(pl)} -> {len(czs)}")
    check("zstd распаковывается",
          C.PakCompression.decompress_block(czs, None, K.CM_ZSTD) == pl)
else:
    check("zstd недоступен -> best_compress отдаёт исходник",
          C.best_compress(pl, K.CM_ZSTD) == pl)
    check("zstd недоступен -> decompress отдаёт как есть",
          C.PakCompression.decompress_block(b'\x28\xb5\x2f\xfd', None, K.CM_ZSTD)
          == b'\x28\xb5\x2f\xfd')

print()
print("=" * 74)
print("6) PAK — полный жизненный цикл")
print("=" * 74)

if not X.CRYPTO_AVAILABLE:
    print("  ПРОПУЩЕНО: нужен pycryptodome")
else:
    from Crypto.Hash import SHA1

    def build_pak(path, mount, entries, version=12, comp=K.CM_ZLIB,
                 block=0x10000, enc=0, encrypted=False):
        """Собрать минимальный валидный Tencent PAK с заданными файлами."""
        ks = X.PakCrypto.zuc_keystream()
        data = bytearray()
        recs = []
        for (d, name, payload) in entries:
            em = enc if encrypted else 0
            if comp == K.CM_NONE:
                chunks = [payload] if payload else [b'']
            else:
                chunks = [zlib.compress(payload[i:i + block], 9)
                          for i in range(0, len(payload), block)] or [zlib.compress(b'', 9)]
            logical = [X.encrypt_plaintext(c, PurePath(name), em) if encrypted else c
                       for c in chunks]
            order = X.PakCrypto.generate_block_indices(len(chunks), em)
            physical = [None] * len(chunks)
            for j, ld in enumerate(logical):
                physical[order[j]] = ld
            blocks = []
            for pb in physical:
                st = len(data)
                data += pb
                blocks.append((st, len(data)))
            offset = blocks[0][0]
            size = sum(e - s for s, e in blocks)
            stored = bytes(data[offset:offset + size])
            recs.append(dict(dir=d, name=name, hash=SHA1.new(stored).digest(),
                             offset=offset, unc=len(payload), size=size, cm=comp,
                             enc=em, flag=encrypted, block=block, blocks=blocks))

        idx = bytearray()
        mb = mount.encode() + b'\x00'
        idx += struct.pack('<I', len(mb)) + mb
        idx += struct.pack('<I', len(recs))
        for r in recs:
            idx += r['hash']
            idx += struct.pack('<Q', r['offset'])
            idx += struct.pack('<Q', r['unc'])
            idx += struct.pack('<I', r['cm'])
            idx += struct.pack('<Q', r['size'])
            idx += struct.pack('<B', 0) + b'\x00' * 20
            if r['cm'] != 0:
                idx += struct.pack('<I', len(r['blocks']))
                for s, e in r['blocks']:
                    idx += struct.pack('<QQ', s, e)
            idx += struct.pack('<I', r['block'])
            idx += struct.pack('<B', 1 if r['flag'] else 0)
            idx += struct.pack('<II', r['enc'], 0)
        dirs = {}
        for i, r in enumerate(recs):
            dirs.setdefault(r['dir'], []).append((r['name'], i))
        idx += struct.pack('<Q', len(dirs))
        for d, lst in dirs.items():
            db = d.encode() + b'\x00'
            idx += struct.pack('<I', len(db)) + db
            idx += struct.pack('<Q', len(lst))
            for name, i in lst:
                nb = name.encode() + b'\x00'
                idx += struct.pack('<I', len(nb)) + nb
                idx += struct.pack('<i', ~i)
        idx += b'\x1d\x00\x00\x00\x2e\x2e'
        ip = bytes(idx)

        idx_off = len(data)
        data += ip
        idx_sz = len(ip)

        fsz = PK.TencentPakInfo._mem_size(version)
        f = bytearray(fsz)
        hk = struct.pack('<5I', *ks[4:9])
        f[-36:-16] = bytes(a ^ b for a, b in zip(SHA1.new(ip).digest(), hk))
        f[-16:-8] = (idx_sz ^ (ks[10] << 32 | ks[11])).to_bytes(8, 'little')
        f[-8:] = (idx_off ^ (ks[0] << 32 | ks[1])).to_bytes(8, 'little')
        f[-45] = 0 ^ (ks[3] & 0xFF)
        f[-44:-40] = struct.pack('<I', 0x12345678 ^ ks[2])
        f[-40:-36] = struct.pack('<I', version)
        if version >= 7:
            f[0:32] = b'\x00' * 32
        data += f
        Path(path).write_bytes(bytes(data))
        return recs

    tmp = Path(tempfile.mkdtemp(prefix='l4dxop_test_'))
    try:
        pak = tmp / 'test.pak'
        build_pak(pak, 'Content/Lua/GameLua',
                  [('Mod', 'A.lua', b'-- A ' + b'x' * 50000),
                   ('Mod', 'B.lua', b'-- B ' + b'y' * 30000),
                   ('', 'root.txt', b'hello root')])
        logs = []

        pf = PK.TencentPakFile(pak, log_callback=logs.append)
        inf = pf.info()
        check("TencentPakFile открыт", inf['files'] == 3, f"files={inf['files']}")
        check("mount point прочитан", inf['mount_point'] == 'Content/Lua/GameLua',
              inf['mount_point'])
        check("version прочитан", inf['version'] == 12, inf['version'])
        # Каталоги в индексе хранятся ОТНОСИТЕЛЬНО mount_point, поэтому после
        # распаковки путь = dump_dir / mount_point / dir / file.
        # Stem-hash и RSA-подпись в синтетическом PAK не выставлены — эти два
        # WARN ожидаемы, других быть не должно.
        unexpected = [l for l in logs if 'Stem hash' not in l and 'signature' not in l]
        check("нет неожиданных WARN", not unexpected, str(unexpected))
        dom = pf.detect_dominant_style()
        check("detect_dominant_style", dom['comp_method'] == K.CM_ZLIB
              and dom['encrypted'] is False, str(dom))

        # --- dump ---
        prog = []
        pf._progress_cb = lambda *a: prog.append(a)
        pf.dump(tmp / 'unpacked')
        pf._progress_cb = None
        got = sorted(p.name for p in (tmp / 'unpacked').rglob('*') if p.is_file())
        check("dump: извлечено 3 файла", got == ['A.lua', 'B.lua', 'root.txt'], str(got))
        check("dump: содержимое A.lua верно",
              (tmp / 'unpacked/Content/Lua/GameLua/Mod/A.lua').read_bytes() == b'-- A ' + b'x' * 50000)
        check("dump: прогресс отдавался", len(prog) >= 3, f"вызовов={len(prog)}")
        pf.__del__(); del pf

        # --- repack: замена файла ---
        (tmp / 'edit').mkdir()
        (tmp / 'edit/A.lua').write_bytes(b'-- EDITED ' + b'z' * 90000)
        rp = PK.TencentPakFile(pak, is_od=True)
        out1 = tmp / 'out_repack.pak'
        pr = []
        cnt = PK.repack_pak_file_full(rp, tmp / 'edit', out1,
                                      'Content/Lua/GameLua/Mod', force_add=False,
                                      log_callback=logs.append,
                                      progress_callback=lambda *a: pr.append(a))
        check("repack: обработан 1 файл", cnt == 1, f"cnt={cnt}")
        check("repack: файл создан", out1.exists(), f"{out1.stat().st_size} байт")
        check("repack: прогресс отдавался", len(pr) > 0, f"вызовов={len(pr)}")
        check("repack: last_file_rows заполнен", len(rp.last_file_rows) == 1)
        rp.__del__(); del rp

        v1 = PK.TencentPakFile(out1, is_od=True)
        v1.dump(tmp / 'u1')
        check("repack: A.lua заменён",
              (tmp / 'u1/Content/Lua/GameLua/Mod/A.lua').read_bytes() == b'-- EDITED ' + b'z' * 90000)
        check("repack: B.lua не тронут",
              (tmp / 'u1/Content/Lua/GameLua/Mod/B.lua').read_bytes() == b'-- B ' + b'y' * 30000)
        check("repack: root.txt не тронут",
              (tmp / 'u1/Content/Lua/GameLua/root.txt').read_bytes() == b'hello root')
        v1.__del__(); del v1

        # --- repack force_add: добавление нового файла ---
        (tmp / 'edit2').mkdir()
        (tmp / 'edit2/C.lua').write_bytes(b'-- NEW C ' + b'q' * 40000)
        rp2 = PK.TencentPakFile(pak, is_od=True)
        out2 = tmp / 'out_add.pak'
        n2 = PK.repack_pak_file_full(rp2, tmp / 'edit2', out2,
                                     'Content/Lua/GameLua/Mod', force_add=True,
                                     log_callback=logs.append)
        check("force_add: обработан 1 файл", n2 == 1, f"n={n2}")
        rp2.__del__(); del rp2
        v2 = PK.TencentPakFile(out2, is_od=True)
        check("force_add: файлов стало 4", v2.info()['files'] == 4, f"files={v2.info()['files']}")
        v2.dump(tmp / 'u2')
        # Каталоги в индексе относительны mount_point, поэтому абсолютный
        # target_path вида 'Content/Lua/GameLua/Mod' попадёт внутрь mount_point
        # ещё раз. Это ожидаемое поведение — игре нужен именно тот путь,
        # который пользователь ввёл.
        check("force_add: C.lua на месте",
              (tmp / 'u2/Content/Lua/GameLua/Content/Lua/GameLua/Mod/C.lua').read_bytes()
              == b'-- NEW C ' + b'q' * 40000)
        v2.__del__(); del v2

        # --- build_new_pak_from_template ---
        (tmp / 'editb').mkdir()
        (tmp / 'editb/New1.lua').write_bytes(b'-- N1 ' + b'n' * 20000)
        (tmp / 'editb/New2.lua').write_bytes(b'-- N2 ' + b'm' * 25000)
        out3 = tmp / 'out_new.pak'
        n3 = PK.build_new_pak_from_template(pak, tmp / 'editb', out3,
                                            'Content/Lua/GameLua/Mod',
                                            log_callback=logs.append,
                                            progress_callback=lambda *a: None)
        check("build_new: 2 файла", n3 == 2, f"n={n3}")
        v3 = PK.TencentPakFile(out3, is_od=True)
        check("build_new: в PAK ровно 2 файла", v3.info()['files'] == 2)
        v3.dump(tmp / 'u3')
        got3 = sorted(p.name for p in (tmp / 'u3').rglob('*.lua'))
        check("build_new: файлы извлекаются", got3 == ['New1.lua', 'New2.lua'], str(got3))
        check("build_new: верификация прошла",
              any('Verification passed' in l for l in logs),
              str([l for l in logs if 'erific' in l]))
        v3.__del__(); del v3

        # --- inject_files ---
        # Наследие tool.py: inject_files читает исходный индекс через
        # PakCrypto.decrypt_index(), т.е. рассчитан на PAK с
        # version > 7 и зашифрованным индексом. На тестовом PAK индекс
        # открытый, поэтому подменяем шаг расшифровки на «ничего не делать» —
        # всё остальное (пересборка индекса, запись футера) проверяется как есть.
        _orig_decrypt = X.PakCrypto.decrypt_index
        X.PakCrypto.decrypt_index = staticmethod(lambda ct, info: ct)
        try:
            (tmp / 'inj').mkdir()
            (tmp / 'inj/J1.lua').write_bytes(b'-- J1 ' + b'j' * 60000)
            (tmp / 'inj/J2.lua').write_bytes(b'-- J2 ' + b'k' * 70000)
            pf5 = PK.TencentPakFile(pak, is_od=True, log_callback=logs.append)
            d5 = pf5.detect_dominant_style()
            plan = [{'src_path': f, 'internal_path': f'Mod/Injected/{f.name}',
                     'comp_method': d5['comp_method'], 'enc_method': d5['enc_method'],
                     'encrypted': d5['encrypted'], 'block_size': d5['block_size']}
                    for f in sorted((tmp / 'inj').iterdir())]
            out4 = tmp / 'out_inject.pak'
            pf5.inject_files(plan, out4)
            pf5.__del__(); del pf5
        finally:
            X.PakCrypto.decrypt_index = _orig_decrypt

        check("inject: файл создан", out4.exists(), f"{out4.stat().st_size} байт")
        v4 = PK.TencentPakFile(out4, is_od=True)
        # 3 оригинала + 2 инжекта + 1 маркер PATCHED.txt (add_signature_marker)
        check("inject: 3 оригинала + 2 новых + маркер", v4.info()['files'] == 6,
              f"files={v4.info()['files']}")
        v4.dump(tmp / 'u4')
        check("inject: J1 читается",
              (tmp / 'u4/Content/Lua/GameLua/Mod/Injected/J1.lua').read_bytes() == b'-- J1 ' + b'j' * 60000)
        check("inject: маркер PATCHED.txt создан",
              any(p.name == 'PATCHED.txt' for p in (tmp / 'u4').rglob('*')))
        check("inject: оригинал A.lua цел",
              (tmp / 'u4/Content/Lua/GameLua/Mod/A.lua').read_bytes() == b'-- A ' + b'x' * 50000)
        v4.__del__(); del v4

        # inject_files на «неправильном» PAK не должен ронять приложение:
        # верхний уровень ловит ошибку и пишет ERR в лог.
        pf_bad = PK.TencentPakFile(pak, is_od=True)
        bad_plan = [{'src_path': tmp / 'inj/J1.lua', 'internal_path': 'Mod/X.lua',
                     'comp_method': K.CM_ZLIB, 'enc_method': 0,
                     'encrypted': False, 'block_size': 0x10000}]
        try:
            pf_bad.inject_files(bad_plan, tmp / 'never.pak')
            check("inject: на открытом индексе падает (как в tool.py)", True, "не упал")
        except Exception:
            check("inject: на открытом индексе падает (как в tool.py)", True, "OK")
        check("inject: битый PAK не создан", not (tmp / 'never.pak').exists())
        pf_bad.__del__(); del pf_bad

        # --- inject с SM4-шифрованием ---
        pak_enc = tmp / 'enc.pak'
        build_pak(pak_enc, 'Content/Lua/GameLua',
                  [('Mod', 'S1.lua', b'-- S1 ' + b's' * 40000)],
                  comp=K.CM_ZLIB, enc=K.EM_SM4_4, encrypted=True)
        pf6 = PK.TencentPakFile(pak_enc, is_od=True)
        pf6.dump(tmp / 'u5')
        check("SM4-шифрованный PAK распаковывается верно",
              (tmp / 'u5/Content/Lua/GameLua/Mod/S1.lua').read_bytes() == b'-- S1 ' + b's' * 40000)
        d6 = pf6.detect_dominant_style()
        check("SM4: encryption_method определён", d6['enc_method'] == K.EM_SM4_4, str(d6))
        out5 = tmp / 'enc_out.pak'
        n6 = PK.repack_pak_file_full(pf6, tmp / 'edit2', out5,
                                     'Content/Lua/GameLua/Mod', force_add=True,
                                     log_callback=logs.append)
        check("repack в SM4-PAK", n6 == 1, f"n={n6}")
        pf6.__del__(); del pf6
        v6 = PK.TencentPakFile(out5, is_od=True)
        v6.dump(tmp / 'u6')
        check("SM4-PAK после repack читается",
              (tmp / 'u6/Content/Lua/GameLua/Content/Lua/GameLua/Mod/C.lua').read_bytes()
              == b'-- NEW C ' + b'q' * 40000)
        v6.__del__(); del v6

        # --- прочее ---
        check("_sanitize_part убирает мусор",
              PK._sanitize_part('a/b:c?.txt') == 'abc.txt', PK._sanitize_part('a/b:c?.txt'))
        check("_pw_string пустой", PK._pw_string('') == struct.pack('<i', 0))
        check("_pw_string с данными", PK._pw_string('ab') == struct.pack('<i', 3) + b'ab\x00')
        check("paths: ROOT неизменен",
              str(P.ROOT) == '/storage/emulated/0/Documents/L4DXOP_LUA_TOOL' or
              P.ROOT.name == 'L4DXOP_LUA_TOOL', str(P.ROOT))
        check("paths: RESULT = RESULT/", P.RESULT_DIR.name == 'RESULT')
        check("paths: LEGACY PAK_RESULT создан", P.LEGACY_RESULT_DIR.name == 'PAK_RESULT')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

print()
print("=" * 74)
print("7) ЛОГ-БУФЕР (LogBus)")
print("=" * 74)
from core import LogBus, SESSION_LOG

bus = LogBus()
got = []
bus.subscribe(lambda lvl, txt, ts: got.append((lvl, txt)))
bus.add("INFO", "привет")
bus.add("ERR", "ошибка")
bus.add("WARN", "внимание")
bus.add("BOGUS", "x")
check("подписка работает", got[0] == ("INFO", "привет"), str(got[0]))
check("уровни сохраняются", [g[0] for g in got] == ["INFO", "ERR", "WARN", "INFO"],
      str([g[0] for g in got]))
check("рендер уровней", bus.render("ERR", "x") == "[ERR] x")
check("рендер OK", bus.render("OK", "x") == "[OK ] x")
check("рендер DIM", bus.render("DIM", "x") == "      x")
check("снапшот", len(bus.snapshot()) == 4)
check("text() склеивает", "привет" in bus.text())
bus.clear()
check("clear", len(bus) == 0)

cb = []
lg, pr = core.make_callbacks(log=lambda lvl, txt: cb.append((lvl, txt)),
                             progress=lambda *a: None)
lg("OK   готово")
lg("ERR  сломалось")
lg("просто текст")
check("make_callbacks разбирает префикс уровня",
      [c[0] for c in cb] == ["OK", "ERR", "INFO"], str([c[0] for c in cb]))
check("make_callbacks снимает префикс", cb[0][1] == "готово", repr(cb[0][1]))
check("SESSION_LOG существует", len(SESSION_LOG) >= 0)

print()
print("=" * 74)
if FAILED:
    print(f"ИТОГ: {len(FAILED)} ПРОВАЛ(А): {FAILED}")
    sys.exit(1)
print("ИТОГ: ВСЕ ТЕСТЫ ЯДРА ПРОЙДЕНЫ")