#!/usr/bin/env python3
"""
中文文章听写助手（Termux）

按中文标点（。！？；：，、……——）把文章切成一个个"半句"，
每按一次回车，打印并朗读下一个分句。

用法：
    python dictation.py 文章.txt
    python dictation.py -t "今天天气很好，我们去公园散步。"
    cat 文章.txt | python dictation.py
"""

import argparse
import re
import shutil
import subprocess
import sys

# 用来切分的标点（句读符号），连续出现会当作一个整体
SPLIT_RE = re.compile(r'([。！？；：，、…—～]+)')
# 判断片段里是否有"实际文字"（用来把孤立的右引号之类并回上一句）
HAS_TEXT_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fffA-Za-z0-9]')


def split_chunks(text):
    """按中文标点把文章切成若干"半句"，标点保留在句尾。"""
    # 去掉换行（中文文章换行一般只是排版），其余空白保留
    text = re.sub(r'[ \t]*\r?\n[ \t]*', '', text).strip()
    if not text:
        return []

    parts = SPLIT_RE.split(text)  # [正文, 标点, 正文, 标点, ...]
    raw = [parts[0]]
    for i in range(1, len(parts), 2):
        raw[-1] += parts[i]                      # 标点接到上一段末尾
        nxt = parts[i + 1] if i + 1 < len(parts) else ''
        raw.append(nxt)

    chunks = []
    for seg in raw:
        if not seg:
            continue
        if chunks and not HAS_TEXT_RE.search(seg):
            chunks[-1] += seg                    # 纯标点片段（如右引号）并入前句
        else:
            chunks.append(seg)
    return chunks


def speak(text, lang, rate, engine=None):
    """调用 termux-tts-speak 朗读（会阻塞到读完）。"""
    cmd = ['termux-tts-speak']
    if engine:
        cmd += ['-e', engine]
    if lang:
        cmd += ['-l', lang]
    if rate:
        cmd += ['-r', f'{rate:g}']
    cmd.append(text)
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print('  (找不到 termux-tts-speak，跳过朗读)', file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f'  (朗读失败，返回码 {e.returncode})', file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(
        description='中文文章听写助手：按回车逐句打印并朗读')
    ap.add_argument('file', nargs='?', help='文章文件（UTF-8），省略则从标准输入读取')
    ap.add_argument('-t', '--text', help='直接在命令行给出文章内容')
    ap.add_argument('-l', '--lang', default='zh-CN', help='TTS 语言，默认 zh-CN')
    ap.add_argument('-r', '--rate', type=float, default=0.9,
                    help='语速倍率，默认 0.9（听写建议慢一点）')
    ap.add_argument('-e', '--engine', help='指定 TTS 引擎（对应 termux-tts-speak -e）')
    ap.add_argument('--no-tts', action='store_true', help='只打印，不朗读')
    args = ap.parse_args()

    # ---------- 读取文章 ----------
    if args.text is not None:
        raw = args.text
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                raw = f.read()
        except OSError as e:
            sys.exit(f'读取文件失败：{e}')
    else:
        if sys.stdin.isatty():
            ap.print_help()
            sys.exit('\n错误：没有提供文章（用文件参数、-t 或管道传入）')
        raw = sys.stdin.read()

    chunks = split_chunks(raw)
    if not chunks:
        sys.exit('没有解析出任何内容。')

    # ---------- 准备"等待回车"的输入源 ----------
    # 如果文章是从管道读进来的，stdin 已经到 EOF，需要改用 /dev/tty
    close_it = False
    if sys.stdin.isatty():
        wait_stream = sys.stdin
    else:
        try:
            wait_stream = open('/dev/tty', 'r')
            close_it = True
        except OSError:
            sys.exit('错误：当前环境无法接收回车输入（没有可用终端）。')

    # ---------- 检查 TTS ----------
    tts_ok = shutil.which('termux-tts-speak') is not None
    do_tts = tts_ok and not args.no_tts
    if not args.no_tts and not tts_ok:
        print('提示：未找到 termux-tts-speak，本次只打印文字。')
        print('      安装：pkg install termux-api（并安装 Termux:API 应用）\n')

    total = len(chunks)
    print(f'共 {total} 句。按【回车】显示并朗读下一句，Ctrl-C 退出。\n')

    # ---------- 主循环 ----------
    try:
        for i, chunk in enumerate(chunks, 1):
            line = wait_stream.readline()   # 等待回车
            if line == '':                  # Ctrl-D / EOF
                break
            print(f'[{i}/{total}] {chunk}', flush=True)
            if do_tts:
                speak(chunk, args.lang, args.rate, args.engine)
    except KeyboardInterrupt:
        pass
    finally:
        if close_it:
            wait_stream.close()

    print('\n已退出。')


if __name__ == '__main__':
    main()
