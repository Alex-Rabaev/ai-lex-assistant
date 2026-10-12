"""API router for analysis module.

Endpoints for:
- Analysis configuration (GET, PUT, POST generate, GET suggestions)
- Snapshots (POST create, GET list, GET by id, PATCH update)
- Respondent analytics (GET by conversation, GET by assistant)
- Export (messages CSV/JSON, respondents/survey CSV/JSON)
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError

from app.common.auth import get_current_admin_auth0, AdminUser
from app.modules.analysis.schemas.api import (
    CreateSnapshotRequest,
    MockRespondentsDeleteResponse,
    MockRespondentsRequest,
    MockRespondentsResponse,
    ProfileListResponse,
    ProfileResponse,
    SnapshotCreatedResponse,
    SnapshotListResponse,
    SnapshotResponse,
    UpdateSnapshotRequest,
)
from app.modules.analysis.schemas.config import (
    AnalysisConfig,
    AnalysisFramework,
)
from app.modules.analysis.export_service import ExportService
from app.modules.analysis.service import AnalysisService
from app.modules.assistants.service import AssistantNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["analysis"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    }
)


async def get_analysis_service() -> AnalysisService:
    """Get AnalysisService instance."""
    return AnalysisService()


async def get_export_service() -> ExportService:
    """Get ExportService instance."""
    return ExportService()


class ExportFormat(str, Enum):
    json = "json"
    csv = "csv"


class GenerateConfigResponse(BaseModel):
    """Response for config generation endpoint."""
    suggested_framework: AnalysisFramework


# ==================== Configuration Endpoints ====================


@router.get(
    "/assistants/{assistant_id}/analysis-config",
    response_model=AnalysisConfig,
    summary="Get analysis configuration",
)
async def get_analysis_config(
    assistant_id: str,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> AnalysisConfig:
    """Get analysis config for assistant. Returns default if not set."""
    try:
        return await service.get_config(assistant_id, user_id=current_admin.email)
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")


@router.put(
    "/assistants/{assistant_id}/analysis-config",
    response_model=AnalysisConfig,
    summary="Update analysis configuration",
)
async def update_analysis_config(
    assistant_id: str,
    config: AnalysisConfig,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> AnalysisConfig:
    """Update analysis config for assistant."""
    try:
        return await service.update_config(assistant_id, user_id=current_admin.email, config=config)
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/assistants/{assistant_id}/analysis-config/generate",
    response_model=GenerateConfigResponse,
    summary="Auto-generate analysis categories from survey goals",
)
async def generate_analysis_config(
    assistant_id: str,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> GenerateConfigResponse:
    """Auto-generate analysis framework using AI."""
    try:
        from app.modules.analysis.llm import generate_config_llm
        framework = await service.generate_config(
            assistant_id, user_id=current_admin.email, llm_callable=generate_config_llm
        )
        return GenerateConfigResponse(suggested_framework=framework)
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate analysis config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate config: {str(e)}")


@router.get(
    "/assistants/{assistant_id}/analysis-config/suggestions",
    summary="Get analysis config suggestions",
)
async def get_analysis_suggestions(
    assistant_id: str,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> Dict[str, Any]:
    """Get suggestions for analysis config setup."""
    try:
        return await service.get_suggestions(assistant_id, user_id=current_admin.email)
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")


# ==================== Mock Respondents ====================


@router.post(
    "/assistants/{assistant_id}/mock-respondents",
    response_model=MockRespondentsResponse,
    summary="Create mock respondents for testing snapshots",
)
async def create_mock_respondents(
    assistant_id: str,
    request: MockRespondentsRequest = None,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> MockRespondentsResponse:
    """Create mock conversations with message history for the assistant."""
    if request is None:
        request = MockRespondentsRequest()
    try:
        result = await service.generate_mock_respondents(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            count=request.count,
            language=request.language,
            include_abandoned=request.include_abandoned,
        )
        return MockRespondentsResponse(
            created=result["created"],
            conversation_ids=result["conversation_ids"],
        )
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create mock respondents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create mock respondents: {str(e)}")


@router.delete(
    "/assistants/{assistant_id}/mock-respondents",
    response_model=MockRespondentsDeleteResponse,
    summary="Delete all mock respondents for assistant",
)
async def delete_mock_respondents(
    assistant_id: str,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> MockRespondentsDeleteResponse:
    """Delete all mock (test) conversations for this assistant. Does not affect real respondents."""
    try:
        result = await service.delete_mock_respondents(
            assistant_id=assistant_id,
            user_id=current_admin.email,
        )
        return MockRespondentsDeleteResponse(deleted=result["deleted"])
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except Exception as e:
        logger.error(f"Failed to delete mock respondents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete mock respondents: {str(e)}")


# ==================== Snapshot Endpoints ====================


@router.post(
    "/assistants/{assistant_id}/analysis/snapshot",
    response_model=SnapshotCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create analysis snapshot",
)
async def create_snapshot(
    assistant_id: str,
    request: CreateSnapshotRequest = None,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> SnapshotCreatedResponse:
    """Start snapshot generation. Returns immediately with execution_id."""
    if request is None:
        request = CreateSnapshotRequest()
    
    try:
        execution_id = await service.create_snapshot(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            force_recalculate=request.force_recalculate,
            include_partial=request.include_partial,
            include_mock=request.include_mock,
            version_name=request.version_name,
        )
        return SnapshotCreatedResponse(execution_id=execution_id)
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {str(e)}")


@router.get(
    "/assistants/{assistant_id}/analysis/snapshots",
    response_model=SnapshotListResponse,
    summary="List snapshots for assistant",
)
async def list_snapshots(
    assistant_id: str,
    include_archived: bool = Query(False, description="Include archived snapshots"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> SnapshotListResponse:
    """Get all snapshots for assistant."""
    try:
        executions = await service.get_snapshots(
            assistant_id, user_id=current_admin.email, include_archived=include_archived
        )
        snapshots = [
            SnapshotResponse(
                id=str(e.id),
                workflow_type=e.workflow_type,
                status=e.status.value if hasattr(e.status, 'value') else e.status,
                payload=e.payload,
                result=e.result,
                error_message=e.error_message,
                version_name=e.version_name,
                is_archived=e.is_archived,
                include_mock=e.payload.get("include_mock", False),
                triggered_by=e.triggered_by,
                started_at=e.started_at,
                completed_at=e.completed_at,
                duration_ms=e.duration_ms,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in executions
        ]
        return SnapshotListResponse(snapshots=snapshots, total=len(snapshots))
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")


@router.get(
    "/assistants/{assistant_id}/analysis/snapshots/{execution_id}",
    response_model=SnapshotResponse,
    summary="Get snapshot by ID",
)
async def get_snapshot(
    assistant_id: str,
    execution_id: str,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> SnapshotResponse:
    """Get specific snapshot."""
    execution = await service.get_snapshot(execution_id, user_id=current_admin.email)
    
    if not execution:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {execution_id}")
    
    return SnapshotResponse(
        id=str(execution.id),
        workflow_type=execution.workflow_type,
        status=execution.status.value if hasattr(execution.status, 'value') else execution.status,
        payload=execution.payload,
        result=execution.result,
        error_message=execution.error_message,
        version_name=execution.version_name,
        is_archived=execution.is_archived,
        include_mock=execution.payload.get("include_mock", False),
        triggered_by=execution.triggered_by,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=execution.duration_ms,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
    )


@router.patch(
    "/analysis/snapshots/{execution_id}",
    response_model=SnapshotResponse,
    summary="Update snapshot (name, archive)",
)
async def update_snapshot(
    execution_id: str,
    request: UpdateSnapshotRequest,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> SnapshotResponse:
    """Update snapshot metadata (version name, archive status)."""
    execution = await service.get_snapshot(execution_id, user_id=current_admin.email)
    
    if not execution:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {execution_id}")
    
    # Update fields via repository
    update_data = {}
    if request.version_name is not None:
        update_data["version_name"] = request.version_name
    if request.is_archived is not None:
        update_data["is_archived"] = request.is_archived
    
    if update_data:
        from app.modules.workflows.repository import WorkflowRepository
        repo = WorkflowRepository()
        # Direct field update — simple enough for PATCH
        await repo._ensure_db()
        from bson import ObjectId
        from datetime import datetime, timezone
        await repo._collection.update_one(
            {"_id": ObjectId(execution_id)},
            {"$set": {**update_data, "updated_at": datetime.now(timezone.utc)}}
        )
        execution = await service.get_snapshot(execution_id, user_id=current_admin.email)
    
    return SnapshotResponse(
        id=str(execution.id),
        workflow_type=execution.workflow_type,
        status=execution.status.value if hasattr(execution.status, 'value') else execution.status,
        payload=execution.payload,
        result=execution.result,
        error_message=execution.error_message,
        version_name=execution.version_name,
        is_archived=execution.is_archived,
        include_mock=execution.payload.get("include_mock", False),
        triggered_by=execution.triggered_by,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=execution.duration_ms,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
    )


@router.delete(
    "/analysis/snapshots/{execution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete snapshot",
)
async def delete_snapshot(
    execution_id: str,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> None:
    """Permanently delete a snapshot."""
    execution = await service.get_snapshot(execution_id, user_id=current_admin.email)
    
    if not execution:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {execution_id}")
    
    from app.modules.workflows.repository import WorkflowRepository
    from bson import ObjectId
    repo = WorkflowRepository()
    await repo._ensure_db()
    result = await repo._collection.delete_one({"_id": ObjectId(execution_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {execution_id}")


# ==================== Analytics Endpoints ====================


@router.get(
    "/conversations/{conversation_id}/analytic-meta",
    response_model=ProfileResponse,
    summary="Get analytics for conversation",
)
async def get_analytic_meta(
    conversation_id: str,
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> ProfileResponse:
    """Get analytic_meta for a specific conversation."""
    meta = await service.get_analytic_meta(conversation_id, user_id=current_admin.email)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Conversation or profile not found: {conversation_id}")
    analytic_meta = meta["analytic_meta"] or {}
    return ProfileResponse(
        conversation_id=conversation_id,
        analytic_meta=analytic_meta,
        is_mock=meta.get("is_mock", False),
        sufficient_data=analytic_meta.get("sufficient_data", True) if isinstance(analytic_meta, dict) else True,
    )


@router.get(
    "/assistants/{assistant_id}/analytic-meta",
    response_model=ProfileListResponse,
    summary="List analytics for assistant",
)
async def list_analytic_meta(
    assistant_id: str,
    include_mock: Optional[bool] = Query(
        None,
        description="Filter: true=only mock respondents, false=only real, omit=all"
    ),
    sufficient_data_only: bool = Query(
        False,
        description="If true, return only profiles with sufficient data quality"
    ),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: AnalysisService = Depends(get_analysis_service)
) -> ProfileListResponse:
    """Get all analytic_meta for assistant's conversations."""
    try:
        results = await service.get_analytic_meta_by_assistant(
            assistant_id,
            user_id=current_admin.email,
            include_mock=include_mock,
            sufficient_data_only=sufficient_data_only,
        )
        profiles = [
            ProfileResponse(
                conversation_id=r["conversation_id"],
                analytic_meta=r["analytic_meta"],
                is_mock=r.get("is_mock", False),
                sufficient_data=r.get("sufficient_data", True),
            )
            for r in results
        ]
        return ProfileListResponse(profiles=profiles, total=len(profiles))
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")


