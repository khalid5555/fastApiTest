import json
import os
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
    # __tablename__ = "doctor"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    date = Column(String, nullable=False)  # Change to Date if you have a Date type
    mobile = Column(String, nullable=False)
    details = Column(String)
    rays = Column(JSON)  # Make sure this is defined in your model
    createdAt = Column(DateTime, default=datetime.now)


# إنشاء الجداول في قاعدة البيانات
Base.metadata.create_all(bind=engine)
# يمكنك استيراد النموذج Patient والدوال اللازمة من الكود السابق
# تأكد من وجود مجلد للأشعة


# إعداد التطبيق
app = FastAPI()

app.mount("/images", StaticFiles(directory="images"), name="images")

# إعداد قالب Jinja2
templates = Jinja2Templates(directory="templates")

# قائمة لتمثيل المرضى
patients: List[PatientModel] = []


# إعداد التبعية لجلسة قاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# لصفحة الرئيسية
@app.get("/", response_class=HTMLResponse)
async def read_home(
    request: Request,
    db: Session = Depends(get_db),
):
    patients = get_patients(skip=0, limit=100, db=db)
    return templates.TemplateResponse(
        "index.html", {"request": request, "patients": patients}
    )


@app.get("/create_patient_page", response_class=HTMLResponse)
def create_patient_form(request: Request):
    return templates.TemplateResponse("create_patient.html", {"request": request})


# إضافة مريض
@app.post("/create_patient", response_class=HTMLResponse)
def create_patient(
    request: Request,
    name: str = Form(...),
    mobile: Optional[str] = Form(None, max_length=11),
    date: Optional[datetime] = Form(default=None),
    details: Optional[str] = Form(default=None),
    rays: Optional[List[UploadFile]] = Form(default=None),
    db: Session = Depends(get_db),
):
    try:
        print("rays:========.. ", rays.__len__())
        images = []

        # تحقق من وجود صور الأشعة ومعالجتها إذا كانت موجودة
        if rays:
            for ray_file in rays:
                if ray_file:  # التحقق من أن الملف ليس فارغًا
                    # تحديد مسار حفظ الصورة
                    file_location = os.path.join("images", ray_file.filename)

                    # حفظ الملف على القرص
                    with open(file_location, "wb") as f:
                        f.write(ray_file.file.read())

                    # إضافة مسار الصورة إلى قائمة الصور
                    images.append(file_location)
                    print("images:=======> ", images)
        # إنشاء كائن المريض بعد إضافة جميع الصور
        db_patient = Patient(
            name=name,
            date=(
                date.strftime("%Y-%m-%d")
                if date
                else datetime.now().strftime("%Y-%m-%d")
            ),
            mobile=mobile,
            details=details,
            rays=images,
            createdAt=datetime.now(),
        )

        # حفظ المريض في قاعدة البيانات
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)

        # جلب قائمة المرضى لعرضها في الواجهة
        db_patient2 = get_patients(skip=0, limit=100, db=db)

        # عرض الصفحة الرئيسية مع قائمة المرضى
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        # في حالة حدوث خطأ، يتم إرجاع العمليات
        db.rollback()
        raise e
    finally:
        # إغلاق الاتصال بقاعدة البيانات
        db.close()


# تعديل دالة إضافة مريض
@app.post("/add_patient", response_class=HTMLResponse)
async def add_patient(
    request: Request,
    name: str = Form(...),
    date: str = Form(...),
    mobile: str = Form(...),
    details: str = Form(None),
    rays: List[UploadFile] = File([]),
):
    directory = "images"
    if not os.path.exists(directory):
        os.makedirs(directory)

    ray_filenames = []
    for ray in rays:
        filename = f"{directory}_{ray.filename}"
        with open(filename, "wb") as buffer:
            buffer.write(ray.file.read())
        ray_filenames.append(filename)

    new_patient = PatientModel(
        id=len(patients) + 1,
        name=name,
        date=date,
        mobile=mobile,
        details=details,
        rays=ray_filenames,
        createdAt=datetime.now(),
    )
    patients.append(new_patient)
    return templates.TemplateResponse(
        "index.html", {"request": request, "patients": patients}
    )


def save_ray_image(ray_file: UploadFile) -> str:
    directory = "images"
    if not os.path.exists(directory):
        os.makedirs(directory)

    file_location = f"{directory}/{ray_file.filename}"
    with open(file_location, "wb") as buffer:
        buffer.write(ray_file.file.read())
    print("file_location: ", file_location)

    return file_location


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
@app.post("/delete_patient/{patient_id}")
async def delete_patient(
    patient_id: int, request: Request, db: Session = Depends(get_db)
):
    # تحقق من أن _method هو DELETE
    form_data = await request.form()
    if form_data.get("_method") == "DELETE":
        # البحث عن المريض
        patient = db.query(Patient).filter(Patient.id == patient_id).first()

        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")

        db.delete(patient)
        db.commit()

        # الحصول على جميع المرضى
        patients = get_patients(skip=0, limit=100, db=db)
        print("delete patient======: ", patients.__len__())
        return RedirectResponse(url="/", status_code=303)


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
