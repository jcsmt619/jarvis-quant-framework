from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InboxProcessorRuntimeRecord:
    inbox_processor_one_cycle_attempted: bool
    inbox_processor_one_cycle_return_code: int | None
    inbox_processor_one_cycle_decision: str
    approval_records_updated: int
    real_gmail_inbox_read_performed: bool
    paper_arm_enabled: bool = False
    broker_order_call_performed: bool = False
    live_trading_enabled: bool = False


def build_inbox_processor_runtime_record(inbox_processor_once) -> InboxProcessorRuntimeRecord:
    return InboxProcessorRuntimeRecord(
        inbox_processor_one_cycle_attempted=bool(inbox_processor_once.attempted),
        inbox_processor_one_cycle_return_code=inbox_processor_once.processor_return_code,
        inbox_processor_one_cycle_decision=str(inbox_processor_once.decision),
        approval_records_updated=int(inbox_processor_once.approval_records_updated),
        real_gmail_inbox_read_performed=bool(inbox_processor_once.real_gmail_inbox_read_performed),
        paper_arm_enabled=False,
        broker_order_call_performed=False,
        live_trading_enabled=False,
    )


def build_inbox_processor_runtime_notes(inbox_processor_once) -> list[str]:
    record = build_inbox_processor_runtime_record(inbox_processor_once)

    return [
        f"inbox_processor_one_cycle_attempted={str(record.inbox_processor_one_cycle_attempted).lower()}",
        f"inbox_processor_one_cycle_return_code={record.inbox_processor_one_cycle_return_code}",
        f"inbox_processor_one_cycle_decision={record.inbox_processor_one_cycle_decision}",
        f"approval_records_updated={record.approval_records_updated}",
        f"real_gmail_inbox_read_performed={str(record.real_gmail_inbox_read_performed).lower()}",
        f"paper_arm_enabled={str(record.paper_arm_enabled).lower()}",
        f"broker_order_call_performed={str(record.broker_order_call_performed).lower()}",
        f"live_trading_enabled={str(record.live_trading_enabled).lower()}",
    ]
