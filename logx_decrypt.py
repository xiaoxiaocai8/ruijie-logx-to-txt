#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
锐捷 logx 文件解密工具 Python3
用法1：命令行：python logx_decrypt.py test.logx
用法2：直接把 .logx 文件拖拽到此py脚本图标上
输出：同目录 xxx_decrypted.txt
"""
import sys
import os

def bitrev(b: int) -> int:
    """单字节bit位反转，锐捷logx加密算法"""
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    return b


def decrypt_logx(file_path: str) -> str:
    with open(file_path, "rb") as f:
        raw_data = f.read()

    # 判断是否是锐捷JR头logx加密文件
    if raw_data.startswith(b"JR"):
        # 全部字节做bit反转
        reversed_bytes = bytes(bitrev(x) for x in raw_data)
        # 查找真实内容起始标记
        offset = -1
        for marker in (b"_pluginId_", b"pluginId"):
            pos = reversed_bytes.find(marker)
            if pos != -1:
                offset = pos
                break
        if offset == -1:
            raise RuntimeError("logx文件损坏：存在JR头部，但是找不到pluginId标记")
        plain_bytes = reversed_bytes[offset:]
    else:
        # 普通log/txt文件直接读取
        plain_bytes = raw_data

    # 移除 UTF‑8 BOM
    if plain_bytes.startswith(b"\xef\xbb\xbf"):
        plain_bytes = plain_bytes[3:]

    text = plain_bytes.decode("utf‑8", errors="replace")
    return text


def main():
    files = sys.argv[1:]
    if not files:
        print("用法：python logx_decrypt.py  xxx.logx")
        print("或者直接把logx拖拽到本py脚本图标上")
        input("\n按回车退出...")
        return

    for fpath in files:
        if not os.path.isfile(fpath):
            print(f"[跳过] 文件不存在：{fpath}")
            continue
        try:
            plain_text = decrypt_logx(fpath)
            base_name, ext = os.path.splitext(fpath)
            out_file = f"{base_name}_decrypted.txt"
            with open(out_file, "w", encoding="utf‑8") as fw:
                fw.write(plain_text)
            print(f"✅成功：{fpath} → {out_file}")
        except Exception as e:
            print(f"❌失败 {fpath} : {str(e)}")

    if len(files) == 1:
        input("\n处理完成，按回车退出...")


if __name__ == "__main__":
    main()
