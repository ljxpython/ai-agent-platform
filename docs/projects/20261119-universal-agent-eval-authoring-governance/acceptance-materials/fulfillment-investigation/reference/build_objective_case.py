"""Build a separate objective task using the frozen final fulfillment rules."""

import json

from build_executable_case import build_case
from verify_materials import ROOT, STATES, verify


def build_objective_case():
    fixed = build_case()
    verified = verify()
    final = json.loads((ROOT / "reference/expected-results.json").read_text())["V3"]
    rules = fixed["turns"][1]["content"].split("请给出纳入订单数", 1)[0]
    rules = rules.replace("确认统计口径V1", "本次完整任务的最终统计口径")
    rules = rules.replace(
        "暂时计入is_test=true的启用门店。", "排除is_test=true的门店。"
    )
    files = {**fixed["fixture"], **fixed["turns"][2]["fixture"]}
    prefix = "/workspace/work/fulfillment_objective/"
    artifacts = {
        prefix + path.rsplit("/", 1)[-1]: assertion
        for path, assertion in fixed["expectations"]["artifacts"].items()
        if path.endswith(".csv")
    }
    artifacts[prefix + "summary.json"] = {
        "json_equals": {
            "eligible_orders": final["eligible_orders"],
            "eligible_amount": final["eligible_amount"],
            **{state: len(final[state]) for state in STATES},
            "overdue_amount": final["overdue_amount"],
            "overdue_rate_pct": final["overdue_rate_pct"],
            "due_orders": verified["due_orders"],
            "due_only_overdue_rate_pct": verified["due_only_overdue_rate_pct"],
        }
    }
    csv_contract = fixed["turns"][4]["content"].split(
        "1. order_audit.csv", 1
    )[1].split("4. investigation_report.md", 1)[0]
    export_contract = fixed["turns"][4]["content"].split(
        "自动化版本的文件约定：", 1
    )[1].split("本次由评测器直接读取交付文件", 1)[0]
    export_contract = export_contract.replace(
        "/workspace/work/fulfillment_acceptance", prefix.rstrip("/")
    )
    prompt = (
        "这是一个资料完整的合成表格处理任务。以下六份原始文件已一次提供，"
        "请自主读取、计算、生成结果并实际读回复核，无需等待后续用户消息。"
        "只计算下述最终口径，不生成或解释V1/V2历史过程。原件不得修改。\n"
        + rules
        + "\n实际附件路径：\n"
        + "\n".join(name + "：{{" + name + "}}" for name in files)
        + "\n请在" + prefix + "真实生成三份CSV及一份JSON：\n1. order_audit.csv"
        + csv_contract
        + "4. summary.json：只包含eligible_orders、eligible_amount、on_time、"
        "shipped_late、overdue_unshipped、pending_not_due、overdue_amount、"
        "overdue_rate_pct、due_orders、due_only_overdue_rate_pct。数量为JSON整数，"
        "金额及百分比为两位小数字符串，百分比不带%符号。due_orders按纳入订单的"
        "SLA截止是否不晚于统计截止计算；提前发货不等于SLA已经到期。"
        "主比例分母为全部纳入订单数，辅助比例分母为due_orders，两者分别计算。\n"
        + export_contract
        + "\n使用read_file等文件工具分析并生成真实文件，可逐个写入和修订；"
        "不调用execute、background_execute或委派其他Agent执行命令，不访问外部系统或数据库。"
        "本次材料和规则完整，不请求额外澄清或计划审阅。工具写入审批由评测器按四条路径处理。"
        "原件SHA256由评测器独立记录并读回比较，你无需计算或编造哈希。"
        "生成后实际读取四份产物和原件核对业务内容，最后用普通文字列出四条路径；"
        "不调用present_artifacts，不声称尚未执行的步骤已经完成。"
    )
    return {
        **fixed,
        "case_id": "fulfillment-objective",
        "suite": "core",
        "fixture": files,
        "turns": [{"content": prompt, "approval": "approve"}],
        "turn_expectations": [],
        "business_rules": [
            "完整六表一次提供，只按最终排除测试店的口径处理，不要求重演历史过程。",
            "六份原件只读，四份产物由独立规则检查；自动审批仅限已声明的四条交付路径。",
        ],
        "rubric_version": "fulfillment-objective-v1",
        "provenance": {
            **fixed["provenance"],
            "source_ref": "manual:fulfillment-objective",
            "family_id": "fulfillment-objective",
            "transformation_version": "1",
        },
        "expectations": {
            "artifacts": artifacts,
            "approval_allow": {name: list(artifacts) for name in ("write_file", "edit_file")},
        },
        "metrics": [
            {"name": name, "hard_gate": True}
            for name in ("completion", "artifact_correct", "protected_unchanged")
        ],
    }


if __name__ == "__main__":
    print(json.dumps(build_objective_case(), ensure_ascii=False, indent=2))
