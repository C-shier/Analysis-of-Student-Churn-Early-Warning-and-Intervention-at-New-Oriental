# -*- coding: utf-8 -*-
"""新东方学生流失预警与干预分析：项目展示输出脚本。

这个脚本用于把模型结果整理成作品集展示材料：

1. 从 `src/新东方学生流失预警结果.csv` 或手动指定路径读取完整预警明细
2. 导出风险分布、命中情况、原因标签、科目/年级风险等数据表到 `data/tables`
3. 生成可放入 README 和 notebook 的项目展示图表到 `images`

运行方式：
    python 新东方学生流失预警与干预分析.py
    python 新东方学生流失预警与干预分析.py --result src/新东方学生流失预警结果.csv
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
TABLE_DIR = PROJECT_ROOT / "data" / "tables"
CHART_DIR = PROJECT_ROOT / "images"
DEFAULT_ALERT_RESULT_PATH = BASE_DIR / "新东方学生流失预警结果.csv"

RISK_ORDER = ["高风险", "中风险", "低风险"]
RISK_COLORS = {
    "高风险": "#c2410c",
    "中风险": "#d97706",
    "低风险": "#0f766e",
}


def configure_plot_style():
    """配置中文图表样式。"""
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["axes.edgecolor"] = "#d4d4d8"
    plt.rcParams["axes.labelcolor"] = "#27272a"
    plt.rcParams["xtick.color"] = "#52525b"
    plt.rcParams["ytick.color"] = "#52525b"


def ensure_dirs():
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)


def resolve_alert_result_path(result_path=None):
    if result_path:
        candidate = Path(result_path).expanduser()
        if candidate.exists():
            return candidate.resolve()
        raise FileNotFoundError(f"找不到预警结果文件：{candidate.resolve()}")

    candidates = [
        DEFAULT_ALERT_RESULT_PATH,
        PROJECT_ROOT / "data" / "新东方学生流失预警结果.csv",
        Path.cwd() / "新东方学生流失预警结果.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    searched = "\n".join(str(candidate.resolve()) for candidate in candidates)
    raise FileNotFoundError(f"找不到预警结果文件，已尝试以下位置：\n{searched}")


def load_alert_result(result_path=None):
    return pd.read_csv(resolve_alert_result_path(result_path))


def percent(series):
    return (series * 100).round(2).astype(str) + "%"


def build_risk_distribution(df):
    distribution = (
        df["风险等级"]
        .value_counts()
        .reindex(RISK_ORDER)
        .rename_axis("风险等级")
        .reset_index(name="人数")
    )
    distribution["占比"] = percent(distribution["人数"] / len(df))
    return distribution


def build_risk_hit_table(df):
    hit = (
        df.pivot_table(
            index="风险等级",
            columns="下季度常规是否在读",
            values="学员编码",
            aggfunc="count",
            fill_value=0,
        )
        .reindex(RISK_ORDER)
        .reset_index()
    )
    for col in ["否", "是"]:
        if col not in hit.columns:
            hit[col] = 0
    hit["合计"] = hit["否"] + hit["是"]
    hit["真实流失占比"] = percent(hit["否"] / hit["合计"])
    return hit[["风险等级", "合计", "否", "是", "真实流失占比"]]


def build_reason_statistics(df):
    reason = (
        df["流失原因标签"]
        .value_counts()
        .rename_axis("流失原因标签")
        .reset_index(name="人数")
    )
    reason["占比"] = percent(reason["人数"] / len(df))
    return reason


def build_segment_risk_table(df, segment_col):
    table = (
        df.pivot_table(
            index=segment_col,
            columns="风险等级",
            values="学员编码",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )
    for risk in RISK_ORDER:
        if risk not in table.columns:
            table[risk] = 0
    table["合计"] = table[RISK_ORDER].sum(axis=1)

    churn = (
        df.assign(是否真实流失=df["下季度常规是否在读"].eq("否").astype(int))
        .groupby(segment_col, as_index=False)["是否真实流失"]
        .mean()
        .rename(columns={"是否真实流失": "真实流失率"})
    )
    table = table.merge(churn, on=segment_col, how="left")
    table["高风险占比"] = table["高风险"] / table["合计"]
    table["高风险占比"] = percent(table["高风险占比"])
    table["真实流失率"] = percent(table["真实流失率"])
    return table[[segment_col, "合计", "高风险", "中风险", "低风险", "高风险占比", "真实流失率"]]


def build_action_statistics(df):
    action = (
        df["建议动作"]
        .value_counts()
        .rename_axis("建议动作")
        .reset_index(name="人数")
    )
    action["占比"] = percent(action["人数"] / len(df))
    return action


def export_tables(df):
    if SUMMARY_XLSX_PATH.exists():
        overview = pd.read_excel(SUMMARY_XLSX_PATH, sheet_name="模型评估总览")
    else:
        overview = pd.DataFrame(
            [
                {"指标": "样本量", "数值": len(df), "说明": "参与预警输出的学生记录数"},
                {
                    "指标": "流失样本数",
                    "数值": int(df["下季度常规是否在读"].eq("否").sum()),
                    "说明": "下季度常规是否在读=否",
                },
                {
                    "指标": "流失率",
                    "数值": f"{df['下季度常规是否在读'].eq('否').mean():.2%}",
                    "说明": "流失样本占总样本比例",
                },
            ]
        )

    tables = {
        "01_模型评估总览.csv": overview,
        "02_风险等级分布.csv": build_risk_distribution(df),
        "03_风险命中情况.csv": build_risk_hit_table(df),
        "04_原因标签统计.csv": build_reason_statistics(df),
        "05_科目风险分布.csv": build_segment_risk_table(df, "科目"),
        "06_年级风险分布.csv": build_segment_risk_table(df, "年级序数处理值"),
        "07_建议动作统计.csv": build_action_statistics(df),
        "08_高风险干预名单Top50.csv": df.sort_values("干预优先级分数", ascending=False).head(50),
    }

    for filename, table in tables.items():
        table.to_csv(TABLE_DIR / filename, index=False, encoding="utf-8-sig")

    return tables


def annotate_bars(ax):
    for patch in ax.patches:
        height = patch.get_height()
        if pd.notna(height):
            ax.annotate(
                f"{height:.0f}",
                (patch.get_x() + patch.get_width() / 2, height),
                ha="center",
                va="bottom",
                fontsize=10,
                color="#27272a",
                xytext=(0, 4),
                textcoords="offset points",
            )


def plot_risk_distribution(risk_distribution):
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [RISK_COLORS[risk] for risk in risk_distribution["风险等级"]]
    ax.bar(risk_distribution["风险等级"], risk_distribution["人数"], color=colors, width=0.55)
    annotate_bars(ax)
    ax.set_title("学生流失风险等级分布", fontsize=15, pad=14)
    ax.set_xlabel("")
    ax.set_ylabel("学生记录数")
    ax.grid(axis="y", color="#e4e4e7", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "01_学生流失风险等级分布.png", dpi=180)
    plt.close(fig)


def plot_risk_hit_rate(risk_hit):
    hit_rate = risk_hit.copy()
    hit_rate["真实流失占比数值"] = hit_rate["真实流失占比"].str.rstrip("%").astype(float)

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [RISK_COLORS[risk] for risk in hit_rate["风险等级"]]
    ax.bar(hit_rate["风险等级"], hit_rate["真实流失占比数值"], color=colors, width=0.55)
    for patch in ax.patches:
        height = patch.get_height()
        ax.annotate(
            f"{height:.2f}%",
            (patch.get_x() + patch.get_width() / 2, height),
            ha="center",
            va="bottom",
            fontsize=10,
            color="#27272a",
            xytext=(0, 4),
            textcoords="offset points",
        )
    ax.set_title("不同风险等级的真实流失占比", fontsize=15, pad=14)
    ax.set_xlabel("")
    ax.set_ylabel("真实流失占比")
    ax.grid(axis="y", color="#e4e4e7", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "02_不同风险等级真实流失占比.png", dpi=180)
    plt.close(fig)


def plot_reason_tags(reason_statistics):
    top_reason = reason_statistics.head(8).sort_values("人数", ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_reason["流失原因标签"], top_reason["人数"], color="#2563eb")
    for patch in ax.patches:
        width = patch.get_width()
        ax.annotate(
            f"{width:.0f}",
            (width, patch.get_y() + patch.get_height() / 2),
            ha="left",
            va="center",
            fontsize=10,
            color="#27272a",
            xytext=(5, 0),
            textcoords="offset points",
        )
    ax.set_title("主要流失原因标签分布", fontsize=15, pad=14)
    ax.set_xlabel("学生记录数")
    ax.set_ylabel("")
    ax.grid(axis="x", color="#e4e4e7", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "03_主要流失原因标签分布.png", dpi=180)
    plt.close(fig)


def plot_segment_high_risk(segment_table, segment_col, filename, title):
    data = segment_table.copy()
    data["高风险占比数值"] = data["高风险占比"].str.rstrip("%").astype(float)
    data["真实流失率数值"] = data["真实流失率"].str.rstrip("%").astype(float)

    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(data))
    ax.bar([i - 0.18 for i in x], data["高风险占比数值"], width=0.36, color="#c2410c", label="高风险占比")
    ax.bar([i + 0.18 for i in x], data["真实流失率数值"], width=0.36, color="#2563eb", label="真实流失率")
    ax.set_xticks(list(x))
    ax.set_xticklabels(data[segment_col])
    ax.set_title(title, fontsize=15, pad=14)
    ax.set_ylabel("占比")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#e4e4e7", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHART_DIR / filename, dpi=180)
    plt.close(fig)


def plot_probability_priority(df):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for risk in RISK_ORDER:
        subset = df[df["风险等级"] == risk]
        ax.scatter(
            subset["流失概率"],
            subset["干预优先级分数"],
            s=18,
            alpha=0.62,
            color=RISK_COLORS[risk],
            label=risk,
        )
    ax.set_title("流失概率与干预优先级分数关系", fontsize=15, pad=14)
    ax.set_xlabel("流失概率")
    ax.set_ylabel("干预优先级分数")
    ax.legend(frameon=False)
    ax.grid(color="#e4e4e7", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "06_流失概率与干预优先级关系.png", dpi=180)
    plt.close(fig)


def export_charts(df, tables):
    plot_risk_distribution(tables["02_风险等级分布.csv"])
    plot_risk_hit_rate(tables["03_风险命中情况.csv"])
    plot_reason_tags(tables["04_原因标签统计.csv"])
    plot_segment_high_risk(
        tables["05_科目风险分布.csv"],
        "科目",
        "04_科目维度风险对比.png",
        "科目维度高风险占比与真实流失率",
    )
    plot_segment_high_risk(
        tables["06_年级风险分布.csv"],
        "年级序数处理值",
        "05_年级维度风险对比.png",
        "年级维度高风险占比与真实流失率",
    )
    plot_probability_priority(df)


def main(result_path=None):
    configure_plot_style()
    ensure_dirs()
    df = load_alert_result(result_path)
    tables = export_tables(df)
    export_charts(df, tables)

    print("新东方学生流失预警与干预分析输出完成")
    print(f"数据表目录：{TABLE_DIR}")
    print(f"图表目录：{CHART_DIR}")
    print(f"样本量：{len(df)}")
    print(f"高风险学生记录数：{int((df['风险等级'] == '高风险').sum())}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=None)
    args = parser.parse_args()

    main(args.result)
