from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib import font_manager, rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..prpd import generate_prpd_matrix
from .theme import chart_colors

for _font_path in (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/Deng.ttf"),
    Path("C:/Windows/Fonts/simhei.ttf"),
):
    if _font_path.is_file():
        font_manager.fontManager.addfont(str(_font_path))
        rcParams["font.family"] = font_manager.FontProperties(fname=str(_font_path)).get_name()
        rcParams["axes.unicode_minus"] = False
        break


class BaseCanvas(FigureCanvasQTAgg):
    def __init__(self, *, dark: bool = False, height: float = 3.2) -> None:
        self.dark = dark
        self.figure = Figure(figsize=(6, height), dpi=100, tight_layout=True)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setMinimumHeight(260)
        self.apply_theme(dark)

    def apply_theme(self, dark: bool) -> None:
        self.dark = dark
        colors = chart_colors(dark=dark)
        self.figure.set_facecolor(colors["background"])
        self.axes.set_facecolor(colors["background"])
        for spine in self.axes.spines.values():
            spine.set_color(colors["grid"])
        self.axes.tick_params(colors=colors["text"])
        self.axes.xaxis.label.set_color(colors["text"])
        self.axes.yaxis.label.set_color(colors["text"])
        self.axes.title.set_color(colors["text"])
        self.draw_idle()


class WaveformCanvas(BaseCanvas):
    def __init__(self, *, dark: bool = False) -> None:
        super().__init__(dark=dark)
        self.setAccessibleName("局部放电信号波形图")
        self.setAccessibleDescription("显示信号采样点与幅值的变化")

    def plot_signal(self, samples: np.ndarray) -> None:
        colors = chart_colors(dark=self.dark)
        self.axes.clear()
        step = max(1, len(samples) // 5000)
        indices = np.arange(0, len(samples), step)
        self.axes.plot(indices, samples[::step], color=colors["primary"], linewidth=1.0)
        self.axes.set_title("局部放电波形")
        self.axes.set_xlabel("采样点")
        self.axes.set_ylabel("幅值")
        self.axes.grid(True, color=colors["grid"], alpha=0.55, linestyle="--")
        self.setAccessibleDescription(
            f"波形共 {len(samples)} 个采样点，最小值 {float(np.min(samples)):.4g}，"
            f"最大值 {float(np.max(samples)):.4g}"
        )
        self.apply_theme(self.dark)


class PrpdCanvas(BaseCanvas):
    def __init__(self, *, dark: bool = False) -> None:
        self._colorbar = None
        super().__init__(dark=dark)
        self.setAccessibleName("相位分辨局部放电图")
        self.setAccessibleDescription("显示信号在 0 到 360 度相位上的放电分布")

    def plot_signal(self, samples: np.ndarray, sampling_rate_hz: int = 1_000_000) -> None:
        phase, amplitude, matrix = generate_prpd_matrix(
            samples, sampling_rate_hz=sampling_rate_hz
        )
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)
        mesh = self.axes.pcolormesh(phase, amplitude, matrix.T, shading="auto", cmap="viridis")
        colorbar = self.figure.colorbar(mesh, ax=self.axes)
        colorbar.set_label("放电频次")
        self.axes.set_title("相位分辨局部放电图（PRPD）")
        self.axes.set_xlabel("相位（°）")
        self.axes.set_ylabel("幅值")
        self.axes.set_xlim(0, 360)
        self.setAccessibleDescription(
            f"PRPD 图由 {len(samples)} 个采样点生成，采样率 {sampling_rate_hz} Hz"
        )
        self.apply_theme(self.dark)


class ProbabilityCanvas(BaseCanvas):
    def __init__(self, *, dark: bool = False) -> None:
        super().__init__(dark=dark, height=2.7)
        self.setMinimumHeight(220)
        self.setAccessibleName("诊断类别概率图")
        self.setAccessibleDescription("显示各诊断类别的模型概率")

    def plot_probabilities(self, probabilities: dict[str, float]) -> None:
        colors = chart_colors(dark=self.dark)
        self.axes.clear()
        labels = list(probabilities)
        values = list(probabilities.values())
        positions = np.arange(len(labels))
        bars = self.axes.barh(positions, values, color=colors["primary"], height=0.55)
        self.axes.set_yticks(positions, [shorten(value) for value in labels])
        self.axes.invert_yaxis()
        self.axes.set_xlim(0, 1)
        self.axes.set_xlabel("概率")
        for bar, value in zip(bars, values):
            self.axes.text(
                min(value + 0.02, 0.94),
                bar.get_y() + bar.get_height() / 2,
                f"{value:.1%}",
                va="center",
                color=colors["text"],
                fontsize=9,
            )
        self.setAccessibleDescription(
            "；".join(f"{label} {value:.1%}" for label, value in probabilities.items())
        )
        self.axes.grid(True, axis="x", color=colors["grid"], alpha=0.5, linestyle="--")
        self.apply_theme(self.dark)


def shorten(value: str, limit: int = 12) -> str:
    aliases = {
        "金属突出物缺陷": "金属突出",
        "自由微粒缺陷": "自由微粒",
        "绝缘子表面金属污染物缺陷": "绝缘子污染",
        "气隙缺陷": "气隙",
    }
    if value in aliases:
        return aliases[value]
    return value if len(value) <= limit else value[: limit - 1] + "…"
