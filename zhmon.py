#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🖥️ 飞牛NAS 中文系统监控
CPU / 内存 / 磁盘 / 温度 / 上下行速度，每秒刷新
用法: zhmon   （按 Ctrl+C 退出）
"""

import time
import psutil
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align

console = Console()


def color_pct(pct: float) -> str:
    """按利用率返回颜色"""
    if pct >= 90:
        return "bold red"
    if pct >= 70:
        return "bold yellow"
    return "green"


def bar(pct: float, width: int = 18) -> Text:
    """画一条彩色进度条"""
    filled = round(max(0.0, min(100.0, pct)) / 100 * width)
    t = Text()
    t.append("█" * filled, style=color_pct(pct))
    t.append("░" * (width - filled), style="grey37")
    return t


def fmt_size(n: float) -> str:
    """字节数转可读单位"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024


def fmt_speed(bps: float) -> str:
    """网速格式化"""
    if bps >= 1024 * 1024:
        return f"{bps / 1024 / 1024:.2f} MB/s"
    if bps >= 1024:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps:.0f} B/s"


def temp_color(t: float) -> str:
    """温度颜色：>=75红 >=65黄"""
    if t >= 75:
        return "bold red"
    if t >= 65:
        return "bold yellow"
    return "cyan"


# 网速采样基准
_last_net = psutil.net_io_counters()
_last_t = time.time()


def build_frame() -> Panel:
    """组装一帧监控画面"""
    global _last_net, _last_t

    # ---- CPU ----
    cpu_total = psutil.cpu_percent(interval=None)
    cpu_per = psutil.cpu_percent(interval=None, percpu=True)
    cpu_txt = Text()
    cpu_txt.append("总使用率 ", style="bold white")
    cpu_txt.append(f"{cpu_total:>4.0f}%", style=color_pct(cpu_total))
    cpu_txt.append("  ")
    cpu_txt.append(bar(cpu_total))
    cpu_rows = Text()
    n = len(cpu_per)
    for i in range(0, n, 2):
        row = []
        for j in range(i, min(i + 2, n)):
            v = cpu_per[j]
            row.append(f"核心{j+1} {v:>3.0f}%")
        cpu_rows.append("    ".join(row) + "\n")
    cpu_body = Group(cpu_txt, Text(), cpu_rows)
    cpu_panel = Panel(
        cpu_body,
        title="[bold cyan]⚙️ CPU[/]",
        border_style="cyan",
        padding=(0, 1),
    )

    # ---- 内存 ----
    vm = psutil.virtual_memory()
    mem_txt = Text()
    mem_txt.append("使用率 ", style="bold white")
    mem_txt.append(f"{vm.percent:>4.1f}%", style=color_pct(vm.percent))
    mem_txt.append("  ")
    mem_txt.append(bar(vm.percent))
    mem_info = Text()
    mem_info.append(f"已用 {fmt_size(vm.used)}  /  共 {fmt_size(vm.total)}", style="white")
    swap = psutil.swap_memory()
    swap_info = Text()
    if swap.total > 0:
        swap_info.append(f"交换分区 {swap.percent:.0f}%", style="grey70")
    mem_panel = Panel(
        Group(mem_txt, Text(), mem_info, swap_info),
        title="[bold magenta]🧠 内存[/]",
        border_style="magenta",
        padding=(0, 1),
    )

    # ---- 磁盘 ----
    disk_lines = []
    for p in psutil.disk_partitions():
        if p.mountpoint in ("/", "/vol1", "/vol2", "/vol3", "/vol4"):
            try:
                u = psutil.disk_usage(p.mountpoint)
            except Exception:
                continue
            name = "系统盘" if p.mountpoint == "/" else p.mountpoint
            line = Text()
            line.append(f"{name}  ", style="bold white")
            line.append(f"{u.percent:>4.1f}%", style=color_pct(u.percent))
            line.append("  ")
            line.append(bar(u.percent))
            line.append("\n")
            line.append(f"      已用 {fmt_size(u.used)}  /  共 {fmt_size(u.total)}", style="grey70")
            disk_lines.append(Group(line, Text()))
    disk_body = Group(*disk_lines) if disk_lines else Text("无磁盘信息", style="grey50")
    disk_panel = Panel(
        disk_body,
        title="[bold green]💾 磁盘[/]",
        border_style="green",
        padding=(0, 1),
    )

    # ---- 温度 ----
    # 传感器标签翻译表
    label_map = {
        "Package id 0": "处理器",
        "Composite": "固态盘",
        "pch_skylake": "芯片组",
        "acpitz": "主板",
        "nvme": "固态盘",
    }
    temp_lines = []
    try:
        all_temps = psutil.sensors_temperatures()
        core_items = []
        other_items = []
        for key, sensors in all_temps.items():
            for s in sensors:
                raw_label = s.label or key
                label = label_map.get(raw_label, raw_label)
                if label.startswith("Core"):
                    label = "核心" + label[4:].strip()
                entry = (s.current, label)
                if label.startswith("核心"):
                    core_items.append(entry)
                else:
                    other_items.append(entry)
        # 核心温度两两一行
        for i in range(0, len(core_items), 2):
            row = Text()
            for cur, label in core_items[i:i + 2]:
                row.append(f"{label} {cur:.0f}°C", style=temp_color(cur))
                row.append("    ")
            temp_lines.append(row)
        # 其他传感器
        for cur, label in other_items:
            temp_lines.append(Text(f"{label} {cur:.0f}°C", style=temp_color(cur)))
    except Exception:
        temp_lines.append(Text("无温度数据", style="grey50"))
    temp_body = Group(*temp_lines) if temp_lines else Text("无温度数据", style="grey50")
    temp_panel = Panel(
        temp_body,
        title="[bold red]🌡️ 温度[/]",
        border_style="red",
        padding=(0, 1),
    )

    # ---- 网络 ----
    now_net = psutil.net_io_counters()
    now_t = time.time()
    dt = max(now_t - _last_t, 0.001)
    up = (now_net.bytes_sent - _last_net.bytes_sent) / dt
    down = (now_net.bytes_recv - _last_net.bytes_recv) / dt
    _last_net, _last_t = now_net, now_t
    net_txt = Text()
    net_txt.append(" ↑ 上传 ", style="bold green")
    net_txt.append(fmt_speed(up), style="green")
    net_txt.append("      ↓ 下载 ", style="bold blue")
    net_txt.append(fmt_speed(down), style="blue")
    net_panel = Panel(
        Align.center(net_txt),
        title="[bold yellow]🌐 网络[/]",
        border_style="yellow",
        padding=(0, 1),
    )

    # ---- 组装左右两栏 ----
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(Group(cpu_panel, mem_panel), Group(temp_panel, disk_panel))

    body = Group(grid, Text(), net_panel)

    # 时间戳
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    title_txt = Text()
    title_txt.append("🖥️ 飞牛NAS · 实时监控", style="bold white on blue")
    title_txt.append(f"    {ts}", style="grey50")

    return Panel(
        body,
        title=title_txt,
        border_style="bright_blue",
        padding=(1, 2),
    )


def main():
    console.clear()
    try:
        with Live(build_frame(), console=console, refresh_per_second=1.0, screen=False) as live:
            while True:
                time.sleep(1)
                live.update(build_frame())
    except KeyboardInterrupt:
        console.print("\n[bold green]已退出监控，下次想看随时敲 zhmon ～[/]")


if __name__ == "__main__":
    main()
