"""Router for assistant steps endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.common.auth import get_current_admin_auth0, AdminUser
from .service import StepService
from .schemas import (
    StepResponse,
    UpdateStepRequest,
    StepListResponse,
    ParseQuestionsRequest,
    ParseQuestionsResponse
)

router = APIRouter(tags=["assistant-steps"])


async def get_steps_service() -> StepService:
    """Get steps service instance."""
    return StepService()


@router.get("/{assistant_id}/steps", response_model=StepListResponse)
async def get_assistant_steps(
    assistant_id: str,
    current_user: AdminUser = Depends(get_current_admin_auth0),
    service: StepService = Depends(get_steps_service)
):
    """
    Get all steps for an assistant.
    
    Returns steps ordered by order_no.
    """
    # user_id is email from token
    user_id = current_user.email
    
    try:
        steps = await service.get_assistant_steps(
            assistant_id=assistant_id,
            user_id=user_id
        )
        
        return StepListResponse(
            steps=[StepResponse.from_model(step) for step in steps],
            total=len(steps),
            assistant_id=assistant_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get steps: {str(e)}"
        )


@router.get("/{assistant_id}/steps/{step_id}", response_model=StepResponse)
async def get_step(
    assistant_id: str,
    step_id: str,
    current_user: AdminUser = Depends(get_current_admin_auth0),
    service: StepService = Depends(get_steps_service)
):
    """
    Get a specific step.
    """
    # user_id is email from token
    user_id = current_user.email
    
    try:
        step = await service.get_step(
            assistant_id=assistant_id,
            step_id=step_id,
            user_id=user_id
        )
        
        if not step:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found"
            )
        
        return StepResponse.from_model(step)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get step: {str(e)}"
        )


@router.put("/{assistant_id}/steps/{step_id}", response_model=StepResponse)
async def update_step(
    assistant_id: str,
    step_id: str,
    data: UpdateStepRequest,
    current_user: AdminUser = Depends(get_current_admin_auth0),
    service: StepService = Depends(get_steps_service)
):
    """
    Update a step - only prompt template can be edited.
    
    - Validates prompt template has balanced braces
    """
    # user_id is email from token
    user_id = current_user.email
    
    try:
        step = await service.update_step(
            assistant_id=assistant_id,
            step_id=step_id,
            user_id=user_id,
            data=data
        )
        
        if not step:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found"
            )
        
        return StepResponse.from_model(step)
    except ValueError as e:
        # Handle validation errors
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update step: {str(e)}"
        )


@router.post(
    "/{assistant_id}/steps/{step_id}/parse-questions",
    response_model=ParseQuestionsResponse
)
async def parse_questions(
    assistant_id: str,
    step_id: str,
    data: ParseQuestionsRequest,
    current_user: AdminUser = Depends(get_current_admin_auth0),
    service: StepService = Depends(get_steps_service)
):
    """
    Parse free-form text into a list of individual questions using LLM.
    
    Takes a block of text (e.g. pasted by user) and returns a structured
    list of questions that can be reviewed and edited in the UI.
    """
    user_id = current_user.email
    
    try:
        # Verify assistant and step exist
        step = await service.get_step(
            assistant_id=assistant_id,
            step_id=step_id,
            user_id=user_id
        )
        
        if not step:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found"
            )
        
        if step.step_key != "questionnaire":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parse questions is only available for questionnaire steps"
            )
        
        questions = await service.parse_questions_from_text(data.text)
        
        return ParseQuestionsResponse(questions=questions)
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse questions: {str(e)}"
        )
