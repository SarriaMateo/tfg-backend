from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from html import escape as html_escape
import csv
import io
import os

from app.db.models.transaction import Transaction, OperationType, TransactionStatus
from app.db.models.transaction_line import TransactionLine
from app.db.models.transaction_event import TransactionEvent, ActionType
from app.db.models.stock_movement import StockMovement, MovementType
from app.db.models.user import User, Role
from app.db.models.item import Item, Unit
from app.repositories.user_repository import UserRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.stock_movement_repository import StockMovementRepository
from app.schemas.transaction import TransactionCreate, TransactionUpdate, TransactionUpdateRequest
from app.schemas.common import PaginatedResponse
from app.core.datetime_utils import madrid_now
from app.core.file_handler import TransactionDocumentHandler
from app.services.user.user_service import UserService


class TransactionService:
    """Business logic service for transactions."""

    # Export constraints
    EXPORT_MAX_LINES_CSV = 50000
    EXPORT_MAX_LINES_PDF = 10000

    OPERATION_TYPE_LABELS = {
        OperationType.IN: "Entrada",
        OperationType.OUT: "Salida",
        OperationType.TRANSFER: "Traspaso",
        OperationType.ADJUSTMENT: "Ajuste",
    }

    STATUS_LABELS = {
        TransactionStatus.PENDING: "Pendiente",
        TransactionStatus.TRANSIT: "En tránsito",
        TransactionStatus.COMPLETED: "Completada",
        TransactionStatus.CANCELLED: "Cancelada",
    }

    UNIT_SHORT_LABELS = {
        Unit.UNIT: "ud",
        Unit.KILOGRAM: "kg",
        Unit.GRAM: "g",
        Unit.LITER: "L",
        Unit.MILLILITER: "mL",
        Unit.METER: "m",
        Unit.SQ_METER: "m²",
        Unit.BOX: "caja",
        Unit.PACK: "pack",
    }

    CSV_HEADERS = [
        "Id",
        "Tipo",
        "Sede",
        "Sede destino",
        "Fecha y hora",
        "Descripción",
        "Estado",
        "Creada por",
        "Artículo",
        "Cantidad",
        "Unidad",
    ]

    @staticmethod
    def _validate_export_permission(current_user: User) -> None:
        """Only ADMIN and MANAGER users can export transactions."""
        if current_user.role not in (Role.ADMIN, Role.MANAGER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

    @staticmethod
    def _validate_export_filter_entities(
        db: Session,
        company_id: int,
        branch_id: Optional[int],
        performed_by: Optional[int],
        item_id: Optional[int],
    ) -> None:
        """Validate export filter entity ownership to prevent cross-company data disclosure."""
        if branch_id is not None:
            branch = BranchRepository.get_by_id(db, branch_id)
            if not branch or branch.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="BRANCH_NOT_FOUND",
                )

        if performed_by is not None:
            user = UserRepository.get_by_id(db, performed_by)
            if not user or user.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="USER_NOT_FOUND",
                )

        if item_id is not None:
            item = ItemRepository.get_by_id(db, item_id)
            if not item or item.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="ITEM_NOT_FOUND",
                )

    @staticmethod
    def _format_decimal_for_export(value: Decimal) -> str:
        """
        Match frontend decimal formatting:
        - Round to 3 decimals
        - Strip trailing zeros and decimal separator when possible
        """
        rounded = round(float(value), 3)
        formatted = f"{rounded:.3f}".rstrip("0").rstrip(".")
        if not formatted:
            return "0"
        return formatted.replace(".", ",")

    @staticmethod
    def _format_datetime_for_export(value: datetime) -> str:
        """Format datetime using Spanish-friendly presentation."""
        return value.strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _get_created_by_name(transaction: Transaction, user_map: dict[int, User]) -> str:
        """Resolve display name from CREATED transaction event."""
        created_events = [event for event in transaction.events if event.action_type == ActionType.CREATED]
        if not created_events:
            return "-"

        created_event = min(created_events, key=lambda event: event.timestamp)
        creator = user_map.get(created_event.performed_by)
        if not creator:
            return "-"
        return creator.name

    @staticmethod
    def _build_export_filename(now: Optional[datetime] = None) -> str:
        """Build export filename using requested naming convention."""
        current = now or madrid_now()
        return f"operaciones_{current.strftime('%Y%m%d_%H%M')}.csv"

    @staticmethod
    def _build_export_filename_for_format(export_format: str, now: Optional[datetime] = None) -> str:
        """Build export filename with extension based on requested format."""
        current = now or madrid_now()
        extension = "csv" if export_format == "csv" else "pdf"
        return f"operaciones_{current.strftime('%Y%m%d_%H%M')}.{extension}"

    @staticmethod
    def _build_transactions_csv_bytes(transactions: List[Transaction], user_map: dict[int, User]) -> bytes:
        """Build CSV content for transactions export with one row per line."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", lineterminator="\n")
        writer.writerow(TransactionService.CSV_HEADERS)

        for transaction_index, transaction in enumerate(transactions):
            origin_branch = transaction.branch.name if transaction.branch else "-"
            destination_branch = transaction.destination_branch.name if transaction.destination_branch else "-"
            created_by = TransactionService._get_created_by_name(transaction, user_map)
            operation_label = TransactionService.OPERATION_TYPE_LABELS.get(transaction.operation_type, "-")
            status_label = TransactionService.STATUS_LABELS.get(transaction.status, "-")
            event_datetime = transaction.last_event_at or transaction.created_at
            created_at_label = TransactionService._format_datetime_for_export(event_datetime)
            description = (transaction.description or "").strip() or "-"
            group_class = "pdf-group-odd" if transaction_index % 2 == 0 else "pdf-group-even"

            for line in transaction.lines:
                item_name = line.item.name if line.item else "-"
                unit_label = TransactionService.UNIT_SHORT_LABELS.get(line.item.unit, "-") if line.item else "-"
                quantity_label = TransactionService._format_decimal_for_export(line.quantity)

                writer.writerow([
                    transaction.id,
                    operation_label,
                    origin_branch,
                    destination_branch,
                    created_at_label,
                    description,
                    status_label,
                    created_by,
                    item_name,
                    quantity_label,
                    unit_label,
                ])

        return output.getvalue().encode("utf-8-sig")

    @staticmethod
    def _get_pdf_template_and_css_paths() -> tuple[Path, Path]:
        """Resolve PDF HTML template and stylesheet paths."""
        templates_dir = Path(__file__).resolve().parent / "templates"
        template_path = templates_dir / "transactions_export_pdf_template.html"
        css_path = templates_dir / "transactions_pdf_export.css"
        return template_path, css_path

    @staticmethod
    def _prepare_weasyprint_runtime() -> None:
        """Prepare dynamic library lookup paths for WeasyPrint in macOS environments."""
        existing_paths = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        current_parts = [part for part in existing_paths.split(":") if part]

        preferred_parts = ["/opt/homebrew/lib", "/usr/local/lib"]
        merged_parts: List[str] = []
        for path in preferred_parts + current_parts:
            if path and path not in merged_parts:
                merged_parts.append(path)

        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(merged_parts)

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        """Escape PDF text control characters for content stream strings."""
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    @staticmethod
    def _build_fallback_pdf_bytes(lines: List[str]) -> bytes:
        """Build a minimal one-page PDF when WeasyPrint runtime dependencies are unavailable."""
        # A4 landscape media box is 842x595; keep text origin inside visible page area.
        y = 560
        content_rows: List[str] = ["BT", "/F1 10 Tf", "40 560 Td"]
        for index, line in enumerate(lines):
            if index > 0:
                content_rows.append("0 -14 Td")
            content_rows.append(f"({TransactionService._escape_pdf_text(line)}) Tj")
            y -= 14
            if y < 40:
                break
        content_rows.append("ET")
        content_stream = "\n".join(content_rows) + "\n"

        objects: List[str] = [
            "<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content_stream.encode('latin-1'))} >>\nstream\n{content_stream}endstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]

        pdf_chunks: List[bytes] = [b"%PDF-1.4\n"]
        offsets = [0]

        for index, obj in enumerate(objects, start=1):
            offsets.append(sum(len(chunk) for chunk in pdf_chunks))
            pdf_chunks.append(f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1"))

        xref_offset = sum(len(chunk) for chunk in pdf_chunks)
        xref_lines = ["xref", f"0 {len(objects) + 1}", "0000000000 65535 f "]
        xref_lines.extend(f"{offset:010d} 00000 n " for offset in offsets[1:])
        trailer = (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        )

        pdf_chunks.append(("\n".join(xref_lines) + "\n").encode("latin-1"))
        pdf_chunks.append(trailer.encode("latin-1"))
        return b"".join(pdf_chunks)

    @staticmethod
    def _get_order_label(order_by: str, order_desc: bool) -> str:
        """Build Spanish order label for PDF header/footer."""
        if order_by == "total_items":
            if order_desc:
                return "Total de líneas (de mayor a menor)"
            return "Total de líneas (de menor a mayor)"

        if order_desc:
            return "Fecha y hora (más reciente primero)"
        return "Fecha y hora (más antigua primero)"

    @staticmethod
    def _build_pdf_filter_chips_html(
        db: Session,
        branch_id: Optional[int],
        operation_type: Optional[OperationType],
        status_filter: Optional[TransactionStatus],
        performed_by: Optional[int],
        item_id: Optional[int],
        start_date: Optional[date],
        end_date: Optional[date],
        search: Optional[str],
        order_label: str,
    ) -> str:
        """Build only-used filter chips for PDF header."""
        chips: List[str] = []

        if branch_id is not None:
            branch = BranchRepository.get_by_id(db, branch_id)
            branch_name = branch.name if branch else str(branch_id)
            chips.append(f"<li class=\"pdf-filter-chip\">Sede: {html_escape(branch_name)}</li>")

        if operation_type is not None:
            operation_label = TransactionService.OPERATION_TYPE_LABELS.get(operation_type, operation_type.value)
            chips.append(f"<li class=\"pdf-filter-chip\">Tipo: {html_escape(operation_label)}</li>")

        if status_filter is not None:
            status_label = TransactionService.STATUS_LABELS.get(status_filter, status_filter.value)
            chips.append(f"<li class=\"pdf-filter-chip\">Estado: {html_escape(status_label)}</li>")

        if performed_by is not None:
            user = UserRepository.get_by_id(db, performed_by)
            user_name = user.name if user else str(performed_by)
            chips.append(f"<li class=\"pdf-filter-chip\">Realizada por: {html_escape(user_name)}</li>")

        if item_id is not None:
            item = ItemRepository.get_by_id(db, item_id)
            item_name = item.name if item else str(item_id)
            chips.append(f"<li class=\"pdf-filter-chip\">Artículo: {html_escape(item_name)}</li>")

        if start_date is not None:
            chips.append(f"<li class=\"pdf-filter-chip\">Desde: {html_escape(start_date.strftime('%d/%m/%Y'))}</li>")

        if end_date is not None:
            chips.append(f"<li class=\"pdf-filter-chip\">Hasta: {html_escape(end_date.strftime('%d/%m/%Y'))}</li>")

        if search:
            chips.append(f"<li class=\"pdf-filter-chip\">Búsqueda: {html_escape(search.strip())}</li>")

        chips.append(f"<li class=\"pdf-filter-chip\">Ordenación: {html_escape(order_label)}</li>")

        if len(chips) == 1:
            chips.append('<li class="pdf-filter-chip">Sin filtros adicionales</li>')

        return "\n".join(chips)

    @staticmethod
    def _build_pdf_rows_html(transactions: List[Transaction], user_map: dict[int, User]) -> str:
        """Build transaction rows HTML merging transaction-level columns with rowspan."""
        rows: List[str] = []

        for transaction_index, transaction in enumerate(transactions):
            origin_branch = transaction.branch.name if transaction.branch else "-"
            destination_branch = transaction.destination_branch.name if transaction.destination_branch else "-"
            created_by = TransactionService._get_created_by_name(transaction, user_map)
            operation_label = TransactionService.OPERATION_TYPE_LABELS.get(transaction.operation_type, "-")
            status_label = TransactionService.STATUS_LABELS.get(transaction.status, "-")
            event_datetime = transaction.last_event_at or transaction.created_at
            created_at_label = TransactionService._format_datetime_for_export(event_datetime)
            description = transaction.description or ""
            group_class = "pdf-group-odd" if transaction_index % 2 == 0 else "pdf-group-even"

            operation_class_map = {
                OperationType.IN: "type-entrada",
                OperationType.OUT: "type-salida",
                OperationType.TRANSFER: "type-transferencia",
                OperationType.ADJUSTMENT: "type-ajuste",
            }
            status_class_map = {
                TransactionStatus.PENDING: "status-pendiente",
                TransactionStatus.TRANSIT: "status-en-transito",
                TransactionStatus.COMPLETED: "status-completada",
                TransactionStatus.CANCELLED: "status-cancelada",
            }
            operation_class = operation_class_map.get(transaction.operation_type, "")
            status_class = status_class_map.get(transaction.status, "")

            line_count = max(len(transaction.lines), 1)
            value_row_index = (line_count - 1) // 2 if line_count > 1 else 0
            for index in range(line_count):
                line = transaction.lines[index] if index < len(transaction.lines) else None
                line_class = "pdf-line-odd" if index % 2 == 0 else "pdf-line-even"
                merge_variant = "pdf-merged-value" if index == value_row_index else "pdf-merged-empty"
                item_name = line.item.name if line and line.item else "-"
                unit_label = (
                    TransactionService.UNIT_SHORT_LABELS.get(line.item.unit, "-")
                    if line and line.item
                    else "-"
                )
                quantity_label = (
                    TransactionService._format_decimal_for_export(line.quantity)
                    if line
                    else "-"
                )

                row_cells: List[str] = []
                show_merged_value = index == value_row_index
                id_html = str(transaction.id) if show_merged_value else ""
                operation_html = (
                    f'<span class="pdf-badge {html_escape(operation_class)}">{html_escape(operation_label)}</span>'
                    if show_merged_value
                    else ""
                )
                origin_html = html_escape(origin_branch) if show_merged_value else ""
                destination_html = html_escape(destination_branch) if show_merged_value else ""
                created_at_html = html_escape(created_at_label) if show_merged_value else ""
                description_html = (
                    f'<span class="pdf-cell-truncate">{html_escape(description)}</span>'
                    if show_merged_value
                    else ""
                )
                status_html = (
                    f'<span class="pdf-badge {html_escape(status_class)}">{html_escape(status_label)}</span>'
                    if show_merged_value
                    else ""
                )
                created_by_html = html_escape(created_by) if show_merged_value else ""

                # Helper to wrap content: badges go directly in cell, others use merged-content wrapper
                def wrap_merged_cell(content: str) -> str:
                    if not content:
                        return content
                    if '<span class="pdf-badge' in content:
                        return content  # Badges go directly, no wrapper
                    return f'<div class="pdf-cell-merged-content">{content}</div>'

                row_cells.extend(
                    [
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(id_html)}</td>'
                        ),
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(operation_html)}</td>'
                        ),
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(origin_html)}</td>'
                        ),
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(destination_html)}</td>'
                        ),
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(created_at_html)}</td>'
                        ),
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(description_html)}</td>'
                        ),
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(status_html)}</td>'
                        ),
                        (
                            f'<td class="pdf-cell-merged {group_class} {merge_variant}">{wrap_merged_cell(created_by_html)}</td>'
                        ),
                    ]
                )

                row_cells.extend(
                    [
                        f'<td class="pdf-line-cell {line_class}">{html_escape(item_name)}</td>',
                        f'<td class="pdf-col-qty pdf-line-cell {line_class}">{html_escape(quantity_label)}</td>',
                        f'<td class="pdf-line-cell {line_class}">{html_escape(unit_label)}</td>',
                    ]
                )

                row_kind = "pdf-row-start" if index == 0 else "pdf-row-continuation"
                row_tail = "pdf-row-last" if index == line_count - 1 else "pdf-row-not-last"
                rows.append(f'<tr class="pdf-row {row_kind} {row_tail} {group_class}">{"".join(row_cells)}</tr>')

        if not rows:
            rows.append(
                '<tr class="pdf-row pdf-row-empty"><td colspan="11">No hay operaciones para los criterios seleccionados.</td></tr>'
            )

        return "\n".join(rows)

    @staticmethod
    def _build_transactions_pdf_bytes(
        db: Session,
        current_user: User,
        transactions: List[Transaction],
        user_map: dict[int, User],
        branch_id: Optional[int],
        operation_type: Optional[OperationType],
        status_filter: Optional[TransactionStatus],
        performed_by: Optional[int],
        item_id: Optional[int],
        start_date: Optional[date],
        end_date: Optional[date],
        search: Optional[str],
        order_by: str,
        order_desc: bool,
    ) -> bytes:
        """Render HTML template and transform it to PDF using WeasyPrint."""
        template_path, css_path = TransactionService._get_pdf_template_and_css_paths()
        if not template_path.exists() or not css_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF_TEMPLATE_NOT_AVAILABLE"
            )

        company = CompanyRepository.get_by_id(db, current_user.company_id)
        company_name = company.name if company else "-"
        company_nif = company.nif if company and company.nif else "-"
        company_email = company.email if company else "-"

        total_transactions = len(transactions)
        total_lines = sum(len(transaction.lines) for transaction in transactions)
        exported_at = madrid_now().strftime("%d/%m/%Y %H:%M")

        order_label = TransactionService._get_order_label(order_by, order_desc)
        filters_html = TransactionService._build_pdf_filter_chips_html(
            db=db,
            branch_id=branch_id,
            operation_type=operation_type,
            status_filter=status_filter,
            performed_by=performed_by,
            item_id=item_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
            order_label=order_label,
        )
        rows_html = TransactionService._build_pdf_rows_html(transactions, user_map)

        html_template = template_path.read_text(encoding="utf-8")
        html_content = (
            html_template
            .replace("{{company_name}}", html_escape(company_name))
            .replace("{{company_nif}}", html_escape(company_nif))
            .replace("{{company_email}}", html_escape(company_email))
            .replace("{{user_name}}", html_escape(current_user.name))
            .replace("{{exported_at}}", html_escape(exported_at))
            .replace("{{total_transactions}}", str(total_transactions))
            .replace("{{total_lines}}", str(total_lines))
            .replace("{{filters_html}}", filters_html)
            .replace("{{rows_html}}", rows_html)
        )

        try:
            TransactionService._prepare_weasyprint_runtime()
            from weasyprint import HTML

            return HTML(string=html_content, base_url=str(template_path.parent)).write_pdf(stylesheets=[str(css_path)])
        except Exception:
            fallback_lines = [
                "Exportacion de operaciones",
                f"Empresa: {company_name}",
                f"Usuario: {current_user.name}",
                f"Fecha y hora: {exported_at}",
                f"Total operaciones: {total_transactions}",
                f"Total lineas: {total_lines}",
                "Renderizado simplificado por dependencias de WeasyPrint no disponibles.",
            ]
            return TransactionService._build_fallback_pdf_bytes(fallback_lines)

    @staticmethod
    def _complete_transaction_in_place(
        db: Session,
        transaction: Transaction,
        performed_by: int,
        current_user: User
    ) -> None:
        """
        Advance transaction completion in place.
        - IN/OUT: PENDING -> COMPLETED
        - TRANSFER: PENDING -> TRANSIT -> COMPLETED
        """
        if transaction.operation_type == OperationType.TRANSFER:
            if transaction.status == TransactionStatus.PENDING:
                TransactionService._send_transfer_in_place(
                    db=db,
                    transaction=transaction,
                    performed_by=performed_by
                )
                return

            if transaction.status == TransactionStatus.TRANSIT:
                TransactionService._validate_transfer_terminal_completion_permission(
                    db=db,
                    transaction=transaction,
                    current_user=current_user
                )
                TransactionService._receive_transfer_in_place(
                    db=db,
                    transaction=transaction,
                    performed_by=performed_by
                )
                return

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSFER_NOT_COMPLETABLE"
            )

        if transaction.status != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSACTION_NOT_COMPLETABLE"
            )

        if transaction.operation_type == OperationType.OUT:
            for line in transaction.lines:
                current_stock = StockMovementRepository.get_stock_by_item_and_branch(
                    db, line.item_id, transaction.branch_id
                )

                if current_stock - line.quantity < 0:
                    item = ItemRepository.get_by_id(db, line.item_id)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"INSUFFICIENT_STOCK_FOR_ITEM_{item.sku}"
                    )

        transaction.status = TransactionStatus.COMPLETED
        TransactionRepository.update(db, transaction)

        for line in transaction.lines:
            if transaction.operation_type == OperationType.ADJUSTMENT:
                quantity = line.quantity
            elif transaction.operation_type == OperationType.IN:
                quantity = line.quantity
            else:
                quantity = -line.quantity

            stock_movement = StockMovement(
                quantity=quantity,
                movement_type=MovementType(transaction.operation_type.value),
                created_at=madrid_now(),
                item_id=line.item_id,
                branch_id=transaction.branch_id,
                transaction_id=transaction.id
            )
            db.add(stock_movement)

        TransactionService._register_transaction_event(
            db=db,
            transaction=transaction,
            action_type=ActionType.COMPLETED,
            performed_by=performed_by,
        )

    @staticmethod
    def _register_transaction_event(
        db: Session,
        transaction: Transaction,
        action_type: ActionType,
        performed_by: int,
        event_metadata: Optional[dict] = None,
    ) -> TransactionEvent:
        """Create a transaction event and sync transactions.last_event_at."""
        event_timestamp = madrid_now()
        event = TransactionEvent(
            action_type=action_type,
            timestamp=event_timestamp,
            transaction_id=transaction.id,
            performed_by=performed_by,
            event_metadata=event_metadata,
        )

        transaction.last_event_at = event_timestamp
        TransactionRepository.update(db, transaction)
        return TransactionRepository.create_event(db, event)

    @staticmethod
    def _send_transfer_in_place(
        db: Session,
        transaction: Transaction,
        performed_by: int
    ) -> None:
        """
        Move TRANSFER from PENDING to TRANSIT and register SENT.
        """
        if transaction.destination_branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSFER_DESTINATION_REQUIRED"
            )

        for line in transaction.lines:
            current_stock = StockMovementRepository.get_stock_by_item_and_branch(
                db, line.item_id, transaction.branch_id
            )

            if current_stock - line.quantity < 0:
                item = ItemRepository.get_by_id(db, line.item_id)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"INSUFFICIENT_STOCK_FOR_ITEM_{item.sku}"
                )

        transaction.status = TransactionStatus.TRANSIT
        TransactionRepository.update(db, transaction)

        for line in transaction.lines:
            stock_movement = StockMovement(
                quantity=-line.quantity,
                movement_type=MovementType.TRANSFER,
                created_at=madrid_now(),
                item_id=line.item_id,
                branch_id=transaction.branch_id,
                transaction_id=transaction.id
            )
            db.add(stock_movement)

        TransactionService._register_transaction_event(
            db=db,
            transaction=transaction,
            action_type=ActionType.SENT,
            performed_by=performed_by,
        )

    @staticmethod
    def _receive_transfer_in_place(
        db: Session,
        transaction: Transaction,
        performed_by: int
    ) -> None:
        """
        Move TRANSFER from TRANSIT to COMPLETED.
        """
        destination_branch_id = transaction.destination_branch_id
        if destination_branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSFER_DESTINATION_REQUIRED"
            )

        transaction.status = TransactionStatus.COMPLETED
        TransactionRepository.update(db, transaction)

        for line in transaction.lines:
            stock_movement = StockMovement(
                quantity=line.quantity,
                movement_type=MovementType.TRANSFER,
                created_at=madrid_now(),
                item_id=line.item_id,
                branch_id=destination_branch_id,
                transaction_id=transaction.id
            )
            db.add(stock_movement)

        TransactionService._register_transaction_event(
            db=db,
            transaction=transaction,
            action_type=ActionType.COMPLETED,
            performed_by=performed_by,
        )

    @staticmethod
    def _validate_user_can_access_branch(current_user: User, branch_id: int, db: Session) -> None:
        """
        Validate that user can access a specific branch.
        - Branch must exist and be active
        - Branch must belong to user's company
        - If user has assigned branch, can only access that branch
        """
        branch = BranchRepository.get_by_id(db, branch_id)
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BRANCH_NOT_FOUND"
            )
        if not branch.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BRANCH_NOT_FOUND"
            )
        
        if branch.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BRANCH_NOT_FOUND"
            )
        
        # If user has assigned branch, can only access that branch
        if current_user.branch_id and current_user.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BRANCH_ACCESS_DENIED"
            )

    @staticmethod
    def _validate_user_can_access_transaction(
        current_user: User, transaction: Transaction, db: Session
    ) -> None:
        """
        Validate that user can access a specific transaction.
        - Access via origin branch, OR
        - For TRANSFER type, access via destination branch.
        """
        try:
            TransactionService._validate_user_can_access_branch(
                current_user, transaction.branch_id, db
            )
            return
        except HTTPException:
            pass

        if transaction.operation_type == OperationType.TRANSFER and transaction.destination_branch_id:
            try:
                TransactionService._validate_user_can_access_branch(
                    current_user, transaction.destination_branch_id, db
                )
                return
            except HTTPException:
                pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="BRANCH_ACCESS_DENIED"
        )

    @staticmethod
    def _validate_items_belong_to_company(db: Session, item_ids: List[int], company_id: int) -> List[Item]:
        """
        Validate that all items exist, are active, and belong to the company.
        Returns list of Item objects.
        """
        items = []
        for item_id in item_ids:
            item = ItemRepository.get_by_id(db, item_id)
            if not item or not item.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ITEM_NOT_FOUND"
                )
            
            if item.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ITEM_NOT_FOUND"
                )
            
            items.append(item)
        
        return items

    @staticmethod
    def _validate_branch_for_create(current_user: User, branch_id: int, db: Session) -> None:
        """
        Validate branch for transaction creation with explicit inactive error.
        """
        branch = BranchRepository.get_by_id(db, branch_id)
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BRANCH_NOT_FOUND"
            )

        if not branch.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="BRANCH_INACTIVE"
            )

        if branch.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BRANCH_NOT_FOUND"
            )

        if current_user.branch_id and current_user.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BRANCH_ACCESS_DENIED"
            )

    @staticmethod
    def _validate_items_for_create(db: Session, item_ids: List[int], company_id: int) -> List[Item]:
        """
        Validate items for transaction creation with explicit inactive error.
        """
        items = []
        for item_id in item_ids:
            item = ItemRepository.get_by_id(db, item_id)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="ITEM_NOT_FOUND"
                )

            if not item.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ITEM_INACTIVE"
                )

            if item.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ITEM_NOT_FOUND"
                )

            items.append(item)

        return items

    @staticmethod
    def _validate_quantities_for_units(lines_data: List, items: List[Item]) -> None:
        """
        Validate that quantities are integers for units: ud, box, pack.
        """
        for idx, line_data in enumerate(lines_data):
            item = items[idx]
            if item.unit in (Unit.UNIT, Unit.BOX, Unit.PACK):
                if line_data.quantity % 1 != 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"QUANTITY_MUST_BE_INTEGER_FOR_UNIT_{item.unit.value}"
                    )

    @staticmethod
    def _validate_transfer_creation_permission(current_user: User) -> None:
        """Only users without branch association can create transfers."""
        if current_user.branch_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="TRANSFER_CREATION_REQUIRES_CENTRAL_USER"
            )

    @staticmethod
    def _validate_adjustment_creation_permission(current_user: User) -> None:
        """Only ADMIN and MANAGER users can create adjustments."""
        if current_user.role not in (Role.ADMIN, Role.MANAGER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

    @staticmethod
    def _validate_line_quantities_for_operation(
        operation_type: OperationType,
        lines_data: List
    ) -> None:
        """
        Validate quantity sign constraints by operation type.
        - ADJUSTMENT: positive or negative values allowed (zero not allowed)
        - IN/OUT/TRANSFER: only positive values allowed
        """
        for line_data in lines_data:
            if operation_type == OperationType.ADJUSTMENT:
                if line_data.quantity == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ADJUSTMENT_QUANTITY_CANNOT_BE_ZERO"
                    )
            else:
                if line_data.quantity <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="QUANTITY_MUST_BE_POSITIVE"
                    )

    @staticmethod
    def _validate_adjustment_payload(transaction_data: TransactionCreate) -> None:
        """
        Validate ADJUSTMENT-specific payload requirements.
        - Description is mandatory
        - auto_complete must be true
        """
        if transaction_data.auto_complete is not True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ADJUSTMENT_REQUIRES_AUTO_COMPLETE"
            )

        if transaction_data.description is None or not transaction_data.description.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ADJUSTMENT_DESCRIPTION_REQUIRED"
            )

    @staticmethod
    def _validate_transfer_terminal_completion_permission(
        db: Session,
        transaction: Transaction,
        current_user: User
    ) -> None:
        """
        Final transfer completion requires destination branch access
        or a user without branch association.
        """
        destination_branch_id = transaction.destination_branch_id
        if destination_branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSFER_DESTINATION_REQUIRED"
            )

        TransactionService._validate_user_can_access_branch(
            current_user,
            destination_branch_id,
            db
        )

    @staticmethod
    def _validate_transfer_send_permission(
        db: Session,
        transaction: Transaction,
        current_user: User
    ) -> None:
        """
        Sending transfer (PENDING -> TRANSIT) requires origin branch access
        or a user without branch association.
        """
        TransactionService._validate_user_can_access_branch(
            current_user,
            transaction.branch_id,
            db
        )

    @staticmethod
    def _validate_transaction_cancelable(transaction: Transaction) -> None:
        """Validate that transaction can be canceled (PENDING or TRANSIT)."""
        if transaction.status not in (TransactionStatus.PENDING, TransactionStatus.TRANSIT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSACTION_NOT_CANCELABLE"
            )

    @staticmethod
    def _validate_transfer_cancel_permission(
        db: Session,
        transaction: Transaction,
        current_user: User
    ) -> None:
        """
        Cancel permissions for transfers by status:
        - PENDING: origin branch users or users without branch association.
        - TRANSIT: destination branch users or users without branch association.
        """
        if transaction.status == TransactionStatus.PENDING:
            TransactionService._validate_transfer_send_permission(
                db=db,
                transaction=transaction,
                current_user=current_user
            )
            return

        if transaction.status == TransactionStatus.TRANSIT:
            TransactionService._validate_transfer_terminal_completion_permission(
                db=db,
                transaction=transaction,
                current_user=current_user
            )
            return

    @staticmethod
    def _validate_transaction_editable(transaction: Transaction) -> None:
        """
        Validate that transaction can be edited (status must be PENDING).
        """
        if transaction.status != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSACTION_NOT_EDITABLE"
            )

    @staticmethod
    def _validate_update_permission(
        db: Session,
        transaction: Transaction,
        current_user: User
    ) -> None:
        """
        Validate update permissions for PUT /transactions/{transaction_id}.

        Rules:
        - PENDING: users from origin branch and users without branch association.
        - TRANSIT/CANCELLED/COMPLETED: no user can update.
        """
        if transaction.status != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="TRANSACTION_UPDATE_FORBIDDEN"
            )

        TransactionService._validate_user_can_access_branch(
            current_user,
            transaction.branch_id,
            db
        )

    @staticmethod
    def _validate_document_permission(db: Session, transaction: Transaction, current_user: User) -> None:
        """
        Validate document upload/delete permissions.

        Rules:
        - PENDING:
          - Users from origin branch
          - Users without branch association
        - TRANSIT:
          - Users from origin branch
          - Users from destination branch
          - Users without branch association
        - COMPLETED/CANCELLED:
          - MANAGER in origin/destination branch
          - MANAGER/ADMIN without branch association
          - EMPLOYEE in origin branch if created CREATED/SENT/COMPLETED/CANCELLED event
          - EMPLOYEE in destination branch if created COMPLETED/CANCELLED event
        """
        if transaction.status == TransactionStatus.PENDING:
            try:
                TransactionService._validate_user_can_access_branch(
                    current_user, transaction.branch_id, db
                )
                return
            except HTTPException:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="DOCUMENT_OPERATION_FORBIDDEN"
                )

        if transaction.status == TransactionStatus.TRANSIT:
            try:
                TransactionService._validate_user_can_access_branch(
                    current_user, transaction.branch_id, db
                )
                return
            except HTTPException:
                pass

            if transaction.destination_branch_id is not None:
                try:
                    TransactionService._validate_user_can_access_branch(
                        current_user, transaction.destination_branch_id, db
                    )
                    return
                except HTTPException:
                    pass

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="DOCUMENT_OPERATION_FORBIDDEN"
            )

        if transaction.status in (TransactionStatus.COMPLETED, TransactionStatus.CANCELLED):
            if current_user.role in (Role.ADMIN, Role.MANAGER):
                if current_user.branch_id is None:
                    return

                if current_user.role == Role.MANAGER and current_user.branch_id in (
                    transaction.branch_id,
                    transaction.destination_branch_id,
                ):
                    return

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="DOCUMENT_OPERATION_FORBIDDEN"
                )

            if current_user.role == Role.EMPLOYEE:
                if current_user.branch_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="DOCUMENT_OPERATION_FORBIDDEN"
                    )

                allowed_actions = set()
                if current_user.branch_id == transaction.branch_id:
                    allowed_actions.update({
                        ActionType.CREATED,
                        ActionType.SENT,
                        ActionType.COMPLETED,
                        ActionType.CANCELLED,
                    })

                if (
                    transaction.destination_branch_id is not None
                    and current_user.branch_id == transaction.destination_branch_id
                ):
                    allowed_actions.update({
                        ActionType.COMPLETED,
                        ActionType.CANCELLED,
                    })

                if not allowed_actions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="DOCUMENT_OPERATION_FORBIDDEN"
                    )

                for event in transaction.events:
                    if event.performed_by == current_user.id and event.action_type in allowed_actions:
                        return

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="DOCUMENT_OPERATION_FORBIDDEN"
                )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DOCUMENT_OPERATION_FORBIDDEN"
        )

    @staticmethod
    def create_transaction(
        db: Session,
        transaction_data: TransactionCreate,
        current_user: User
    ) -> Transaction:
        """
        Create a new transaction.
        
        Validations:
        - User must be active
        - Operation type supports IN, OUT, TRANSFER and ADJUSTMENT
        - TRANSFER can only be created by users without associated branch
        - ADJUSTMENT can only be created by ADMIN and MANAGER users
        - Branch must be active and belong to user's company
        - If user has branch assigned, can only create in that branch
        - All items must be active and belong to same company
        - Quantities must be integers for units: ud, box, pack
        
        Actions:
        - Create transaction record
        - Create transaction lines
        - Create CREATED event
        """
        UserService.validate_user_active(current_user)

        if transaction_data.operation_type == OperationType.TRANSFER:
            TransactionService._validate_transfer_creation_permission(current_user)
        elif transaction_data.operation_type == OperationType.ADJUSTMENT:
            TransactionService._validate_adjustment_creation_permission(current_user)
            TransactionService._validate_adjustment_payload(transaction_data)
        
        # Validate branch access
        TransactionService._validate_branch_for_create(
            current_user, transaction_data.branch_id, db
        )

        if transaction_data.operation_type == OperationType.TRANSFER:
            destination_branch_id = transaction_data.destination_branch_id
            if destination_branch_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="TRANSFER_DESTINATION_REQUIRED"
                )

            if transaction_data.branch_id == destination_branch_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="TRANSFER_BRANCHES_MUST_BE_DIFFERENT"
                )

            TransactionService._validate_user_can_access_branch(
                current_user,
                destination_branch_id,
                db
            )
        
        # Validate items
        item_ids = [line.item_id for line in transaction_data.lines]
        items = TransactionService._validate_items_for_create(
            db, item_ids, current_user.company_id
        )
        
        # Validate quantities for specific units
        TransactionService._validate_quantities_for_units(transaction_data.lines, items)
        TransactionService._validate_line_quantities_for_operation(
            transaction_data.operation_type,
            transaction_data.lines
        )
        
        # Create transaction
        transaction = Transaction(
            operation_type=transaction_data.operation_type,
            status=TransactionStatus.PENDING,
            description=transaction_data.description,
            branch_id=transaction_data.branch_id,
            destination_branch_id=transaction_data.destination_branch_id,
            created_at=madrid_now()
        )
        TransactionRepository.create(db, transaction)
        
        # Create transaction lines
        for line_data in transaction_data.lines:
            line = TransactionLine(
                quantity=line_data.quantity,
                item_id=line_data.item_id,
                transaction_id=transaction.id
            )
            TransactionRepository.create_line(db, line)
        
        # Create CREATED event
        TransactionService._register_transaction_event(
            db=db,
            transaction=transaction,
            action_type=ActionType.CREATED,
            performed_by=current_user.id,
        )

        if transaction_data.auto_complete:
            TransactionService._complete_transaction_in_place(
                db=db,
                transaction=transaction,
                performed_by=current_user.id,
                current_user=current_user
            )
        
        TransactionRepository.commit(db)
        
        # Refresh to get lines and events
        db.refresh(transaction)
        return transaction

    @staticmethod
    def update_transaction(
        db: Session,
        transaction_id: int,
        transaction_data: TransactionUpdateRequest,
        current_user: User,
    ) -> Transaction:
        """
        Update a transaction (only if status is PENDING).
        
        Validations:
        - User must be active
        - Transaction must exist and belong to user's accessible branches
        - Transaction must be in PENDING status
        - If items are updated, same validations as create
        
        Actions:
        - Update transaction fields
        - Update transaction lines if provided
        - Create EDITED event with metadata showing old and new values
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )

        # Validate update permissions by status and branch scope
        TransactionService._validate_update_permission(
            db=db,
            transaction=transaction,
            current_user=current_user
        )
        
        # Track changes for metadata
        changes = {}
        
        # Update description
        if transaction_data.description is not None:
            if transaction.description != transaction_data.description:
                changes["description"] = {
                    "previous": transaction.description,
                    "new": transaction_data.description
                }
            transaction.description = transaction_data.description
        
        # Update lines if provided
        if transaction_data.lines is not None:
            # Validate items
            item_ids = [line.item_id for line in transaction_data.lines]
            items = TransactionService._validate_items_for_create(
                db, item_ids, current_user.company_id
            )
            
            # Validate quantities
            TransactionService._validate_quantities_for_units(transaction_data.lines, items)
            TransactionService._validate_line_quantities_for_operation(
                transaction.operation_type,
                transaction_data.lines
            )
            
            # Snapshot old lines before deleting
            old_snapshot = [
                {"item_id": l.item_id, "quantity": float(l.quantity)}
                for l in transaction.lines
            ]
            
            # Delete old lines
            for old_line in transaction.lines:
                db.delete(old_line)
            
            # Create new lines
            for line_data in transaction_data.lines:
                line = TransactionLine(
                    quantity=line_data.quantity,
                    item_id=line_data.item_id,
                    transaction_id=transaction.id
                )
                TransactionRepository.create_line(db, line)
            
            new_snapshot = [
                {"item_id": l.item_id, "quantity": float(l.quantity)}
                for l in transaction_data.lines
            ]
            changes["lines"] = {
                "previous": old_snapshot,
                "new": new_snapshot
            }
        
        TransactionRepository.update(db, transaction)
        
        # Create EDITED event only if there were actual changes
        if changes:
            TransactionService._register_transaction_event(
                db=db,
                transaction=transaction,
                action_type=ActionType.EDITED,
                performed_by=current_user.id,
                event_metadata=changes,
            )

        if transaction_data.auto_complete:
            db.flush()
            db.refresh(transaction)
            TransactionService._complete_transaction_in_place(
                db=db,
                transaction=transaction,
                performed_by=current_user.id,
                current_user=current_user
            )
        
        TransactionRepository.commit(db)
        
        db.refresh(transaction)
        return transaction

    @staticmethod
    def cancel_transaction(
        db: Session,
        transaction_id: int,
        current_user: User,
        cancel_reason: Optional[str] = None
    ) -> Transaction:
        """
        Cancel a transaction.
        
        Validations:
        - User must be active
        - Transaction must exist and belong to user's accessible branches
        - Transaction must be in PENDING or TRANSIT status
        
        Actions:
        - Update status to CANCELLED
        - Create CANCELLED event with optional reason in metadata
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate cancelable
        TransactionService._validate_transaction_cancelable(transaction)

        # Validate access
        if transaction.operation_type == OperationType.TRANSFER:
            TransactionService._validate_transfer_cancel_permission(
                db=db,
                transaction=transaction,
                current_user=current_user
            )
        else:
            TransactionService._validate_user_can_access_branch(
                current_user, transaction.branch_id, db
            )
        
        # Update status
        transaction.status = TransactionStatus.CANCELLED
        TransactionRepository.update(db, transaction)
        
        # Create CANCELLED event
        metadata = None
        if cancel_reason:
            metadata = {"reason": cancel_reason}
        
        TransactionService._register_transaction_event(
            db=db,
            transaction=transaction,
            action_type=ActionType.CANCELLED,
            performed_by=current_user.id,
            event_metadata=metadata,
        )
        
        TransactionRepository.commit(db)
        
        db.refresh(transaction)
        return transaction

    @staticmethod
    def complete_transaction(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> Transaction:
        """
        Complete a transaction.
        
        Validations:
        - User must be active
        - Transaction must exist and belong to user's accessible branches
        - IN/OUT transactions must be in PENDING status
        - TRANSFER transactions can be completed from PENDING or TRANSIT
        - For OUT operations, verify stock won't go negative
        
        Actions:
        - Update status to COMPLETED
        - Create stock_movements for each line (IN = positive, OUT = negative)
        - Create COMPLETED event
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction with lines
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        if transaction.operation_type == OperationType.TRANSFER and transaction.status == TransactionStatus.TRANSIT:
            TransactionService._validate_transfer_terminal_completion_permission(
                db=db,
                transaction=transaction,
                current_user=current_user
            )
        elif transaction.operation_type == OperationType.TRANSFER and transaction.status == TransactionStatus.PENDING:
            TransactionService._validate_transfer_send_permission(
                db=db,
                transaction=transaction,
                current_user=current_user
            )
        else:
            TransactionService._validate_user_can_access_branch(
                current_user, transaction.branch_id, db
            )

        if transaction.operation_type == OperationType.TRANSFER:
            if transaction.status not in (TransactionStatus.PENDING, TransactionStatus.TRANSIT):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="TRANSFER_NOT_COMPLETABLE"
                )
        else:
            TransactionService._validate_transaction_editable(transaction)
        
        TransactionService._complete_transaction_in_place(
            db=db,
            transaction=transaction,
            performed_by=current_user.id,
            current_user=current_user
        )
        
        TransactionRepository.commit(db)
        
        db.refresh(transaction)
        return transaction

    @staticmethod
    def get_transaction(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> Transaction:
        """
        Get a transaction by ID.
        User can only view transactions from their accessible branches.
        """
        UserService.validate_user_active(current_user)
        
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_transaction(
            current_user, transaction, db
        )
        
        return transaction

    @staticmethod
    def list_transactions(
        db: Session,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        branch_id: Optional[int] = None,
        operation_type: Optional[OperationType] = None,
        status: Optional[TransactionStatus] = None,
        performed_by: Optional[int] = None,
        item_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        order_by: str = "last_event_at",
        order_desc: bool = True
    ) -> Tuple[List[Transaction], int]:
        """
        List transactions for the user's company with filters.
        If user has assigned branch, only show transactions from that branch.
        """
        UserService.validate_user_active(current_user)
        
        # If user has assigned branch, override branch_id filter
        if current_user.branch_id:
            branch_id = current_user.branch_id
        
        transactions, total = TransactionRepository.list_transactions(
            db=db,
            company_id=current_user.company_id,
            page=page,
            page_size=page_size,
            branch_id=branch_id,
            operation_type=operation_type,
            status=status,
            performed_by=performed_by,
            item_id=item_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
            order_by=order_by,
            order_desc=order_desc
        )
        
        return transactions, total

    @staticmethod
    def export_transactions_file(
        db: Session,
        current_user: User,
        export_format: str,
        branch_id: Optional[int] = None,
        operation_type: Optional[OperationType] = None,
        status_filter: Optional[TransactionStatus] = None,
        performed_by: Optional[int] = None,
        item_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        order_by: str = "last_event_at",
        order_desc: bool = True
    ) -> tuple[bytes, str, str]:
        """
        Export transactions as file bytes, filename, and media type.
        """
        UserService.validate_user_active(current_user)
        TransactionService._validate_export_permission(current_user)

        if export_format not in ("csv", "pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="EXPORT_FORMAT_NOT_SUPPORTED"
            )

        if current_user.branch_id:
            branch_id = current_user.branch_id

        TransactionService._validate_export_filter_entities(
            db=db,
            company_id=current_user.company_id,
            branch_id=branch_id,
            performed_by=performed_by,
            item_id=item_id,
        )

        transactions = TransactionRepository.list_transactions_for_export(
            db=db,
            company_id=current_user.company_id,
            branch_id=branch_id,
            operation_type=operation_type,
            status=status_filter,
            performed_by=performed_by,
            item_id=item_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
            order_by=order_by,
            order_desc=order_desc,
        )

        # Count total lines to validate export limit by format
        total_lines = sum(len(transaction.lines) for transaction in transactions)
        max_lines = (
            TransactionService.EXPORT_MAX_LINES_CSV
            if export_format == "csv"
            else TransactionService.EXPORT_MAX_LINES_PDF
        )
        if total_lines > max_lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"EXPORT_EXCEEDS_LIMIT_{max_lines}"
            )

        created_by_ids = {
            event.performed_by
            for transaction in transactions
            for event in transaction.events
            if event.action_type == ActionType.CREATED
        }

        users = [UserRepository.get_by_id(db, user_id) for user_id in created_by_ids]
        user_map = {user.id: user for user in users if user is not None}

        if export_format == "csv":
            file_bytes = TransactionService._build_transactions_csv_bytes(transactions, user_map)
            media_type = "text/csv; charset=utf-8"
        else:
            file_bytes = TransactionService._build_transactions_pdf_bytes(
                db=db,
                current_user=current_user,
                transactions=transactions,
                user_map=user_map,
                branch_id=branch_id,
                operation_type=operation_type,
                status_filter=status_filter,
                performed_by=performed_by,
                item_id=item_id,
                start_date=start_date,
                end_date=end_date,
                search=search,
                order_by=order_by,
                order_desc=order_desc,
            )
            media_type = "application/pdf"

        filename = TransactionService._build_export_filename_for_format(export_format)
        return file_bytes, filename, media_type

    @staticmethod
    def upload_document(
        db: Session,
        transaction_id: int,
        current_user: User,
        document_file: bytes,
        document_filename: str
    ) -> Transaction:
        """
        Upload a document to a transaction.
        Allowed for any transaction status.
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate document operation permissions
        TransactionService._validate_document_permission(db, transaction, current_user)
        
        # Delete old document if exists
        if transaction.document_url:
            TransactionDocumentHandler.delete_document(transaction.document_url)
        
        # Save new document
        document_url = TransactionDocumentHandler.save_document(
            document_file, document_filename, current_user.company_id
        )
        
        transaction.document_url = document_url
        transaction.document_name = document_filename
        TransactionRepository.update(db, transaction)
        TransactionRepository.commit(db)
        
        return transaction

    @staticmethod
    def get_document(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> tuple[Path, str, str]:
        """
        Get the document file path and metadata for a transaction.
        Similar to ItemService.get_item_image.
        """
        UserService.validate_user_active(current_user)
        
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_transaction(
            current_user, transaction, db
        )
        
        if not transaction.document_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DOCUMENT_NOT_FOUND"
            )
        
        file_path = TransactionDocumentHandler.get_absolute_path(transaction.document_url)
        if not file_path or not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DOCUMENT_NOT_FOUND"
            )
        
        import mimetypes
        media_type, _ = mimetypes.guess_type(str(file_path))
        if not media_type:
            media_type = "application/octet-stream"

        if transaction.document_name:
            download_name = transaction.document_name
        else:
            extension = file_path.suffix.lower()
            download_name = f"unknown{extension}" if extension else "unknown"

        return file_path, media_type, download_name

    @staticmethod
    def delete_document(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> Transaction:
        """
        Delete the document from a transaction.
        Allowed for any transaction status.
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate document operation permissions
        TransactionService._validate_document_permission(db, transaction, current_user)
        
        if transaction.document_url:
            TransactionDocumentHandler.delete_document(transaction.document_url)
            transaction.document_url = None
            transaction.document_name = None
            TransactionRepository.update(db, transaction)
            TransactionRepository.commit(db)
        
        return transaction
