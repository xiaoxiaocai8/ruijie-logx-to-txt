#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
锐捷 logx 解密工具 GUI【可配置并行批量版】
可UI设置最大并行任务数，支持多选批量logx
"""
import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import concurrent.futures
import queue
import threading

def bitrev(b: int) -> int:
    """单字节bit位反转，锐捷logx加密算法"""
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    return b


def decrypt_logx_file(file_path: str) -> str:
    with open(file_path, "rb") as f:
        raw_data = f.read()

    if raw_data.startswith(b"JR"):
        reversed_bytes = bytes(bitrev(x) for x in raw_data)
        offset = -1
        for marker in (b"_pluginId_", b"pluginId"):
            pos = reversed_bytes.find(marker)
            if pos != -1:
                offset = pos
                break
        if offset == -1:
            raise RuntimeError("logx损坏：存在JR头部，找不到pluginId标记")
        plain_bytes = reversed_bytes[offset:]
    else:
        plain_bytes = raw_data

    if plain_bytes.startswith(b"\xef\xbb\xbf"):
        plain_bytes = plain_bytes[3:]
    text = plain_bytes.decode("utf-8", errors="replace")
    return text


def worker_task(src_file: str, out_dir: str):
    """单个解密任务，给线程池调用"""
    try:
        plain_text = decrypt_logx_file(src_file)
        base_name = os.path.splitext(os.path.basename(src_file))[0]
        out_path = os.path.join(out_dir, f"{base_name}_decrypted.txt")
        with open(out_path, "w", encoding="utf-8") as fw:
            fw.write(plain_text)
        return {"ok": True, "src": src_file, "out": out_path, "err": None}
    except Exception as e:
        return {"ok": False, "src": src_file, "out": None, "err": str(e)}


class LogxDecryptGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("锐捷 logx 解密工具｜可配置并行批量版")
        self.root.geometry("760x500")
        self.root.resizable(True, True)

        self.input_files: list[str] = []
        self.output_dir_var = tk.StringVar()
        self.worker_count_var = tk.StringVar(value="10")  # 默认并发10
        self.msg_queue = queue.Queue()
        self.running = False

        main_frame = ttk.Frame(root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 源文件选择
        ttk.Label(main_frame, text="源logx文件(支持多选)：").grid(row=0, column=0, sticky="w")
        self.file_entry = ttk.Entry(main_frame)
        self.file_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="多选文件", command=self.select_input_files).grid(row=0, column=2)

        # 输出目录
        ttk.Label(main_frame, text="输出保存目录：").grid(row=1, column=0, sticky="w", pady=10)
        ttk.Entry(main_frame, textvariable=self.output_dir_var).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="选择目录", command=self.select_output_dir).grid(row=1, column=2)

        # 并发任务数配置
        ttk.Label(main_frame, text="最大并行任务数(1‑20)：").grid(row=2, column=0, sticky="w", pady=6)
        spin = ttk.Spinbox(main_frame, from_=1, to=20, textvariable=self.worker_count_var, width=8)
        spin.grid(row=2, column=1, sticky="w", padx=5)
        ttk.Label(main_frame, text="SSD建议8‑12；机械硬盘建议2‑4").grid(row=2, column=1, padx=80, sticky="w")

        main_frame.columnconfigure(1, weight=1)

        # 状态与运行按钮
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(main_frame, textvariable=self.status_var).grid(row=3, column=0, sticky="w", pady=4)
        self.run_btn = ttk.Button(main_frame, text="开始批量解密", command=self.start_batch, state="normal")
        self.run_btn.grid(row=3, column=1, columnspan=2, pady=8)

        # 日志框
        ttk.Label(main_frame, text="运行日志：").grid(row=4, column=0, sticky="w")
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=5, column=0, columnspan=3, sticky="nsew")
        main_frame.rowconfigure(5, weight=1)

        self.log_text = tk.Text(log_frame)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.poll_msg()

    def log(self, msg: str):
        self.msg_queue.put(msg)

    def poll_msg(self):
        """从队列回写日志到UI，tkinter线程安全"""
        while not self.msg_queue.empty():
            m = self.msg_queue.get()
            self.log_text.insert(tk.END, f"{m}\n")
            self.log_text.see(tk.END)
        self.root.after(80, self.poll_msg)

    def select_input_files(self):
        paths = filedialog.askopenfilenames(
            title="选择一个或多个 .logx 文件",
            filetypes=[("logx巡检文件", "*.logx"), ("所有文件", "*.*")]
        )
        if not paths:
            return
        self.input_files = list(paths)
        self.file_entry.delete(0, tk.END)
        self.file_entry.insert(0, f"已选中 {len(self.input_files)} 个文件")
        src_dir = os.path.dirname(paths[0])
        self.output_dir_var.set(src_dir)
        self.log(f"📂选中 {len(self.input_files)} 个待处理文件")

    def select_output_dir(self):
        d = filedialog.askdirectory(title="选择输出文件夹")
        if d:
            self.output_dir_var.set(d)

    def batch_thread(self, file_list: list[str], out_dir: str, max_workers: int):
        """后台线程执行线程池，不阻塞GUI"""
        total = len(file_list)
        ok_cnt = 0
        fail_cnt = 0
        self.log(f"🚀开始批量处理，最大并行 {max_workers}，总共 {total} 个文件")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_map = {executor.submit(worker_task, f, out_dir): f for f in file_list}
            for fut in concurrent.futures.as_completed(fut_map):
                res = fut.result()
                src = res["src"]
                if res["ok"]:
                    ok_cnt += 1
                    self.log(f"✅成功 {os.path.basename(src)} → {os.path.basename(res['out'])}")
                else:
                    fail_cnt += 1
                    self.log(f"❌失败 {os.path.basename(src)} : {res['err']}")
        self.log(f"\n🏁全部完成：成功 {ok_cnt} / 失败 {fail_cnt} / 总计 {total}")
        self.status_var.set(f"完成｜成功:{ok_cnt} 失败:{fail_cnt}")
        self.run_btn.config(state="normal")
        self.running = False

    def start_batch(self):
        if self.running:
            messagebox.showwarning("提示", "任务正在运行中，请等待完成")
            return
        file_list = self.input_files
        out_dir = self.output_dir_var.get().strip()

        # 校验并发数
        try:
            max_workers = int(self.worker_count_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "最大并行任务数必须输入数字")
            return
        if not (1 <= max_workers <= 20):
            messagebox.showerror("参数错误", "并行任务数范围必须 1‑20")
            return

        if len(file_list) == 0:
            messagebox.showerror("错误", "请先选择至少一个logx文件")
            return
        if not os.path.isdir(out_dir):
            messagebox.showerror("错误", "输出目录不存在")
            return

        self.running = True
        self.run_btn.config(state="disabled")
        self.status_var.set("运行中...")
        t = threading.Thread(target=self.batch_thread, args=(file_list, out_dir, max_workers), daemon=True)
        t.start()


def main():
    root = tk.Tk()
    app = LogxDecryptGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
