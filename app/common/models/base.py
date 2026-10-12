"""Base models and types for the platform."""

from datetime import datetime, timezone
from typing import Optional, Any, Annotated
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator, field_serializer
from bson import ObjectId


def validate_object_id(v: Any) -> ObjectId:
    """Validate and convert to ObjectId."""
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str) and ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError(f"Invalid ObjectId: {v}")


# Use Annotated for PyObjectId
PyObjectId = Annotated[ObjectId, BeforeValidator(validate_object_id)]


class MongoBaseModel(BaseModel):
    """Base model for MongoDB documents."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "created_at": "2025-10-29T10:00:00",
                "updated_at": "2025-10-29T10:00:00"
            }
        }
    )
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_serializer('id')
    def serialize_id(self, v: Optional[ObjectId]) -> Optional[str]:
        """Serialize ObjectId to string."""
        return str(v) if v else None
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, v: datetime) -> str:
        """Serialize datetime to ISO format."""
        return v.isoformat()
    
    def model_dump(self, **kwargs):
        """Override model_dump to handle _id field properly."""
        exclude_unset = kwargs.pop('exclude_unset', False)  # Changed default to False
        by_alias = kwargs.pop('by_alias', True)
        
        parsed = super().model_dump(
            exclude_unset=exclude_unset,
            by_alias=by_alias,
            **kwargs
        )
        
        # Convert _id to string for JSON serialization
        if "_id" in parsed and parsed["_id"] is not None:
            parsed["_id"] = str(parsed["_id"])
        
        return parsed
    
    def dict(self, **kwargs):
        """Backward compatibility for dict() method."""
        return self.model_dump(**kwargs)
