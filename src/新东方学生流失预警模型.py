# -*- coding: utf-8 -*-
"""新东方学生流失预警模型：脚本自检 + 建模主程序。

运行方式：
    python 新东方学生流失预警模型.py
    python 新东方学生流失预警模型.py --self-test

输出文件：
    新东方学生流失预警结果.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
EXCEL_FILE_NAME = "原始学生花名册.xlsx"
EXCEL_PATH = SCRIPT_DIR.parent / EXCEL_FILE_NAME
SHEET_NAME = "题目6-数据源-花名册表"
OUTPUT_PATH = SCRIPT_DIR / "新东方学生流失预警结果.csv"
TARGET_COL = "下季度常规是否在读"


LEAKAGE_OR_RESULT_COLS = [
    TARGET_COL,
    # 联报字段对“下季度是否在读”暗示性很强，预测模型中剔除，避免答案被质疑数据泄露。
    # 后续仍可用于“学员价值系数”，因为运营排序可以参考已知购买承诺。
    "联报标签",
    "联报类型",
    "离班日期",
    "离班方式名称",
    "开课前流失标志(1-是，0-否)",
    "开课后流失标志(1-是，0-否)",
    "开课前退费(1-是，0-否)",
    "开课后退费(1-是，0-否)",
    "首课流失标志",
]

ID_COLS = [
    "辅助列",
    "学员编码",
    "班级编码",
    "班级名称",
    "课程顾问",
    "带课最多教师",
    "主带课教师",
]


def resolve_excel_path(excel_path):
    """解析Excel路径，支持从任意当前目录运行脚本。"""
    if excel_path:
        candidate = Path(excel_path)
        if candidate.exists():
            return candidate.resolve()
        raise FileNotFoundError(f"找不到Excel文件：{candidate.resolve()}")

    candidates = [
        SCRIPT_DIR / EXCEL_FILE_NAME,
        SCRIPT_DIR.parent / EXCEL_FILE_NAME,
        Path.cwd() / EXCEL_FILE_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    searched = "\n".join(str(candidate.resolve()) for candidate in candidates)
    raise FileNotFoundError(f"找不到Excel文件，已尝试以下位置：\n{searched}")


def build_target(df):
    """将下季度不在读定义为流失样本：否=1，是=0。"""
    if TARGET_COL not in df.columns:
        raise ValueError(f"缺少目标字段：{TARGET_COL}")

    target = df[TARGET_COL].map({"是": 0, "否": 1})
    if target.isna().any():
        bad_values = df.loc[target.isna(), TARGET_COL].drop_duplicates().tolist()
        raise ValueError(f"目标字段存在无法识别的值：{bad_values}")
    return target.astype(int)


def assign_risk_level(probability):
    """把模型概率转成业务可读的风险等级。"""
    if probability >= 0.70:
        return "高风险"
    if probability >= 0.40:
        return "中风险"
    return "低风险"


def build_reason_tags(row):
    """基于可解释业务规则生成流失原因标签。"""
    reasons = []

    if row.get("是否好友 0否 1是", 1) == 0 or row.get("当天是否互动", 1) == 0 or row.get("聊天次数", 1) <= 0:
        reasons.append("互动弱风险")

    reply_seconds = row.get("老师回复平均时长-秒", 0)
    if pd.notna(reply_seconds) and reply_seconds >= 300:
        reasons.append("服务响应风险")

    linked_flag = row.get("联报标签", "是")
    paid_lessons = row.get("实际缴费课次", 10)
    if linked_flag == "否" or (pd.notna(paid_lessons) and paid_lessons < 10):
        reasons.append("购买意愿弱风险")

    source_type = str(row.get("生源类型(新老生标签)", ""))
    previous_regular = row.get("上季度常规是否在读", "是")
    if "新生" in source_type or previous_regular == "否":
        reasons.append("新生适应风险")

    if not reasons:
        reasons.append("综合模型预警")
    return "、".join(reasons)


def intervention_advice(risk_level, reasons):
    """根据风险等级和原因标签给出运营动作。"""
    if risk_level == "高风险":
        if "互动弱风险" in reasons:
            return "当天电话/微信重点触达，补充学习反馈并确认续读意向"
        if "服务响应风险" in reasons:
            return "检查老师响应链路，安排班主任跟进服务体验"
        return "列入重点挽回名单，由老师和课程顾问联合跟进"

    if risk_level == "中风险":
        return "加强课堂互动和学习反馈，观察后续沟通变化"

    return "正常维护，持续观察互动和缴费变化"


def add_time_features(df):
    """把日期字段转成更适合模型使用的时间差特征。"""
    data = df.copy()
    date_cols = [
        "进班日期",
        "开课日期",
        "结课日期",
        "最早进班日期",
        "开课日期处理值",
        "结课日期处理值",
    ]
    for col in date_cols:
        if col in data.columns:
            data[col] = pd.to_datetime(data[col], errors="coerce")

    if "进班日期" in data.columns and "开课日期" in data.columns:
        data["进班距开课天数"] = (data["开课日期"] - data["进班日期"]).dt.days

    if "开课日期" in data.columns and "结课日期" in data.columns:
        data["课程跨度天数"] = (data["结课日期"] - data["开课日期"]).dt.days

    if "最早进班日期" in data.columns and "进班日期" in data.columns:
        data["历史沉淀天数"] = (data["进班日期"] - data["最早进班日期"]).dt.days

    for col in date_cols:
        if col in data.columns:
            data[f"{col}_月份"] = data[col].dt.month
            data[f"{col}_星期"] = data[col].dt.dayofweek
            data = data.drop(columns=[col])

    if "进班时间" in data.columns:
        data["进班时间"] = pd.to_datetime(data["进班时间"], errors="coerce")
        data["进班小时"] = data["进班时间"].dt.hour
        data = data.drop(columns=["进班时间"])

    return data


def prepare_features(df):
    """清洗特征：剔除泄露字段、ID字段、全空字段、常量字段，并编码类别变量。"""
    X = df.copy()
    drop_cols = [col for col in LEAKAGE_OR_RESULT_COLS + ID_COLS if col in X.columns]
    X = X.drop(columns=drop_cols)
    X = X.dropna(axis=1, how="all")
    X = add_time_features(X)

    nunique = X.nunique(dropna=False)
    constant_cols = nunique[nunique <= 1].index.tolist()
    X = X.drop(columns=constant_cols)

    numeric_cols = X.select_dtypes(include=[np.number, "bool"]).columns.tolist()
    category_cols = [col for col in X.columns if col not in numeric_cols]

    for col in numeric_cols:
        X[col] = pd.to_numeric(X[col], errors="coerce")
        X[col] = X[col].fillna(X[col].median())

    for col in category_cols:
        X[col] = X[col].astype("string").fillna("未知")

    X = pd.get_dummies(X, columns=category_cols, dummy_na=False)
    return X


def calculate_recoverability(row):
    """可挽回系数：沟通基础越好，越值得主动运营跟进。"""
    score = 0.40
    score += 0.20 if row.get("是否好友 0否 1是", 0) == 1 else 0
    score += 0.15 if row.get("当天是否互动", 0) == 1 else 0
    score += min(float(row.get("聊天次数", 0) or 0), 5) * 0.03
    score += 0.10 if row.get("客户主动聊天次数", 0) > 0 else 0
    score += 0.10 if row.get("是否优质聊天 ", 0) == 1 else 0
    return min(score, 1.0)


def calculate_student_value(row):
    """学员价值系数：购买承诺和老生稳定性越强，挽回优先级越高。"""
    score = 0.50
    paid_lessons = float(row.get("实际缴费课次", 0) or 0)
    score += min(paid_lessons / 10, 1) * 0.20
    score += 0.15 if row.get("联报标签", "否") == "是" else 0
    score += 0.10 if row.get("上季度常规是否在读", "否") == "是" else 0
    score += 0.05 if "老生" in str(row.get("生源类型(新老生标签)", "")) else 0
    return min(score, 1.0)


def train_model(X_train, y_train):
    """优先使用随机森林；它对表格数据稳健，也能输出特征重要性。"""
    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=20,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test):
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    prob = model.predict_proba(X_test)[:, 1]
    pred = (prob >= 0.40).astype(int)

    metrics = {
        "accuracy": accuracy_score(y_test, pred),
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "f1": f1_score(y_test, pred, zero_division=0),
        "auc": roc_auc_score(y_test, prob),
        "confusion_matrix": confusion_matrix(y_test, pred),
        "classification_report": classification_report(y_test, pred, zero_division=0),
    }
    return metrics, prob


def feature_importance(model, feature_names, top_n=15):
    importance = pd.DataFrame(
        {
            "feature": feature_names,
            "importance": model.feature_importances_,
        }
    )
    return importance.sort_values("importance", ascending=False).head(top_n)


def build_alert_result(df, probabilities):
    result = df[["学员编码", "班级名称", "科目", "年级序数处理值", TARGET_COL]].copy()
    result["流失概率"] = probabilities
    result["风险等级"] = result["流失概率"].apply(assign_risk_level)
    result["可挽回系数"] = df.apply(calculate_recoverability, axis=1)
    result["学员价值系数"] = df.apply(calculate_student_value, axis=1)
    result["干预优先级分数"] = (
        result["流失概率"] * result["可挽回系数"] * result["学员价值系数"]
    )
    result["流失原因标签"] = df.apply(build_reason_tags, axis=1)
    result["建议动作"] = result.apply(
        lambda row: intervention_advice(row["风险等级"], row["流失原因标签"]),
        axis=1,
    )
    return result.sort_values("干预优先级分数", ascending=False)


def run_pipeline(excel_path=EXCEL_PATH, output_path=OUTPUT_PATH):
    from sklearn.model_selection import train_test_split

    excel_path = resolve_excel_path(excel_path)
    output_path = Path(output_path).resolve()

    df = pd.read_excel(excel_path, sheet_name=SHEET_NAME)
    y = build_target(df)
    X = prepare_features(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = train_model(X_train, y_train)
    metrics, _ = evaluate_model(model, X_test, y_test)
    all_probabilities = model.predict_proba(X)[:, 1]
    alert_result = build_alert_result(df, all_probabilities)
    alert_result.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("学生流失预警模型运行结果")
    print("=" * 40)
    print(f"样本量：{len(df)}")
    print(f"流失样本数：{int(y.sum())}")
    print(f"流失率：{y.mean():.2%}")
    print(f"准确率 accuracy：{metrics['accuracy']:.4f}")
    print(f"精确率 precision：{metrics['precision']:.4f}")
    print(f"召回率 recall：{metrics['recall']:.4f}")
    print(f"F1：{metrics['f1']:.4f}")
    print(f"AUC：{metrics['auc']:.4f}")
    print("\n混淆矩阵：")
    print(metrics["confusion_matrix"])
    print("\nTop15重要特征：")
    print(feature_importance(model, X.columns).to_string(index=False))
    print(f"\n预警结果已输出：{output_path.resolve()}")
    print("\n干预优先级Top10：")
    print(
        alert_result[
            [
                "学员编码",
                "科目",
                "风险等级",
                "流失概率",
                "干预优先级分数",
                "流失原因标签",
                "建议动作",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    return metrics, alert_result


def run_self_tests():
    import pandas as pd

    sample = pd.DataFrame(
        {
            "下季度常规是否在读": ["是", "否", "是"],
            "聊天次数": [0, 3, 1],
            "是否好友 0否 1是": [1, 1, 0],
        }
    )

    y = build_target(sample)
    assert y.tolist() == [0, 1, 0]

    risk = assign_risk_level(0.72)
    assert risk == "高风险"

    reason = build_reason_tags(
        {
            "是否好友 0否 1是": 0,
            "当天是否互动": 0,
            "聊天次数": 0,
            "老师回复平均时长-秒": 500,
            "联报标签": "否",
            "实际缴费课次": 3,
            "生源类型(新老生标签)": "纯新新生",
        }
    )
    assert "互动弱风险" in reason
    assert "购买意愿弱风险" in reason

    resolved_excel = resolve_excel_path(None)
    assert resolved_excel.name == EXCEL_FILE_NAME
    assert resolved_excel.exists()

    print("self tests passed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--excel", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    if args.self_test:
        run_self_tests()
    else:
        run_pipeline(args.excel, args.output)