# ==================== Export Endpoints ====================


def _parse_date(value: Optional[str], param_name: str) -> Optional[datetime]:
    """Parse ISO date string or raise 400."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name} format. Use ISO format.",
        )


def _file_response(content: str, filename: str, media_type: str) -> Response:
    """Build a downloadable file response."""
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/assistants/{assistant_id}/interlocutors/{interlocutor_id}/export/messages",
    summary="Export single respondent messages (CSV/JSON)",
    tags=["export"],
)
async def export_single_messages(
    assistant_id: str,
    interlocutor_id: str,
    format: ExportFormat = Query(ExportFormat.json, description="Export format"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ExportService = Depends(get_export_service),
):
    """Download conversation messages for a single respondent."""
    try:
        rows = await service.get_single_messages(
            assistant_id=assistant_id,
            interlocutor_id=interlocutor_id,
            user_id=current_admin.email,
        )
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except Exception as e:
        logger.error(f"Export single messages failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if format == ExportFormat.csv:
        csv_text = service.single_messages_to_csv(rows)
        return _file_response(csv_text, f"messages_{interlocutor_id}.csv", "text/csv; charset=utf-8")

    return _file_response(
        json.dumps(rows, ensure_ascii=False, indent=2),
        f"messages_{interlocutor_id}.json",
        "application/json; charset=utf-8",
    )


@router.get(
    "/assistants/{assistant_id}/export/messages",
    summary="Bulk export messages for all respondents (CSV/JSON)",
    tags=["export"],
)
async def export_bulk_messages(
    assistant_id: str,
    format: ExportFormat = Query(ExportFormat.json, description="Export format"),
    include_mock: bool = Query(False, description="Include mock respondents"),
    conversation_ids: Optional[List[str]] = Query(None, description="Filter by conversation IDs"),
    stage: Optional[List[str]] = Query(None, description="Filter by stage (e.g. completed)"),
    date_from: Optional[str] = Query(None, description="Filter from date (ISO)"),
    date_to: Optional[str] = Query(None, description="Filter to date (ISO)"),
    limit: int = Query(500, ge=1, le=2000, description="Max respondents"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ExportService = Depends(get_export_service),
):
    """Download conversation messages for all (or filtered) respondents."""
    try:
        data = await service.get_bulk_messages(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            include_mock=include_mock,
            conversation_ids=conversation_ids,
            stages=stage,
            date_from=_parse_date(date_from, "date_from"),
            date_to=_parse_date(date_to, "date_to"),
            limit=limit,
        )
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except Exception as e:
        logger.error(f"Export bulk messages failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if format == ExportFormat.csv:
        csv_text = service.bulk_messages_to_csv(data)
        return _file_response(csv_text, f"messages_{assistant_id}.csv", "text/csv; charset=utf-8")

    return _file_response(
        json.dumps(data, ensure_ascii=False, indent=2),
        f"messages_{assistant_id}.json",
        "application/json; charset=utf-8",
    )


@router.get(
    "/assistants/{assistant_id}/export/respondents",
    summary="Bulk export respondent profiles and survey data (CSV/JSON)",
    tags=["export"],
)
async def export_bulk_respondents(
    assistant_id: str,
    format: ExportFormat = Query(ExportFormat.json, description="Export format"),
    include_mock: bool = Query(False, description="Include mock respondents"),
    conversation_ids: Optional[List[str]] = Query(None, description="Filter by conversation IDs"),
    stage: Optional[List[str]] = Query(None, description="Filter by stage (e.g. completed)"),
    date_from: Optional[str] = Query(None, description="Filter from date (ISO)"),
    date_to: Optional[str] = Query(None, description="Filter to date (ISO)"),
    limit: int = Query(500, ge=1, le=2000, description="Max respondents"),
    current_admin: AdminUser = Depends(get_current_admin_auth0),
    service: ExportService = Depends(get_export_service),
):
    """Download respondent profiles with survey Q&A data."""
    try:
        data = await service.get_bulk_respondents(
            assistant_id=assistant_id,
            user_id=current_admin.email,
            include_mock=include_mock,
            conversation_ids=conversation_ids,
            stages=stage,
            date_from=_parse_date(date_from, "date_from"),
            date_to=_parse_date(date_to, "date_to"),
            limit=limit,
        )
    except AssistantNotFoundError:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {assistant_id}")
    except Exception as e:
        logger.error(f"Export bulk respondents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if format == ExportFormat.csv:
        csv_text = service.bulk_respondents_to_csv(data)
        return _file_response(csv_text, f"respondents_{assistant_id}.csv", "text/csv; charset=utf-8")

    return _file_response(
        json.dumps(data, ensure_ascii=False, indent=2),
        f"respondents_{assistant_id}.json",
        "application/json; charset=utf-8",
    )
