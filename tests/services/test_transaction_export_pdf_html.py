from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional

from app.db.models.item import Unit
from app.db.models.transaction import OperationType, TransactionStatus
from app.db.models.transaction_event import ActionType
from app.services.transaction.transaction_service import TransactionService


def _transaction_event_created(performed_by: int, timestamp: datetime):
    return SimpleNamespace(
        action_type=ActionType.CREATED,
        performed_by=performed_by,
        timestamp=timestamp,
    )


def _line(item_name: str, quantity: str, unit: Unit):
    return SimpleNamespace(
        item=SimpleNamespace(name=item_name, unit=unit),
        quantity=Decimal(quantity),
    )


def _transaction(
    transaction_id: int,
    operation_type: OperationType,
    status: TransactionStatus,
    created_at: datetime,
    description: str,
    branch_name: str,
    destination_branch_name: Optional[str],
    performed_by: int,
    lines,
):
    return SimpleNamespace(
        id=transaction_id,
        operation_type=operation_type,
        status=status,
        created_at=created_at,
        description=description,
        branch=SimpleNamespace(name=branch_name),
        destination_branch=SimpleNamespace(name=destination_branch_name) if destination_branch_name else None,
        events=[_transaction_event_created(performed_by=performed_by, timestamp=created_at)],
        lines=lines,
    )


def test_build_pdf_rows_html_merges_transaction_cells_with_rowspan():
    now = datetime.utcnow()
    user_map = {
        10: SimpleNamespace(id=10, name="Admin Export"),
    }

    tx_with_two_lines = _transaction(
        transaction_id=101,
        operation_type=OperationType.TRANSFER,
        status=TransactionStatus.TRANSIT,
        created_at=now,
        description="Traspaso con dos líneas",
        branch_name="Sede A",
        destination_branch_name="Sede B",
        performed_by=10,
        lines=[
            _line("Harina", "5.500", Unit.KILOGRAM),
            _line("Aceite", "2.000", Unit.LITER),
        ],
    )

    tx_with_one_line = _transaction(
        transaction_id=102,
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        created_at=now,
        description="Entrada",
        branch_name="Sede A",
        destination_branch_name=None,
        performed_by=10,
        lines=[
            _line("Azúcar", "1.000", Unit.KILOGRAM),
        ],
    )

    html_rows = TransactionService._build_pdf_rows_html(
        [tx_with_two_lines, tx_with_one_line],
        user_map=user_map,
    )

    assert html_rows.count("<tr>") == 3

    # Transaction 101 has 2 lines so merged cells must use rowspan=2 exactly once per merged column.
    assert html_rows.count('<td rowspan="2" class="pdf-cell-merged pdf-group-odd">101</td>') == 1
    assert html_rows.count('<td rowspan="2" class="pdf-cell-merged pdf-group-odd">Sede A</td>') == 1
    assert html_rows.count('<td rowspan="2" class="pdf-cell-merged pdf-group-odd">Sede B</td>') == 1

    # Item-level cells must remain unmerged and appear once per line.
    assert '<td class="pdf-line-cell pdf-line-odd">Harina</td>' in html_rows
    assert '<td class="pdf-line-cell pdf-line-even">Aceite</td>' in html_rows
    assert '<td class="pdf-line-cell pdf-line-odd">Azúcar</td>' in html_rows

    # Quantity formatting remains aligned with existing CSV/PDF formatting rules.
    assert '<td class="pdf-col-qty pdf-line-cell pdf-line-odd">5,5</td>' in html_rows
    assert '<td class="pdf-col-qty pdf-line-cell pdf-line-even">2</td>' in html_rows
    assert '<td class="pdf-col-qty pdf-line-cell pdf-line-odd">1</td>' in html_rows
