"""
CRUD operations for UsageLog model.
Provides methods for logging AI usage and querying analytics.
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, extract
from decimal import Decimal

from app.models.usage_log import UsageLog, FeatureType, OperationType
from app.models.document import Document
from app.models.code_component import CodeComponent
from app.models.user import User
from app.schemas.usage_log import (
    UsageLogCreate,
    FeatureUsageSummary,
    OperationUsageSummary,
    TimeSeriesDataPoint,
    DocumentUsageSummary,
    CodeComponentUsageSummary,
    TokenSummary,
    TimeRangeEnum,
    WeeklyUsageSummary,
    MonthlyUsageSummary,
)


class CRUDUsageLog:
    """CRUD operations for usage log entries."""

    def create(self, db: Session, *, obj_in: UsageLogCreate) -> UsageLog:
        """Create a new usage log entry."""
        db_obj = UsageLog(
            tenant_id=obj_in.tenant_id,
            user_id=obj_in.user_id,
            document_id=obj_in.document_id,
            feature_type=obj_in.feature_type,
            operation=obj_in.operation,
            model_used=obj_in.model_used,
            input_tokens=obj_in.input_tokens,
            output_tokens=obj_in.output_tokens,
            cached_tokens=obj_in.cached_tokens,
            cost_usd=obj_in.cost_usd,
            cost_inr=obj_in.cost_inr,
            processing_time_seconds=obj_in.processing_time_seconds,
            extra_data=obj_in.extra_data,
            created_at=datetime.now(),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def log_usage(
        self,
        db: Session,
        *,
        tenant_id: int,
        feature_type: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        cost_inr: float,
        user_id: Optional[int] = None,
        document_id: Optional[int] = None,
        model_used: str = "gemini-2.5-flash",
        cached_tokens: int = 0,
        processing_time_seconds: Optional[float] = None,
        extra_data: Optional[dict] = None,
    ) -> UsageLog:
        """
        Convenience method to log AI usage.
        Used throughout the application after each AI API call.
        """
        obj_in = UsageLogCreate(
            tenant_id=tenant_id,
            user_id=user_id,
            document_id=document_id,
            feature_type=feature_type,
            operation=operation,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost_usd,
            cost_inr=cost_inr,
            processing_time_seconds=processing_time_seconds,
            extra_data=extra_data,
        )
        return self.create(db, obj_in=obj_in)

    def get_date_range(self, time_range: TimeRangeEnum, custom_start: Optional[date] = None, custom_end: Optional[date] = None) -> tuple[datetime, datetime]:
        """Get start and end datetime for a time range."""
        today = date.today()
        now = datetime.now()

        if time_range == TimeRangeEnum.TODAY:
            start = datetime.combine(today, datetime.min.time())
            end = now
        elif time_range == TimeRangeEnum.YESTERDAY:
            yesterday = today - timedelta(days=1)
            start = datetime.combine(yesterday, datetime.min.time())
            end = datetime.combine(yesterday, datetime.max.time())
        elif time_range == TimeRangeEnum.LAST_7_DAYS:
            start = datetime.combine(today - timedelta(days=7), datetime.min.time())
            end = now
        elif time_range == TimeRangeEnum.LAST_15_DAYS:
            start = datetime.combine(today - timedelta(days=15), datetime.min.time())
            end = now
        elif time_range == TimeRangeEnum.THIS_WEEK:
            start_of_week = today - timedelta(days=today.weekday())
            start = datetime.combine(start_of_week, datetime.min.time())
            end = now
        elif time_range == TimeRangeEnum.LAST_WEEK:
            start_of_this_week = today - timedelta(days=today.weekday())
            start_of_last_week = start_of_this_week - timedelta(days=7)
            end_of_last_week = start_of_this_week - timedelta(days=1)
            start = datetime.combine(start_of_last_week, datetime.min.time())
            end = datetime.combine(end_of_last_week, datetime.max.time())
        elif time_range == TimeRangeEnum.THIS_MONTH:
            start = datetime(today.year, today.month, 1)
            end = now
        elif time_range == TimeRangeEnum.LAST_MONTH:
            first_of_this_month = date(today.year, today.month, 1)
            last_of_prev_month = first_of_this_month - timedelta(days=1)
            start = datetime(last_of_prev_month.year, last_of_prev_month.month, 1)
            end = datetime.combine(last_of_prev_month, datetime.max.time())
        elif time_range == TimeRangeEnum.LAST_30_DAYS:
            start = datetime.combine(today - timedelta(days=30), datetime.min.time())
            end = now
        elif time_range == TimeRangeEnum.LAST_90_DAYS:
            start = datetime.combine(today - timedelta(days=90), datetime.min.time())
            end = now
        elif time_range == TimeRangeEnum.THIS_YEAR:
            start = datetime(today.year, 1, 1)
            end = now
        elif time_range == TimeRangeEnum.CUSTOM:
            if custom_start and custom_end:
                start = datetime.combine(custom_start, datetime.min.time())
                end = datetime.combine(custom_end, datetime.max.time())
            else:
                # Default to last 30 days if custom dates not provided
                start = datetime.combine(today - timedelta(days=30), datetime.min.time())
                end = now
        else:
            start = datetime.combine(today - timedelta(days=30), datetime.min.time())
            end = now

        return start, end

    def get_by_tenant(
        self,
        db: Session,
        *,
        tenant_id: int,
        time_range: TimeRangeEnum = TimeRangeEnum.THIS_MONTH,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        feature_type: Optional[str] = None,
        document_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UsageLog]:
        """Get usage logs for a tenant with filters."""
        start, end = self.get_date_range(time_range, start_date, end_date)

        query = db.query(UsageLog).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        )

        if feature_type:
            query = query.filter(UsageLog.feature_type == feature_type)
        if document_id:
            query = query.filter(UsageLog.document_id == document_id)

        return query.order_by(desc(UsageLog.created_at)).offset(offset).limit(limit).all()

    def get_total_summary(
        self,
        db: Session,
        *,
        tenant_id: int,
        start: datetime,
        end: datetime,
        feature_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregate summary for a tenant."""
        query = db.query(
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cached_tokens), 0).label("total_cached_tokens"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("total_cost_usd"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        )

        if feature_type:
            query = query.filter(UsageLog.feature_type == feature_type)

        result = query.first()

        return {
            "total_calls": result.total_calls or 0,
            "total_input_tokens": int(result.total_input_tokens or 0),
            "total_output_tokens": int(result.total_output_tokens or 0),
            "total_cached_tokens": int(result.total_cached_tokens or 0),
            "total_cost_usd": float(result.total_cost_usd or 0),
            "total_cost_inr": float(result.total_cost_inr or 0),
        }

    def get_by_feature(
        self,
        db: Session,
        *,
        tenant_id: int,
        start: datetime,
        end: datetime,
    ) -> List[FeatureUsageSummary]:
        """Get usage breakdown by feature type."""
        # First get total cost for percentage calculation
        total_result = db.query(
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total")
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).first()

        total_cost = float(total_result.total or 0)

        # Get breakdown by feature
        results = db.query(
            UsageLog.feature_type,
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("total_cost_usd"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).group_by(UsageLog.feature_type).all()

        summaries = []
        for r in results:
            total_tokens = int(r.total_input_tokens or 0) + int(r.total_output_tokens or 0)
            cost_inr = float(r.total_cost_inr or 0)
            calls = r.total_calls or 1

            summaries.append(FeatureUsageSummary(
                feature_type=r.feature_type,
                total_calls=r.total_calls or 0,
                total_input_tokens=int(r.total_input_tokens or 0),
                total_output_tokens=int(r.total_output_tokens or 0),
                total_tokens=total_tokens,
                total_cost_usd=float(r.total_cost_usd or 0),
                total_cost_inr=cost_inr,
                avg_cost_per_call_inr=cost_inr / calls if calls > 0 else 0,
                percentage_of_total=(cost_inr / total_cost * 100) if total_cost > 0 else 0,
            ))

        return sorted(summaries, key=lambda x: x.total_cost_inr, reverse=True)

    def get_by_operation(
        self,
        db: Session,
        *,
        tenant_id: int,
        start: datetime,
        end: datetime,
        limit: int = 10,
    ) -> List[OperationUsageSummary]:
        """Get usage breakdown by operation."""
        results = db.query(
            UsageLog.feature_type,
            UsageLog.operation,
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).group_by(
            UsageLog.feature_type, UsageLog.operation
        ).order_by(desc("total_cost_inr")).limit(limit).all()

        return [
            OperationUsageSummary(
                feature_type=r.feature_type,
                operation=r.operation,
                total_calls=r.total_calls or 0,
                total_input_tokens=int(r.total_input_tokens or 0),
                total_output_tokens=int(r.total_output_tokens or 0),
                total_tokens=int(r.total_input_tokens or 0) + int(r.total_output_tokens or 0),
                total_cost_inr=float(r.total_cost_inr or 0),
            )
            for r in results
        ]

    def get_daily_usage(
        self,
        db: Session,
        *,
        tenant_id: int,
        start: datetime,
        end: datetime,
        feature_type: Optional[str] = None,
    ) -> List[TimeSeriesDataPoint]:
        """Get daily usage for time series charts."""
        query = db.query(
            func.date(UsageLog.created_at).label("date"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
            func.coalesce(func.sum(UsageLog.input_tokens + UsageLog.output_tokens), 0).label("total_tokens"),
            func.count(UsageLog.id).label("call_count"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        )

        if feature_type:
            query = query.filter(UsageLog.feature_type == feature_type)

        results = query.group_by(func.date(UsageLog.created_at)).order_by("date").all()

        return [
            TimeSeriesDataPoint(
                date=r.date,
                total_cost_inr=float(r.total_cost_inr or 0),
                total_tokens=int(r.total_tokens or 0),
                call_count=r.call_count or 0,
            )
            for r in results
        ]

    def get_top_documents(
        self,
        db: Session,
        *,
        tenant_id: int,
        start: datetime,
        end: datetime,
        limit: int = 10,
    ) -> List[DocumentUsageSummary]:
        """Get top documents by cost."""
        results = db.query(
            UsageLog.document_id,
            Document.filename,
            UsageLog.feature_type,
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
            func.max(UsageLog.created_at).label("last_used"),
        ).join(
            Document, UsageLog.document_id == Document.id
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.document_id.isnot(None),
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).group_by(
            UsageLog.document_id, Document.filename, UsageLog.feature_type
        ).order_by(desc("total_cost_inr")).limit(limit).all()

        return [
            DocumentUsageSummary(
                document_id=r.document_id,
                filename=r.filename or f"Document {r.document_id}",
                feature_type=r.feature_type,
                total_calls=r.total_calls or 0,
                total_input_tokens=int(r.total_input_tokens or 0),
                total_output_tokens=int(r.total_output_tokens or 0),
                total_tokens=int(r.total_input_tokens or 0) + int(r.total_output_tokens or 0),
                total_cost_inr=float(r.total_cost_inr or 0),
                last_used=r.last_used,
            )
            for r in results
        ]

    def get_top_code_components(
        self,
        db: Session,
        *,
        tenant_id: int,
        limit: int = 10,
    ) -> List[CodeComponentUsageSummary]:
        """Get top code components by cost (from code_components table directly)."""
        results = db.query(CodeComponent).filter(
            CodeComponent.tenant_id == tenant_id,
            CodeComponent.ai_cost_inr.isnot(None),
            CodeComponent.ai_cost_inr > 0,
        ).order_by(desc(CodeComponent.ai_cost_inr)).limit(limit).all()

        return [
            CodeComponentUsageSummary(
                component_id=r.id,
                name=r.name,
                component_type=r.component_type,
                total_cost_inr=float(r.ai_cost_inr or 0),
                token_count_input=int(r.token_count_input or 0),
                token_count_output=int(r.token_count_output or 0),
                total_tokens=int(r.token_count_input or 0) + int(r.token_count_output or 0),
                analysis_status=r.analysis_status or "unknown",
            )
            for r in results
        ]

    def get_token_summary(
        self,
        db: Session,
        *,
        tenant_id: int,
        start: datetime,
        end: datetime,
    ) -> TokenSummary:
        """Get aggregate token summary."""
        result = db.query(
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cached_tokens), 0).label("total_cached_tokens"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).first()

        total_calls = result.total_calls or 1
        input_tokens = int(result.total_input_tokens or 0)
        output_tokens = int(result.total_output_tokens or 0)
        cached_tokens = int(result.total_cached_tokens or 0)

        return TokenSummary(
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_cached_tokens=cached_tokens,
            total_tokens=input_tokens + output_tokens,
            avg_input_per_call=input_tokens / total_calls if total_calls > 0 else 0,
            avg_output_per_call=output_tokens / total_calls if total_calls > 0 else 0,
            input_output_ratio=input_tokens / output_tokens if output_tokens > 0 else 0,
        )

    def get_weekly_summary(
        self,
        db: Session,
        *,
        tenant_id: int,
        weeks: int = 4,
    ) -> List[WeeklyUsageSummary]:
        """Get weekly usage summary for the last N weeks."""
        today = date.today()
        summaries = []

        for i in range(weeks):
            # Calculate week boundaries
            start_of_week = today - timedelta(days=today.weekday() + (i * 7))
            end_of_week = start_of_week + timedelta(days=6)

            if end_of_week > today:
                end_of_week = today

            start_dt = datetime.combine(start_of_week, datetime.min.time())
            end_dt = datetime.combine(end_of_week, datetime.max.time())

            result = db.query(
                func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
                func.coalesce(func.sum(UsageLog.input_tokens + UsageLog.output_tokens), 0).label("total_tokens"),
                func.count(UsageLog.id).label("call_count"),
            ).filter(
                UsageLog.tenant_id == tenant_id,
                UsageLog.created_at >= start_dt,
                UsageLog.created_at <= end_dt,
            ).first()

            summaries.append(WeeklyUsageSummary(
                week_number=weeks - i,
                week_start=start_of_week,
                week_end=end_of_week,
                total_cost_inr=float(result.total_cost_inr or 0),
                total_tokens=int(result.total_tokens or 0),
                call_count=result.call_count or 0,
                change_from_previous_week=None,  # Will be calculated after
            ))

        # Calculate week-over-week change
        summaries.reverse()  # Now oldest first
        for i in range(1, len(summaries)):
            prev_cost = summaries[i - 1].total_cost_inr
            curr_cost = summaries[i].total_cost_inr
            if prev_cost > 0:
                change = ((curr_cost - prev_cost) / prev_cost) * 100
                summaries[i].change_from_previous_week = round(change, 1)

        summaries.reverse()  # Back to newest first
        return summaries

    # =========================================================================
    # USER-LEVEL ANALYTICS (For Admin/CXO Dashboard)
    # =========================================================================

    def get_all_users_summary(
        self,
        db: Session,
        *,
        tenant_id: int,
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Get usage summary for ALL users in a tenant.
        For Admin/CXO dashboard to see billing breakdown by user.
        """
        # Get total cost for percentage calculation
        total_result = db.query(
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total")
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).first()

        total_cost = float(total_result.total or 0)

        # Get breakdown by user
        results = db.query(
            UsageLog.user_id,
            User.email,
            User.full_name,
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("total_cost_usd"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
            func.max(UsageLog.created_at).label("last_activity"),
        ).outerjoin(
            User, UsageLog.user_id == User.id
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).group_by(
            UsageLog.user_id, User.email, User.full_name
        ).order_by(desc("total_cost_inr")).all()

        summaries = []
        for r in results:
            cost_inr = float(r.total_cost_inr or 0)
            summaries.append({
                "user_id": r.user_id,
                "user_email": r.email or f"User #{r.user_id}" if r.user_id else "System/Unknown",
                "user_name": r.full_name or "Unknown",
                "total_calls": r.total_calls or 0,
                "total_input_tokens": int(r.total_input_tokens or 0),
                "total_output_tokens": int(r.total_output_tokens or 0),
                "total_tokens": int(r.total_input_tokens or 0) + int(r.total_output_tokens or 0),
                "total_cost_usd": float(r.total_cost_usd or 0),
                "total_cost_inr": cost_inr,
                "percentage_of_total": (cost_inr / total_cost * 100) if total_cost > 0 else 0,
                "last_activity": r.last_activity,
            })

        return summaries

    def get_user_summary(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        """Get detailed usage summary for a specific user."""
        result = db.query(
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cached_tokens), 0).label("total_cached_tokens"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("total_cost_usd"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.user_id == user_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).first()

        # Get user info
        user = db.query(User).filter(User.id == user_id).first()

        return {
            "user_id": user_id,
            "user_email": user.email if user else f"User #{user_id}",
            "user_name": user.full_name if user else "Unknown",
            "total_calls": result.total_calls or 0,
            "total_input_tokens": int(result.total_input_tokens or 0),
            "total_output_tokens": int(result.total_output_tokens or 0),
            "total_cached_tokens": int(result.total_cached_tokens or 0),
            "total_tokens": int(result.total_input_tokens or 0) + int(result.total_output_tokens or 0),
            "total_cost_usd": float(result.total_cost_usd or 0),
            "total_cost_inr": float(result.total_cost_inr or 0),
        }

    def get_user_by_feature(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> List[FeatureUsageSummary]:
        """Get feature breakdown for a specific user."""
        # Get total for this user for percentage
        total_result = db.query(
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total")
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.user_id == user_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).first()

        total_cost = float(total_result.total or 0)

        results = db.query(
            UsageLog.feature_type,
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("total_cost_usd"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.user_id == user_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).group_by(UsageLog.feature_type).all()

        summaries = []
        for r in results:
            total_tokens = int(r.total_input_tokens or 0) + int(r.total_output_tokens or 0)
            cost_inr = float(r.total_cost_inr or 0)
            calls = r.total_calls or 1

            summaries.append(FeatureUsageSummary(
                feature_type=r.feature_type,
                total_calls=r.total_calls or 0,
                total_input_tokens=int(r.total_input_tokens or 0),
                total_output_tokens=int(r.total_output_tokens or 0),
                total_tokens=total_tokens,
                total_cost_usd=float(r.total_cost_usd or 0),
                total_cost_inr=cost_inr,
                avg_cost_per_call_inr=cost_inr / calls if calls > 0 else 0,
                percentage_of_total=(cost_inr / total_cost * 100) if total_cost > 0 else 0,
            ))

        return sorted(summaries, key=lambda x: x.total_cost_inr, reverse=True)

    def get_user_daily_usage(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> List[TimeSeriesDataPoint]:
        """Get daily usage for a specific user."""
        results = db.query(
            func.date(UsageLog.created_at).label("date"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
            func.coalesce(func.sum(UsageLog.input_tokens + UsageLog.output_tokens), 0).label("total_tokens"),
            func.count(UsageLog.id).label("call_count"),
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.user_id == user_id,
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).group_by(func.date(UsageLog.created_at)).order_by("date").all()

        return [
            TimeSeriesDataPoint(
                date=r.date,
                total_cost_inr=float(r.total_cost_inr or 0),
                total_tokens=int(r.total_tokens or 0),
                call_count=r.call_count or 0,
            )
            for r in results
        ]

    def get_user_documents(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: int,
        start: datetime,
        end: datetime,
        limit: int = 10,
    ) -> List[DocumentUsageSummary]:
        """Get top documents by cost for a specific user."""
        results = db.query(
            UsageLog.document_id,
            Document.filename,
            UsageLog.feature_type,
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageLog.cost_inr), 0).label("total_cost_inr"),
            func.max(UsageLog.created_at).label("last_used"),
        ).join(
            Document, UsageLog.document_id == Document.id
        ).filter(
            UsageLog.tenant_id == tenant_id,
            UsageLog.user_id == user_id,
            UsageLog.document_id.isnot(None),
            UsageLog.created_at >= start,
            UsageLog.created_at <= end,
        ).group_by(
            UsageLog.document_id, Document.filename, UsageLog.feature_type
        ).order_by(desc("total_cost_inr")).limit(limit).all()

        return [
            DocumentUsageSummary(
                document_id=r.document_id,
                filename=r.filename or f"Document {r.document_id}",
                feature_type=r.feature_type,
                total_calls=r.total_calls or 0,
                total_input_tokens=int(r.total_input_tokens or 0),
                total_output_tokens=int(r.total_output_tokens or 0),
                total_tokens=int(r.total_input_tokens or 0) + int(r.total_output_tokens or 0),
                total_cost_inr=float(r.total_cost_inr or 0),
                last_used=r.last_used,
            )
            for r in results
        ]


# Singleton instance
crud_usage_log = CRUDUsageLog()
