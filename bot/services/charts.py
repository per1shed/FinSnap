from decimal import Decimal
from io import BytesIO
from datetime import date

from bot.services.goals_format import progress_percent

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

DARK_COLORS = [
    "#4FC3F7",
    "#81C784",
    "#FFB74D",
    "#E57373",
    "#BA68C8",
    "#4DB6AC",
    "#FFD54F",
    "#90A4AE",
]


def build_goal_progress_pie(saved: Decimal, target: Decimal, title: str) -> BytesIO:
    """Круговая диаграмма прогресса цели: накоплено / осталось."""
    saved_f = float(max(saved, Decimal("0")))
    target_f = float(target)
    remaining_f = float(max(target - saved, Decimal("0")))

    if saved >= target and target > 0:
        labels = ["Накоплено", "Сверх цели"]
        values = [target_f, saved_f - target_f]
        colors = ["#81C784", "#4FC3F7"]
    elif saved_f == 0:
        labels = ["Осталось"]
        values = [target_f]
        colors = ["#616161"]
    else:
        labels = ["Накоплено", "Осталось"]
        values = [saved_f, remaining_f]
        colors = ["#81C784", "#616161"]

    return _render_pie(labels, values, title, colors)


def _truncate_label(text: str, max_len: int = 22) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def build_goals_overview_pie(goals: list, title: str = "Прогресс по целям") -> BytesIO:
    """Горизонтальная диаграмма: % выполнения каждой цели (как в подписи к фото)."""
    if not goals:
        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(7, 3), facecolor="#121212")
        ax.set_facecolor("#121212")
        ax.text(
            0.5,
            0.5,
            "Нет активных целей",
            ha="center",
            va="center",
            color="#BDBDBD",
            transform=ax.transAxes,
        )
        ax.axis("off")
        ax.set_title(title, color="#FFFFFF", fontsize=14, pad=12)
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=120, facecolor=fig.get_facecolor())
        plt.close(fig)
        buffer.seek(0)
        return buffer

    labels = [_truncate_label(g.title) for g in goals]
    pcts = [progress_percent(g.saved_amount, g.target_amount) for g in goals]

    plt.style.use("dark_background")
    height = max(3.0, len(goals) * 0.72 + 1.2)
    fig, ax = plt.subplots(figsize=(8, height), facecolor="#121212")
    ax.set_facecolor("#121212")

    y_pos = list(range(len(goals)))
    colors = [DARK_COLORS[i % len(DARK_COLORS)] for i in range(len(goals))]
    bars = ax.barh(y_pos, pcts, color=colors, height=0.55, zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, color="#E0E0E0", fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Прогресс, %", color="#BDBDBD", fontsize=10)
    ax.set_title(title, color="#FFFFFF", fontsize=14, pad=14)
    ax.tick_params(axis="x", colors="#BDBDBD", labelsize=9)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#2A2A2A", linewidth=0.8, alpha=0.65, zorder=0)

    for bar, pct in zip(bars, pcts):
        label_x = min(float(pct) + 2.0, 96.0) if pct > 0 else 2.0
        ax.text(
            label_x,
            bar.get_y() + bar.get_height() / 2,
            f"{pct:.0f}%",
            va="center",
            ha="left",
            color="#E0E0E0",
            fontsize=9,
            zorder=4,
        )

    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return buffer


def _pie_legend_labels(labels: list[str], values: list[float]) -> list[str]:
    total = sum(values)
    if total <= 0:
        return list(labels)
    return [f"{label} — {100 * v / total:.1f}%" for label, v in zip(labels, values)]


def _style_legend(legend) -> None:
    frame = legend.get_frame()
    frame.set_facecolor("#1a1a1a")
    frame.set_edgecolor("#404040")
    frame.set_alpha(0.92)
    for text in legend.get_texts():
        text.set_color("#E0E0E0")


def _render_pie(
    labels: list[str], values: list[float], title: str, colors: list[str]
) -> BytesIO:
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(7, 7), facecolor="#121212")
    ax.set_facecolor("#121212")

    slice_colors = colors[: len(values)]
    wedges, _ = ax.pie(
        values,
        labels=None,
        autopct=None,
        startangle=90,
        counterclock=False,
        colors=slice_colors,
        radius=0.72,
        center=(-0.08, 0),
    )

    legend = ax.legend(
        wedges,
        _pie_legend_labels(labels, values),
        loc="upper right",
        bbox_to_anchor=(1.0, 1.0),
        fontsize=9,
        frameon=True,
        borderaxespad=0.6,
    )
    _style_legend(legend)

    ax.set_title(title, color="#FFFFFF", fontsize=14, pad=16)
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return buffer


def build_category_pie(categories: list[tuple[str, Decimal]], title: str) -> BytesIO:
    labels = [name for name, _ in categories]
    values = [float(amount) for _, amount in categories]
    return _render_pie(labels, values, title, DARK_COLORS[: len(values)])


DAY_NAMES_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
WEEKDAY_COLOR = "#E0E0E0"
WEEKEND_COLOR = "#E57373"


def build_daily_histogram(days: list[date], totals: list[Decimal], title: str) -> BytesIO:
    x = list(range(len(days)))
    y = [float(v) for v in totals]

    plt.style.use("dark_background")
    width = max(12, len(days) * 0.38)
    fig, ax = plt.subplots(figsize=(width, 5), facecolor="#121212")
    ax.set_facecolor("#121212")

    ax.set_axisbelow(True)
    ax.grid(
        axis="y",
        color="#2A2A2A",
        linewidth=0.8,
        alpha=0.6,
        zorder=0,
    )
    bar_color = "#4FC3F7"
    bar_edge = "#29B6F6"
    ax.bar(
        x, y, color=bar_color, width=0.75, zorder=3, edgecolor=bar_edge, linewidth=0.5
    )
    hist_legend = ax.legend(
        handles=[
            Patch(facecolor=bar_color, edgecolor=bar_edge, label="Сумма за день"),
        ],
        loc="upper right",
        bbox_to_anchor=(1.0, 1.0),
        fontsize=9,
        frameon=True,
        borderaxespad=0.6,
    )
    _style_legend(hist_legend)
    ax.set_title(title, color="#FFFFFF", fontsize=14, pad=12, zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels([])
    ax.tick_params(axis="y", colors="#BDBDBD", labelsize=9)

    for i, day in enumerate(days):
        weekday = day.weekday()
        is_weekend = weekday >= 5
        color = WEEKEND_COLOR if is_weekend else WEEKDAY_COLOR
        day_abbr = DAY_NAMES_RU[weekday]

        ax.text(
            i,
            -0.03,
            str(day.day),
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            color=color,
            fontsize=8,
            fontweight="bold" if is_weekend else "normal",
            clip_on=False,
        )
        ax.text(
            i,
            -0.11,
            day_abbr,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            color=color,
            fontsize=7,
            clip_on=False,
        )

    ax.set_xlim(-0.6, len(days) - 0.4)
    fig.subplots_adjust(bottom=0.22)
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return buffer
