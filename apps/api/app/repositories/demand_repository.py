from __future__ import annotations

from collections import defaultdict
import datetime as dt
from typing import Any

from app.data.dataset import ShopFlowDataset
from app.data.generator import generate_shopflow_dataset
from app.domain.demand import DemandRecord


class DemandRepository:
    """In-memory data access layer for ShopFlow historical demand records.

    Provides reliable, deterministic read access and historical aggregations
    for observed demand backed by the ShopFlow synthetic data engine.
    """

    def __init__(self, dataset: ShopFlowDataset | None = None) -> None:
        """Initializes the repository with a dataset or defaults to canonical seed 42."""
        if dataset is None:
            self._dataset = generate_shopflow_dataset(seed=42)
        else:
            self._dataset = dataset

    @property
    def dataset(self) -> ShopFlowDataset:
        """Returns the underlying ShopFlow dataset container."""
        return self._dataset

    def list_all(
        self,
        product_id: str | None = None,
        warehouse_id: str | None = None,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> list[DemandRecord]:
        """Retrieves all historical demand records with optional filtering."""
        records = self._dataset.demand

        if product_id is not None:
            records = [d for d in records if d.product_id == product_id]
        if warehouse_id is not None:
            records = [d for d in records if d.warehouse_id == warehouse_id]
        if start_date is not None:
            records = [d for d in records if d.date >= start_date]
        if end_date is not None:
            records = [d for d in records if d.date <= end_date]

        return list(records)

    def get_by_id(self, demand_id: str) -> DemandRecord | None:
        """Retrieves a single demand record by its unique ID."""
        for record in self._dataset.demand:
            if record.id == demand_id:
                return record
        return None

    def get_by_product_id(
        self,
        product_id: str,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> list[DemandRecord]:
        """Retrieves all historical demand records for a specific product."""
        records = [d for d in self._dataset.demand if d.product_id == product_id]
        if start_date is not None:
            records = [d for d in records if d.date >= start_date]
        if end_date is not None:
            records = [d for d in records if d.date <= end_date]
        return list(records)

    def get_by_warehouse_id(
        self,
        warehouse_id: str,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> list[DemandRecord]:
        """Retrieves all historical demand records for a specific warehouse."""
        records = [d for d in self._dataset.demand if d.warehouse_id == warehouse_id]
        if start_date is not None:
            records = [d for d in records if d.date >= start_date]
        if end_date is not None:
            records = [d for d in records if d.date <= end_date]
        return list(records)

    def get_by_product_and_warehouse(
        self,
        product_id: str,
        warehouse_id: str,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> list[DemandRecord]:
        """Retrieves historical demand records for a specific product at a specific warehouse."""
        records = [
            d
            for d in self._dataset.demand
            if d.product_id == product_id and d.warehouse_id == warehouse_id
        ]
        if start_date is not None:
            records = [d for d in records if d.date >= start_date]
        if end_date is not None:
            records = [d for d in records if d.date <= end_date]
        return list(records)

    def get_by_date_range(
        self,
        start_date: dt.date,
        end_date: dt.date,
        product_id: str | None = None,
        warehouse_id: str | None = None,
    ) -> list[DemandRecord]:
        """Retrieves historical demand records within a specific inclusive date range."""
        return self.list_all(
            product_id=product_id,
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date,
        )

    def product_exists(self, product_id: str) -> bool:
        """Checks if a product exists in the underlying catalog."""
        return self._dataset.get_product(product_id) is not None

    def warehouse_exists(self, warehouse_id: str) -> bool:
        """Checks if a warehouse exists in the underlying dataset."""
        return self._dataset.get_warehouse(warehouse_id) is not None

    def get_product_demand_trend(
        self,
        product_id: str,
        warehouse_id: str | None = None,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> dict[str, Any]:
        """Calculates a deterministic historical demand summary and trend for a product.

        Aggregates observed daily demand across historical dates. Compares the earlier
        half of the observed window to the recent half to determine historical trajectory.
        Contains no forecasting or future prediction.
        """
        records = self.list_all(
            product_id=product_id,
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date,
        )

        daily_totals: dict[dt.date, int] = defaultdict(int)
        for r in records:
            daily_totals[r.date] += r.quantity

        sorted_dates = sorted(daily_totals.keys())
        history = [
            {"date": d, "quantity": daily_totals[d]}
            for d in sorted_dates
        ]

        total_demand = sum(daily_totals.values())
        days_count = len(sorted_dates)
        average_daily_demand = round(total_demand / days_count, 2) if days_count > 0 else 0.0

        if days_count < 2:
            trend_direction = "stable"
            percentage_change = 0.0
        else:
            mid = days_count // 2
            first_half_sum = sum(daily_totals[d] for d in sorted_dates[:mid])
            first_half_avg = first_half_sum / mid

            second_half_sum = sum(daily_totals[d] for d in sorted_dates[mid:])
            second_half_avg = second_half_sum / (days_count - mid)

            if first_half_avg == 0:
                if second_half_avg == 0:
                    percentage_change = 0.0
                    trend_direction = "stable"
                else:
                    percentage_change = 100.0
                    trend_direction = "increasing"
            else:
                pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100.0
                percentage_change = round(pct, 2)
                if percentage_change > 5.0:
                    trend_direction = "increasing"
                elif percentage_change < -5.0:
                    trend_direction = "decreasing"
                else:
                    trend_direction = "stable"

        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "total_demand": total_demand,
            "average_daily_demand": average_daily_demand,
            "trend_direction": trend_direction,
            "percentage_change": percentage_change,
            "history": history,
        }
