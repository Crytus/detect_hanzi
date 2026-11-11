@echo off
chcp 65001 >nul
rem ============================================================
rem  detect_hanzi.bat - ダブルクリック／ドラッグ＆ドロップ用の起動ファイル
rem   ・ダブルクリック: 入力待ちになり、ファイルを画面にドロップして検査
rem   ・ファイル/フォルダをこのファイルにドロップ: それを検査してから入力待ち
rem ============================================================
setlocal

rem 使用できる Python を探す（py ランチャー → python → python3 の順）
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY python3 --version >nul 2>&1 && set "PY=python3"

if not defined PY (
    echo Python が見つかりません。
    echo README.md の「はじめての方へ」を参考に Python をインストールしてください。
    echo インストール時は「Add python.exe to PATH」にチェックを入れてください。
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

rem 文脈表示(-c)付き・対話モード(-i)で起動する
%PY% "%~dp0detect_hanzi.py" -c -i %*

rem 異常終了した場合はエラー内容を読めるよう画面を止める
if errorlevel 1 (
    echo.
    echo エラーが発生しました。
    pause
)
endlocal
