"""导入带独立标签的科普图谱；重复运行不重复创建，不删除已有数据。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from env import get_env_value
from config.config import Config
from py2neo import Graph

HYPERTENSION_SOURCE = "https://www.who.int/news-room/fact-sheets/detail/hypertension"
DIABETES_SOURCE = "https://www.who.int/news-room/fact-sheets/detail/diabetes"
DATASET = "赛博华佗医学科普v1"


def main():
    config = Config.get_instance()
    graph = Graph(
        config.get_with_nested_params("database", "neo4j", "url"),
        auth=(config.get_with_nested_params("database", "neo4j", "username"), get_env_value("NEO4J_PASSWORD")),
        name=config.get_with_nested_params("database", "neo4j", "database"),
    )
    categories = {
        "疾病": ["高血压", "糖尿病"],
        "健康特征": ["可无明显症状"],
        "症状": ["严重头痛", "胸痛", "视物模糊", "口渴", "多尿", "乏力", "不明原因体重下降"],
        "危险因素": ["高盐饮食", "超重或肥胖", "缺乏身体活动", "过量饮酒", "烟草使用", "年龄增长", "家族史"],
        "健康管理": ["减少食盐", "均衡膳食", "规律身体活动", "保持健康体重", "戒烟", "避免过量饮酒", "定期测量血压", "遵医嘱治疗", "规范血糖监测"],
    }
    edges = []
    for disease, source in [("高血压", HYPERTENSION_SOURCE), ("糖尿病", DIABETES_SOURCE)]:
        edges.append((disease, "表现特点", "可无明显症状", source,
                      "高血压常无明显症状，需规范测量确认" if disease == "高血压" else "2型糖尿病可症状轻微或不明显，不能凭症状排除"))
        symptoms = ["严重头痛", "胸痛", "视物模糊"] if disease == "高血压" else ["口渴", "多尿", "乏力", "不明原因体重下降", "视物模糊"]
        for name in symptoms:
            edges.append((disease, "可能症状", name, source,
                          "血压很高时可能出现；如同时出现严重症状应立即就医，不是所有高血压患者的常见表现" if disease == "高血压" else "可能出现的症状，确诊需要规范检测"))
        risks = categories["危险因素"] if disease == "高血压" else ["超重或肥胖", "缺乏身体活动"]
        for name in risks:
            edges.append((disease, "危险因素", name, source,
                          "高血压相关危险因素" if disease == "高血压" else "此关系特指2型糖尿病风险，不概括所有类型"))
        measures = ["均衡膳食", "规律身体活动", "保持健康体重", "戒烟", "遵医嘱治疗"]
        measures += ["减少食盐", "避免过量饮酒", "定期测量血压"] if disease == "高血压" else ["规范血糖监测"]
        for name in measures:
            edges.append((disease, "健康管理", name, source, "一般健康教育；具体治疗与监测方案由医务人员结合病情制定，不自行停药"))
    before = graph.run("MATCH (n) RETURN count(n) AS nodes").data()[0]
    tx = graph.begin()
    try:
        for label, names in categories.items():
            tx.run(
                f"UNWIND $names AS name MERGE (n:CyberDoctorMedical:`{label}` {{名称: name}}) "
                "ON CREATE SET n.知识集=$dataset, n.数据性质='医学科普整理，非患者数据'",
                names=names, dataset=DATASET,
            )
        for start, relation, end, source, note in edges:
            tx.run(
                f"MATCH (a:CyberDoctorMedical {{名称:$start}}),(b:CyberDoctorMedical {{名称:$end}}) "
                f"MERGE (a)-[r:`{relation}`]->(b) "
                "ON CREATE SET r.来源=$source, r.说明=$note, r.知识集=$dataset",
                start=start, end=end, source=source, note=note, dataset=DATASET,
            )
        graph.commit(tx)
    except Exception:
        graph.rollback(tx)
        raise
    print("Database nodes before import:", before, flush=True)
    print("Dataset counts:", graph.run(
        "MATCH (n:CyberDoctorMedical) WITH count(n) AS nodes "
        "MATCH (:CyberDoctorMedical)-[r]->(:CyberDoctorMedical) RETURN nodes,count(r) AS relationships"
    ).data(), flush=True)
    print("Hypertension query:", graph.run(
        "MATCH (a:CyberDoctorMedical {名称:'高血压'})-[r]->(b) "
        "RETURN a.名称 AS disease,type(r) AS relationship,b.名称 AS target,r.说明 AS note,r.来源 AS source"
    ).data(), flush=True)


if __name__ == "__main__":
    main()
