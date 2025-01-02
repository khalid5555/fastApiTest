from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PatientModel(BaseModel):
    id: Optional[int] = None  # يمكن أن يكون هذا الحقل خاليًا
    name: str
    date: str  # يمكنك استخدام datetime بدلاً من string إذا كنت ترغب في ذلك
    details: Optional[str] = None
    # rays: Optional[List[str]] = []  # يمكنك أن تجعل هذا اختياريًا
    rays: List[str] = Field(default_factory=list)  # حقل الأشعة افتراضيًا قائمة فارغة
    createAt: Optional[str] = None  # الوقت الذي تم فيه إنشاء السجل

    class Config:
        from_attributes = True
