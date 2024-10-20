import json
import os
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile

# تعريف مخطط المريض باستخدام Pydantic
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from patient_model import PatientModel

# إعداد قاعدة البيانات
DATABASE_URL = "sqlite:///./doctor.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# تعريف نموذج المريض
class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    date = Column(String, nullable=False)  # Change to Date if you have a Date type
    mobile = Column(String, nullable=False)
    details = Column(String)
    rays = Column(String)  # Make sure this is defined in your model
    createdAt = Column(DateTime, default=datetime.now)


# إنشاء الجداول في قاعدة البيانات
Base.metadata.create_all(bind=engine)
# يمكنك استيراد النموذج Patient والدوال اللازمة من الكود السابق


# # إنشاء دالة لإضافة مريض جديد
# def create_new_patient(PatientModel: dict, db: Session, rays_files: List[UploadFile]):
#     new_patient = Patient(
#         name=PatientModel["name"],
#         mobile=PatientModel["mobile"],
#         date=datetime.now(),
#         details=PatientModel["details"],
#         rays=[save_ray_image(ray_file) for ray_file in rays_files],
#         createdAt=datetime.now(),
#     )
#     db.add(new_patient)
#     db.commit()
#     db.refresh(new_patient)
#     return new_patient


# إعداد التطبيق
app = FastAPI()


# إعداد التبعية لجلسة قاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# إضافة مريض
@app.post("/patients/")
def create_patient(
    name: str,
    mobile: str,
    details: Optional[str] = None,
    rays: Optional[List[UploadFile]] = File(...),
    db: Session = Depends(get_db),
):
    try:
        images = [save_ray_image(ray_file) for ray_file in rays]
        db_patient = Patient(
            name=name,
            date=datetime.now().strftime("%Y-%m-%d"),
            mobile=mobile,
            details=details,
            rays=json.dumps(images) if images else None,
            createdAt=datetime.now(),
        )
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)
        return db_patient
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


""" @app.post("/patients/")
# نموذج الدالة
async def create_patient(
    patient: PatientModel,
    fileRays: List[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    # تحديد المسار الذي تريد حفظ الصور فيه
    directory = "images"

    # التأكد من وجود المجلد
    if not os.path.exists(directory):
        os.makedirs(directory)  # إنشاء المجلد إذا لم يكن موجودًا

    rays = []

    if fileRays:
        for file in fileRays:
            file_location = f"{directory}/{file.filename}"

            # حفظ الملف
            with open(file_location, "wb") as file_object:
                file_object.write(file.file.read())

            # إضافة مسار الصورة إلى قائمة الأشعة
            rays.append(file_location)

    # إنشاء كائن مريض جديد
    db_patient = PatientModel(
        name=patient.name,
        mobile=patient.mobile,
        details=patient.details,
        rays=rays,
        createdAt=datetime.now(),
    )

    # حفظ المريض في قاعدة البيانات
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    return {
        "message": "Patient created successfully",
        "data": db_patient,
    }
 """


def save_ray_image(ray_file: UploadFile) -> str:
    directory = "images"
    if not os.path.exists(directory):
        os.makedirs(directory)

    file_location = f"{directory}/{ray_file.filename}"
    with open(file_location, "wb") as buffer:
        buffer.write(ray_file.file.read())
    print("file_location: ", file_location)

    return file_location


# # نقطة نهاية لإضافة مريض جديد
# @app.post("/patients/")
# def add_patient(
#     patient: PatientModel,
#     rays_files: List[UploadFile] = File(...),
#     db: Session = Depends(get_db),
# ):
#     new_patient = create_new_patient(patient.dict(), db, rays_files)
#     return {"message": "Patient created successfully", "data": new_patient}


# الحصول على جميع المرضى
@app.get("/patients/", response_model=list[PatientModel])
def get_patients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    patients = db.query(Patient).offset(skip).limit(limit).all()
    return patients


# الحصول على مريض حسب المعرف
@app.get("/patients/{patient_id}", response_model=PatientModel)
def read_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


# وظيفة لتحديث بيانات مريض
@app.put("/patients/{patient_id}", response_model=PatientModel)
def update_patient(
    patient_id: int, updated_patient: PatientModel, db: Session = Depends(get_db)
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient.name = updated_patient.name
    patient.details = updated_patient.details
    patient.mobile = updated_patient.mobile
    patient.rays = updated_patient.rays
    patient.date = updated_patient.date
    db.commit()
    db.refresh(patient)
    return patient


# وظيفة لحذف مريض
@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    db.delete(patient)
    db.commit()
    return {"message": "Patient deleted successfully"}


""" 
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    # تحديد المسار الذي تريد حفظ الصورة فيه
    directory = "images"

    # التأكد من وجود المجلد
    if not os.path.exists(directory):
        os.makedirs(directory)  # إنشاء المجلد إذا لم يكن موجودًا

    file_location = f"{directory}/{file.filename}"

    # حفظ الملف
    with open(file_location, "wb") as file_object:
        file_object.write(file.file.read())

    return {"info": f"file '{file.filename}' saved at '{file_location}'"}
 """
