#!/bin/bash
# ============================================================
#  detect_hanzi.command - Mac でダブルクリックして使う起動ファイル
#   ダブルクリックするとターミナルが開き、入力待ちになります。
#   調べたいファイルやフォルダをターミナルの画面にドラッグ＆ドロップして
#   Enter キーを押すと検査します。
# ============================================================

# このファイルが置かれているフォルダ（detect_hanzi.py の場所）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 使用できる Python 3 を探す（PATH 上 → python.org版 → Homebrew版 → 標準）
PY=""
for cand in \
    "$(command -v python3 2>/dev/null)" \
    /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3
do
    if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 7))' >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "Python が見つかりません。"
    echo "README.md の「はじめての方へ」を参考に Python をインストールしてください。"
    echo "https://www.python.org/downloads/"
    echo
    read -r -p "Enter キーを押すと終了します。" _
    exit 1
fi

# 文脈表示(-c)付き・対話モード(-i)で起動する
"$PY" "$SCRIPT_DIR/detect_hanzi.py" -c -i "$@"
status=$?

# 異常終了した場合はエラー内容を読めるよう止める
if [ $status -ne 0 ]; then
    echo
    echo "エラーが発生しました。"
    read -r -p "Enter キーを押すと終了します。" _
fi
exit $status
