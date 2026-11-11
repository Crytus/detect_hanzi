#!/usr/bin/env python3
"""日本語テキストに混入した中国語の漢字（主に簡体字）を検出するツール。

判定方法:
    CJK統合漢字のうち、日本の文字コードで表現できない文字を「中国語の漢字」とみなす。
      - cp932   : Shift_JIS(Windows) = JIS X 0208 + NEC/IBM拡張（既定・厳しめ）
      - jis2004 : JIS X 0213（第3・第4水準まで含む。日本語の稀な字の誤検出が減るが、
                  「么」など一部の簡体字を見逃す）
    さらに、日本の文字コードに含まれるが日本語ではまず使われない簡体字
    （例: 个）を追加リストで検出する。

使い方:
    python detect_hanzi.py ファイルまたはフォルダ [...]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

# JISに含まれるが日本語ではほぼ使われない簡体字（追加で検出する）
#   个(個) 气(気) 儿(児) 无(無) 坏(壊) 听(聴) 苹(蘋)
#   ※ 学・会・来 などは日本の新字体と同形のため対象外（原理的に区別不可）
DEFAULT_EXTRA_CHARS = "个气儿无坏听苹"

# 判定レベルと使用するエンコーディングの対応
LEVEL_ENCODINGS = {
    "cp932": "cp932",
    "jis2004": "shift_jis_2004",
}

# 自動判定で試す文字コード（先に成功したものを採用）
AUTO_ENCODINGS = ("utf-8-sig", "cp932", "euc_jp", "utf-16")

# フォルダ指定時に対象とする既定の拡張子
DEFAULT_EXTENSIONS = (".txt", ".md", ".csv", ".json", ".html", ".htm", ".xml", ".srt", ".vtt")

# CJK統合漢字の範囲（拡張A〜、互換漢字を含む）
CJK_RANGES = (
    (0x3400, 0x4DBF),    # 拡張A
    (0x4E00, 0x9FFF),    # 基本
    (0xF900, 0xFAFF),    # 互換漢字
    (0x20000, 0x2A6DF),  # 拡張B
    (0x2A700, 0x2EBEF),  # 拡張C〜F
    (0x2F800, 0x2FA1F),  # 互換漢字補助
    (0x30000, 0x323AF),  # 拡張G〜H
)


@dataclass(frozen=True)
class Hit:
    """検出結果1件分。"""
    path: str
    line: int      # 1始まりの行番号
    column: int    # 1始まりの桁番号（文字単位）
    char: str
    line_text: str


def is_cjk_ideograph(ch: str) -> bool:
    """CJK統合漢字かどうかを判定する。"""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in CJK_RANGES)


class Detector:
    """1文字ごとに中国語の漢字かどうかを判定する（結果はキャッシュ）。"""

    def __init__(self, level: str = "cp932", extra_chars: str = DEFAULT_EXTRA_CHARS,
                 allow_chars: str = ""):
        self.encoding = LEVEL_ENCODINGS[level]
        self.extra = set(extra_chars)
        self.allow = set(allow_chars)
        self._cache: dict[str, bool] = {}

    def is_chinese(self, ch: str) -> bool:
        cached = self._cache.get(ch)
        if cached is not None:
            return cached
        result = self._judge(ch)
        self._cache[ch] = result
        return result

    def _judge(self, ch: str) -> bool:
        if ch in self.allow:
            return False
        if ch in self.extra:
            return True
        if not is_cjk_ideograph(ch):
            return False
        try:
            ch.encode(self.encoding)
        except UnicodeEncodeError:
            return True  # 日本の文字コードで表せない漢字
        return False

    def scan_text(self, text: str, path: str = "<text>") -> Iterator[Hit]:
        """テキスト全体を走査して検出結果を返す。"""
        for lineno, line in enumerate(text.splitlines(), start=1):
            for col, ch in enumerate(line, start=1):
                if self.is_chinese(ch):
                    yield Hit(path, lineno, col, ch, line)


def read_text(path: Path, encoding: str = "auto") -> str:
    """ファイルを読み込む。auto の場合は複数の文字コードを順に試す。"""
    data = path.read_bytes()
    if encoding != "auto":
        return data.decode(encoding)
    # BOM付きUTF-16 を先に判定
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for enc in AUTO_ENCODINGS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("auto", data, 0, 1, "文字コードを判定できませんでした")


def iter_files(targets: Iterable[str], extensions: tuple[str, ...]) -> Iterator[Path]:
    """引数のファイル/フォルダから対象ファイルを列挙する。"""
    for t in targets:
        p = Path(t)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and (not extensions or f.suffix.lower() in extensions):
                    yield f
        elif p.is_file():
            yield p  # 明示指定されたファイルは拡張子に関係なく対象
        else:
            print(f"警告: 見つかりません: {t}", file=sys.stderr)


def format_hit(hit: Hit, show_context: bool, context_width: int = 10) -> str:
    s = f"{hit.path}:{hit.line}:{hit.column}\t'{hit.char}' (U+{ord(hit.char):04X})"
    if show_context:
        start = max(0, hit.column - 1 - context_width)
        end = hit.column + context_width
        before = hit.line_text[start:hit.column - 1]
        after = hit.line_text[hit.column:end]
        s += f"\t…{before}【{hit.char}】{after}…"
    return s


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="日本語テキストに混入した中国語の漢字（簡体字など）を検出します。")
    p.add_argument("targets", nargs="*", help="検査するファイルまたはフォルダ")
    p.add_argument("--level", choices=LEVEL_ENCODINGS.keys(), default="cp932",
                   help="判定に使う文字集合（既定: cp932）。jis2004 は第3・第4水準漢字を許容")
    p.add_argument("--encoding", default="auto",
                   help="入力ファイルの文字コード（既定: auto で自動判定）")
    p.add_argument("--ext", default=",".join(DEFAULT_EXTENSIONS),
                   help="フォルダ指定時の対象拡張子（カンマ区切り。空文字で全ファイル）")
    p.add_argument("--allow", default="", help="検出対象から除外する文字（例: --allow 们说）")
    p.add_argument("--extra", default=DEFAULT_EXTRA_CHARS,
                   help=f"追加で検出する文字（既定: {DEFAULT_EXTRA_CHARS}）。空文字で無効化")
    p.add_argument("-c", "--context", action="store_true", help="前後の文脈も表示する")
    p.add_argument("-s", "--summary-only", action="store_true",
                   help="個別の位置を出さず、文字ごとの集計のみ表示する")
    p.add_argument("-i", "--interactive", action="store_true",
                   help="対話モード。検査するファイルの入力を繰り返し受け付ける")
    return p


def parse_input_paths(line: str) -> list[str]:
    """入力された文字列からパスを取り出す。

    ドラッグ＆ドロップで入力された "..." で囲まれたパスや、
    空白区切りの複数パスに対応する。
    """
    return [m.group(1) or m.group(2) for m in re.finditer(r'"([^"]+)"|(\S+)', line)]


def scan_targets(targets: Iterable[str], args: argparse.Namespace, detector: Detector) -> int:
    """指定されたファイル/フォルダを検査して結果を表示し、終了コードを返す。"""
    extensions = tuple(e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
                       for e in args.ext.split(",") if e.strip())

    counts: dict[str, int] = {}
    total = 0
    files_with_hits = 0
    error = False

    for path in iter_files(targets, extensions):
        try:
            text = read_text(path, args.encoding)
        except (UnicodeDecodeError, LookupError, OSError) as e:
            print(f"エラー: {path}: {e}", file=sys.stderr)
            error = True
            continue
        found = False
        for hit in detector.scan_text(text, str(path)):
            found = True
            total += 1
            counts[hit.char] = counts.get(hit.char, 0) + 1
            if not args.summary_only:
                print(format_hit(hit, args.context))
        files_with_hits += found

    # 集計表示
    print(f"--- 検出数: {total}文字（種類: {len(counts)}、ファイル: {files_with_hits}）")
    if counts:
        ranking = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        print("    " + " ".join(f"{ch}×{n}" for ch, n in ranking))

    # 終了コード: 0=検出なし, 1=検出あり, 2=読み込みエラー
    if error:
        return 2
    return 1 if total else 0


def interactive_loop(args: argparse.Namespace, detector: Detector) -> int:
    """対話モード: 空行（または入力終了）までパスの入力と検査を繰り返す。"""
    while True:
        print()
        print("調べたいファイルまたはフォルダを、この画面にドラッグ＆ドロップして Enter キーを押してください。")
        print("（何も入力せずに Enter キーを押すと終了します）")
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        paths = parse_input_paths(line)
        if not paths:
            return 0
        print()
        scan_targets(paths, args, detector)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Windowsコンソールでも文字化けしないよう標準出力をUTF-8に
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    detector = Detector(args.level, args.extra, args.allow)

    if args.interactive:
        # 対話モード: 引数があれば先に検査してから入力待ちへ移る。終了コードは常に0
        if args.targets:
            scan_targets(args.targets, args, detector)
        return interactive_loop(args, detector)
    if args.targets:
        return scan_targets(args.targets, args, detector)
    parser.error("検査するファイルまたはフォルダを指定してください（または -i で対話モード）")
    return 2  # parser.error は終了するため到達しない


if __name__ == "__main__":
    sys.exit(main())
