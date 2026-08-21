from __future__ import annotations

from .models import ChangeKind, ContractChange, ContractField, ContractSnapshot, Severity


def _field_map(contract: ContractSnapshot) -> dict[str, ContractField]:
    return {item.path: item for item in contract.fields}


def compare_contracts(before: ContractSnapshot, after: ContractSnapshot) -> list[ContractChange]:
    if before.name != after.name or before.kind != after.kind:
        return [
            ContractChange(
                contract=after.name,
                path="/",
                kind=ChangeKind.CHANGED,
                severity=Severity.BREAKING,
                reason="contract identity or kind changed",
                before=before.kind,
                after=after.kind,
            )
        ]

    left, right = _field_map(before), _field_map(after)
    changes: list[ContractChange] = []
    for path in sorted(left.keys() - right.keys()):
        changes.append(
            ContractChange(
                contract=before.name,
                path=path,
                kind=ChangeKind.REMOVED,
                severity=Severity.BREAKING,
                reason="field removed",
                before=left[path].model_dump(),
            )
        )
    for path in sorted(right.keys() - left.keys()):
        field = right[path]
        severity = Severity.BREAKING if field.required else Severity.INFO
        changes.append(
            ContractChange(
                contract=after.name,
                path=path,
                kind=ChangeKind.ADDED,
                severity=severity,
                reason="required field added" if field.required else "optional field added",
                after=field.model_dump(),
            )
        )
    for path in sorted(left.keys() & right.keys()):
        old, new = left[path], right[path]
        if old.type != new.type:
            changes.append(
                ContractChange(
                    contract=after.name,
                    path=path,
                    kind=ChangeKind.CHANGED,
                    severity=Severity.BREAKING,
                    reason="field type changed",
                    before=old.type,
                    after=new.type,
                )
            )
            continue
        if not old.required and new.required:
            changes.append(
                ContractChange(
                    contract=after.name,
                    path=path,
                    kind=ChangeKind.CHANGED,
                    severity=Severity.BREAKING,
                    reason="optional field became required",
                    before=False,
                    after=True,
                )
            )
        if old.enum != new.enum and old.enum is not None and new.enum is not None:
            removed = sorted(set(old.enum) - set(new.enum), key=str)
            if removed:
                changes.append(
                    ContractChange(
                        contract=after.name,
                        path=path,
                        kind=ChangeKind.CHANGED,
                        severity=Severity.BREAKING,
                        reason="enum values removed",
                        before=old.enum,
                        after=new.enum,
                    )
                )
        if (
            old.minimum != new.minimum
            and new.minimum is not None
            and (old.minimum is None or new.minimum > old.minimum)
        ):
            changes.append(
                ContractChange(
                    contract=after.name,
                    path=path,
                    kind=ChangeKind.CHANGED,
                    severity=Severity.BREAKING,
                    reason="minimum constraint tightened",
                    before=old.minimum,
                    after=new.minimum,
                )
            )
        if (
            old.maximum != new.maximum
            and new.maximum is not None
            and (old.maximum is None or new.maximum < old.maximum)
        ):
            changes.append(
                ContractChange(
                    contract=after.name,
                    path=path,
                    kind=ChangeKind.CHANGED,
                    severity=Severity.BREAKING,
                    reason="maximum constraint tightened",
                    before=old.maximum,
                    after=new.maximum,
                )
            )
    return changes
