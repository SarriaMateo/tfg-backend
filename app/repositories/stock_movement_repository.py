from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from decimal import Decimal
from typing import Dict, Tuple
from app.db.models.stock_movement import StockMovement


class StockMovementRepository:

    @staticmethod
    def get_by_id(db: Session, stock_movement_id: int) -> StockMovement:
        return db.query(StockMovement).filter(StockMovement.id == stock_movement_id).first()

    @staticmethod
    def create(db: Session, stock_movement: StockMovement) -> StockMovement:
        db.add(stock_movement)
        db.flush()
        return stock_movement

    @staticmethod
    def get_stock_by_item_and_branch(
        db: Session, 
        item_id: int, 
        branch_id: int
    ) -> Decimal:
        """
        Calculate stock for a specific item at a specific branch.
        Stock = SUM(quantity) of all stock movements for that item-branch combination.
        Returns 0 if no movements exist.
        """
        result = db.query(
            func.sum(StockMovement.quantity)
        ).filter(
            and_(
                StockMovement.item_id == item_id,
                StockMovement.branch_id == branch_id
            )
        ).scalar()
        
        return result if result is not None else Decimal("0.000")

    @staticmethod
    def get_stock_by_items_and_branches(
        db: Session,
        item_ids: list[int],
        branch_ids: list[int]
    ) -> Dict[Tuple[int, int], Decimal]:
        """
        Calculate stock for multiple items across multiple branches.
        Returns a dictionary with (item_id, branch_id) as key and stock as value.
        """
        if not item_ids or not branch_ids:
            return {}

        results = db.query(
            StockMovement.item_id,
            StockMovement.branch_id,
            func.sum(StockMovement.quantity).label('total_stock')
        ).filter(
            and_(
                StockMovement.item_id.in_(item_ids),
                StockMovement.branch_id.in_(branch_ids)
            )
        ).group_by(
            StockMovement.item_id,
            StockMovement.branch_id
        ).all()

        stock_dict = {}
        for item_id, branch_id, stock in results:
            stock_dict[(item_id, branch_id)] = stock if stock is not None else Decimal("0.000")

        return stock_dict

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()
