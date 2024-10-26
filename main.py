import json
import os
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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
    details = Column(String)
    rays = Column(String)  # Make sure this is defined in your model
    date = Column(String, nullable=False)  # Change to Date if you have a Date type
    createdAt = Column(String, default=datetime.now)


# إنشاء الجداول في قاعدة البيانات
Base.metadata.create_all(bind=engine)
# إعداد التطبيق
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # يمكنك تحديد النطاقات المسموح بها هنا
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
async def read_home(request: Request, db: Session = Depends(get_db)):
    patients = get_patients(db=db)
    return templates.TemplateResponse(
        "index.html", {"request": request, "patients": patients}
    )


@app.get("/create_patient_page", response_class=HTMLResponse)
def create_patient_form(request: Request):
    return templates.TemplateResponse("create_patient.html", {"request": request})


# إضافة مريض
@app.post("/create_patient", response_class=HTMLResponse)
async def create_patient(
    request: Request,
    name: str = Form(...),
    date: Optional[str] = Form(default=None),
    details: Optional[str] = Form(default=None),
    rays: List[UploadFile] | None = None,
    db: Session = Depends(get_db),
):
    try:
        print("rays:========> ", rays)
        images = []

        # تحقق من وجود صور الأشعة ومعالجتها إذا كانت موجودة
        if rays is not None and len(rays) > 0:
            for ray_file in rays:
                if (
                    ray_file
                    and ray_file.filename
                    and ray_file.filename != ""
                    and ray_file.file
                ):
                    # تحديد مسار حفظ الصورة
                    file_location = save_ray_image(ray_file)
                    print("file_location: ", file_location)
                    images.append(file_location)
                    print("images:=======> ", images)

        # إنشاء كائن المريض بعد إضافة جميع الصور
        db_patient = Patient(
            name=name,
            date=date,
            # date=(
            #     date.strftime("%Y-%m-%d")
            #     if date
            #     else datetime.now().strftime("%Y-%m-%d")
            # ),
            details=details,
            rays=images,
            createdAt=datetime.now(),
        )

        # حفظ المريض في قاعدة البيانات
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)

        # جلب قائمة المرضى لعرضها في الواجهة
        db_patient2 = get_patients(db=db)

        # عرض الصفحة الرئيسية مع قائمة المرضى
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        # في حالة حدوث خطأ، يتم إرجاع العمليات
        db.rollback()
        raise e
    finally:
        # إغلاق الاتصال بقاعدة البيانات
        db.close()


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
def get_patients(db: Session = Depends(get_db)):
    try:
        patients = db.query(Patient).offset(0).limit(1000).all()
        for patient in patients:
            patient.rays = patient.rays.replace("[", "").replace("]", "").split(", ")

        print(vars(patients[0]))
        return patients
    except Exception as e:
        raise e


# الحصول على جميع المرضى
@app.get("/api/get_all/", response_class=JSONResponse)
def get_patients_api(db: Session = Depends(get_db)):
    try:
        patients = db.query(Patient).offset(0).limit(1000).all()
        # معالجة البيانات قبل إرجاعها
        for patient in patients:
            # تحويل حقل rays إلى قائمة إذا كان مخزن كسلسلة نصية
            if isinstance(patient.rays, str):
                try:
                    patient.rays = json.loads(patient.rays)
                except json.JSONDecodeError:
                    # إذا لم تكن JSON صحيحة، يمكن تحويلها إلى قائمة بالطريقة المناسبة
                    patient.rays = (
                        patient.rays.replace("[", "").replace("]", "").split(", ")
                    )
        patient_data = [PatientModel.from_orm(patient).dict() for patient in patients]
        print(vars(patients[0]))

        return JSONResponse(
            content={
                "success": True,
                "data": {"records": patient_data, "nums": len(patient_data)},
            }
        )
        # return JSONResponse(
        #     content={
        #         "success": True,
        #         "number_patients": len(patient_data),
        #         "data": patient_data,
        #     }
        # )

    except Exception as e:
        raise e


@app.get("/api/search/", response_class=JSONResponse)
def search_patients(name: str, db: Session = Depends(get_db)):
    try:
        # البحث عن المرضى الذين يحتوي اسمهم على النص المحدد
        patients = db.query(Patient).filter(Patient.name.contains(name)).all()

        # تحويل قائمة كائنات المرضى إلى قائمة من القواميس باستخدام Pydantic
        patient_data = [PatientModel.from_orm(patient).dict() for patient in patients]

        # تحضير النتيجة النهائية
        response_data = {
            "success": True,
            "data": {"records": patient_data, "nums": len(patient_data)},
        }

        return JSONResponse(content=response_data)
    except Exception as e:
        raise e


# الحصول على مريض حسب المعرف
@app.get("/patients/{patient_id}", response_model=PatientModel)
def read_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


# وظيفة لتحديث بيانات مريض
@app.post("/update_web/{patient_id}", response_class=HTMLResponse)
async def update_web(
    request: Request,
    patient_id: int,
    name: Optional[str] = Form(default=None),
    date: Optional[str] = Form(default=None),
    details: Optional[str] = Form(default=None),
    rays: List[UploadFile] | None = None,
    db: Session = Depends(get_db),
):
    try:
        # جلب المريض من قاعدة البيانات باستخدام معرفه
        db_patient = db.query(Patient).filter(Patient.id == patient_id).first()

        # إذا لم يتم العثور على المريض، يتم رفع استثناء
        if not db_patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # تحديث الحقول المعدلة فقط
        if name is not None:
            db_patient.name = name
        if date is not None:
            db_patient.date = date
        if details is not None:
            db_patient.details = details

        # معالجة صور الأشعة الجديدة إذا تم رفعها
        if rays is not None and len(rays) > 0:
            new_images = []
            for ray_file in rays:
                if (
                    ray_file
                    and ray_file.filename
                    and ray_file.filename != ""
                    and ray_file.file
                ):
                    file_location = save_ray_image(ray_file)
                    new_images.append(file_location)

            # تحديث قائمة الصور إذا تم إضافة صور جديدة
            if new_images:
                db_patient.rays = new_images

        # حفظ التعديلات في قاعدة البيانات
        db.commit()
        db.refresh(db_patient)

        # إعادة توجيه المستخدم إلى الصفحة الرئيسية بعد التعديل
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        # في حالة حدوث خطأ، يتم إرجاع العمليات
        db.rollback()
        raise e

    finally:
        # إغلاق الاتصال بقاعدة البيانات
        db.close()


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
