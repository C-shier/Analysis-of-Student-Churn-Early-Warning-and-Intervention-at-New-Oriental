-- 新东方学生流失预警与干预分析核心 SQL
-- 说明：以下 SQL 假设模型结果表已导入为 student_churn_alert_result。
-- 表字段与 `结果/新东方学生流失预警结果.csv` 保持一致。

-- 1. 风险等级分布
SELECT
    风险等级,
    COUNT(*) AS 人数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS 占比
FROM student_churn_alert_result
GROUP BY 风险等级
ORDER BY
    CASE 风险等级
        WHEN '高风险' THEN 1
        WHEN '中风险' THEN 2
        WHEN '低风险' THEN 3
        ELSE 4
    END;

-- 2. 不同风险等级下的真实流失命中情况
SELECT
    风险等级,
    COUNT(*) AS 合计,
    SUM(CASE WHEN 下季度常规是否在读 = '否' THEN 1 ELSE 0 END) AS 真实流失数,
    SUM(CASE WHEN 下季度常规是否在读 = '是' THEN 1 ELSE 0 END) AS 真实未流失数,
    ROUND(
        SUM(CASE WHEN 下季度常规是否在读 = '否' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS 真实流失占比
FROM student_churn_alert_result
GROUP BY 风险等级
ORDER BY
    CASE 风险等级
        WHEN '高风险' THEN 1
        WHEN '中风险' THEN 2
        WHEN '低风险' THEN 3
        ELSE 4
    END;

-- 3. 流失原因标签分布
SELECT
    流失原因标签,
    COUNT(*) AS 人数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS 占比
FROM student_churn_alert_result
GROUP BY 流失原因标签
ORDER BY 人数 DESC;

-- 4. 科目维度风险分布
SELECT
    科目,
    COUNT(*) AS 合计,
    SUM(CASE WHEN 风险等级 = '高风险' THEN 1 ELSE 0 END) AS 高风险人数,
    SUM(CASE WHEN 风险等级 = '中风险' THEN 1 ELSE 0 END) AS 中风险人数,
    SUM(CASE WHEN 风险等级 = '低风险' THEN 1 ELSE 0 END) AS 低风险人数,
    ROUND(SUM(CASE WHEN 风险等级 = '高风险' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS 高风险占比,
    ROUND(SUM(CASE WHEN 下季度常规是否在读 = '否' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS 真实流失率
FROM student_churn_alert_result
GROUP BY 科目
ORDER BY 高风险占比 DESC;

-- 5. 年级维度风险分布
SELECT
    年级序数处理值,
    COUNT(*) AS 合计,
    SUM(CASE WHEN 风险等级 = '高风险' THEN 1 ELSE 0 END) AS 高风险人数,
    SUM(CASE WHEN 风险等级 = '中风险' THEN 1 ELSE 0 END) AS 中风险人数,
    SUM(CASE WHEN 风险等级 = '低风险' THEN 1 ELSE 0 END) AS 低风险人数,
    ROUND(SUM(CASE WHEN 风险等级 = '高风险' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS 高风险占比,
    ROUND(SUM(CASE WHEN 下季度常规是否在读 = '否' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS 真实流失率
FROM student_churn_alert_result
GROUP BY 年级序数处理值
ORDER BY 高风险占比 DESC;

-- 6. Top50 干预优先名单
SELECT
    学员编码,
    班级名称,
    科目,
    年级序数处理值,
    下季度常规是否在读,
    流失概率,
    风险等级,
    可挽回系数,
    学员价值系数,
    干预优先级分数,
    流失原因标签,
    建议动作
FROM student_churn_alert_result
ORDER BY 干预优先级分数 DESC
LIMIT 50;

-- 7. 建议动作统计
SELECT
    建议动作,
    COUNT(*) AS 人数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS 占比
FROM student_churn_alert_result
GROUP BY 建议动作
ORDER BY 人数 DESC;
