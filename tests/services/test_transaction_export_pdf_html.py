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
        last_event_at=created_at,
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

    assert html_rows.count("<tr ") == 3
    assert 'class="pdf-row pdf-row-start pdf-row-not-last pdf-group-odd"' in html_rows
    assert 'class="pdf-row pdf-row-continuation pdf-row-last pdf-group-odd"' in html_rows
    assert 'class="pdf-row pdf-row-start pdf-row-last pdf-group-even"' in html_rows

    # Transaction-level values appear once per operation and continuation rows keep merged cells empty.
    assert html_rows.count('<div class="pdf-cell-merged-content">101</div>') == 1
    assert html_rows.count('<div class="pdf-cell-merged-content">Sede A</div>') == 2
    assert html_rows.count('<div class="pdf-cell-merged-content">Sede B</div>') == 1
    assert html_rows.count('pdf-merged-empty') >= 7  # Continuation rows have multiple empty merged cells

    # Item-level cells must remain unmerged and appear once per line.
    assert '<td class="pdf-line-cell pdf-line-odd">Harina</td>' in html_rows
    assert '<td class="pdf-line-cell pdf-line-even">Aceite</td>' in html_rows
    assert '<td class="pdf-line-cell pdf-line-odd">Azúcar</td>' in html_rows

    # Quantity formatting remains aligned with existing CSV/PDF formatting rules.
    assert '<td class="pdf-col-qty pdf-line-cell pdf-line-odd">5,5</td>' in html_rows
    assert '<td class="pdf-col-qty pdf-line-cell pdf-line-even">2</td>' in html_rows
    assert '<td class="pdf-col-qty pdf-line-cell pdf-line-odd">1</td>' in html_rows


def test_build_pdf_filter_chips_html_without_filters_uses_default_label():
    html_chips = TransactionService._build_pdf_filter_chips_html(
        db=None,
        branch_id=None,
        operation_type=None,
        status_filter=None,
        performed_by=None,
        item_id=None,
        start_date=None,
        end_date=None,
        search=None,
        order_label="Fecha y hora (mas reciente primero)",
    )

    assert '<li class="pdf-filter-chip">Sin filtros adicionales</li>' in html_chips
    assert '<li class="pdf-filter-chip">Ordenación: Fecha y hora (mas reciente primero)</li>' in html_chips


def test_build_pdf_rows_html_without_transactions_returns_empty_row():
    html_rows = TransactionService._build_pdf_rows_html([], user_map={})

    assert 'class="pdf-row pdf-row-empty"' in html_rows
    assert 'No hay operaciones para los criterios seleccionados.' in html_rows
