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
from sqlalchemy import create_engine
from sqlalchemy import desc

from sqlalchemy import JSON, Column, DateTime, Integer, String
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker,declarative_base

from patient_model import PatientModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
import sys
Base = declarative_base()
# إعداد قاعدة البيانات
DATABASE_URL = "sqlite:///./doctor.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# #  # تعريف نموذج المريض
# class Patient(Base):
#     # __tablename__ = "patients"
#     __tablename__ = "doctor"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, nullable=False, index=True)
#     details = Column(String, nullable=True)
#     rays = Column(String, nullable=True)  # Make sure this is defined in your model
#     date = Column(String, nullable=False)  # Change to Date if you have a Date type
#     createAt = Column(String, default=datetime.now)

#     def to_dict(self):
#         return {
#             "id": self.id,
#             "name": self.name,
#             "date": self.date,
#             "details": self.details,
#             "rays": self.rays,
#             "createAt": self.createAt

            
            
#         }
#     def __repr__(self):
#        return f"<Patient(id={self.id}, name={self.name}, date={self.date})>"

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()

class Patient(Base):
    __tablename__ = "doctor"

    id = Column(Integer, primary_key=True , index=True)
    name = Column(String, nullable=False, index=True)
    details = Column(String, nullable=True)
    rays = Column(String, nullable=True)
    date = Column(String, nullable=False)
    createAt = Column(String, default=lambda: datetime.now().isoformat())

    def to_dict(self):
        """Convert patient object to dictionary with proper handling of rays"""
        data = {
            "id": self.id,
            "name": self.name,
            "date": self.date,
            "details": self.details or "",
            "createAt": self.createAt
        }
        

    
        # Ensure rays is handled safely
        if self.rays:
            try:
                # Try to parse as JSON
                data["rays"] = json.loads(self.rays)
            except (json.JSONDecodeError, TypeError):
                # Handle cases where rays are not valid JSON
                data["rays"] = []
        else:
            data["rays"] = []
        
        return data




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

# إنشاء الجداول في قاعدة البيانات
def init_db():
    Base.metadata.create_all(bind=engine)
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






# إعداد التسجيل
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.post("/create_patient", response_class=HTMLResponse)
async def create_patient(
    request: Request,
    id: Optional[int] = Form(default=None),
    name: str = Form(...),
    date: Optional[str] = Form(default=None),
    details: Optional[str] = Form(default=None),
    rays: List[UploadFile] | None = Form(default=None),
    db: Session = Depends(get_db),
):
    logger.debug("=== بداية إضافة مريض جديد ===")
    logger.debug(f"الاسم: {name}")
    logger.debug(f"التاريخ: {date}")
    logger.debug(f"التفاصيل: {details}")
    logger.debug(f"الأشعة: {rays}")
    
    try:
        # معالجة التاريخ
        if date:
            try:
                patient_date = datetime.strptime(date, "%Y-%m-%d")
                logger.debug(f"تم تحويل التاريخ بنجاح: {patient_date}")
            except ValueError as e:
                logger.error(f"خطأ في تنسيق التاريخ: {e}")
                raise HTTPException(status_code=400, detail="تنسيق التاريخ غير صحيح")
        else:
            patient_date = datetime.now()
            logger.debug(f"تم استخدام تاريخ اليوم: {patient_date}")

        images = []
        
        # معالجة الصور
        if rays:
            logger.debug(f"عدد الملفات المرفقة: {len(rays)}")
            for ray_file in rays:
                if ray_file and ray_file.filename:
                    try:
                        file_location = save_ray_image(ray_file)
                        logger.debug(f"تم حفظ الصورة في: {file_location}")
                        images.append(file_location)
                    except Exception as e:
                        logger.error(f"خطأ في حفظ الصورة {ray_file.filename}: {str(e)}")
                        raise HTTPException(status_code=400, detail=f"خطأ في حفظ الصورة: {str(e)}")

        # إنشاء كائن المريض
        try:
               # الحصول على آخر ID
            last_patient = db.query(Patient).order_by(Patient.id.desc()).first()
            new_id = (last_patient.id + 1) if last_patient else 1
            db_patient = Patient(
                id=new_id,
                name=name,
                date=patient_date.strftime("%Y-%m-%d"),
                details=details,
                rays=json.dumps(images) if images else None,
                createAt=datetime.now().isoformat()
            )
            logger.debug("تم إنشاء كائن المريض بنجاح")
            
            # محاولة الحفظ في قاعدة البيانات
            db.add(db_patient)
            logger.debug("تم إضافة المريض إلى الجلسة")
            
            db.commit()
            logger.debug("تم حفظ البيانات بنجاح")
            
            db.refresh(db_patient)
            logger.debug(f"تم إنشاء المريض بنجاح. معرف المريض: {db_patient.id}")
            
            # التحقق من وجود البيانات
            check_patient = db.query(Patient).filter(Patient.id == db_patient.id).first()
            if check_patient:
                logger.debug(f"تم التأكد من وجود المريض في قاعدة البيانات. الاسم: {check_patient.name}")
            else:
                logger.error("لم يتم العثور على المريض في قاعدة البيانات بعد الإضافة!")

        except Exception as e:
            logger.error(f"خطأ في حفظ البيانات: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"خطأ في حفظ البيانات: {str(e)}")

        # إعادة التوجيه فقط إذا نجحت كل العمليات
        logger.debug("=== اكتملت العملية بنجاح ===")
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        logger.error(f"خطأ عام: {str(e)}")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.error("معلومات الخطأ الكاملة:", exc_info=(exc_type, exc_value, exc_traceback))
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("تم إغلاق اتصال قاعدة البيانات")
        
        
# إضافة مريض
# @app.post("/create_patient", response_class=HTMLResponse)
# async def create_patient(
#     request: Request,
#     name: str = Form(...),
#     date: Optional[datetime] = Form(default=None),
#     details: Optional[str] = Form(default=None),
#     rays: List[UploadFile] | None = None,
#     db: Session = Depends(get_db),
# ):
#     try:
#         print("rays:========> ", rays)
#         images = []

#         # تحقق من وجود صور الأشعة ومعالجتها إذا كانت موجودة
#         if rays is not None and len(rays) > 0:
#             for ray_file in rays:
#                 if (
#                     ray_file
#                     and ray_file.filename
#                     and ray_file.filename != ""
#                     and ray_file.file
#                 ):
#                     # تحديد مسار حفظ الصورة
#                     file_location = save_ray_image(ray_file)
#                     print("file_location: ", file_location)
#                     images.append(file_location)
#                     print("images:=======> ", images)

#         # إنشاء كائن المريض بعد إضافة جميع الصور
#         db_patient = Patient(
#             name=name,
#             # date=date,
#             date=(
#                 date.strftime("%Y-%m-%d")
#                 if date
#                 else datetime.now().strftime("%Y-%m-%d")
#             ),
#             details=details,
#             # rays  =images ,
#              rays=json.dumps(images) if images else None,
#             createAt=datetime.now().__str__(),
#         )

#         # حفظ المريض في قاعدة البيانات
#         db.add(db_patient)
#         db.commit()
#         db.refresh(db_patient)

#         # جلب قائمة المرضى لعرضها في الواجهة
#         get_patients(db=db)

#         # عرض الصفحة الرئيسية مع قائمة المرضى
#         return RedirectResponse(url="/", status_code=303)
#     except Exception as e:
#         # في حالة حدوث خطأ، يتم إرجاع العمليات
#         db.rollback()
#         raise e
#     finally:
#         # إغلاق الاتصال بقاعدة البيانات
#         db.close()


def save_ray_image(ray_file: UploadFile) -> str:
    directory = "images"
    if not os.path.exists(directory):
        os.makedirs(directory)

    file_location = f"{directory}/{ray_file.filename}"
    with open(file_location, "wb") as buffer:
        buffer.write(ray_file.file.read())
    print("file_location: ", file_location)

    return file_location

@app.get("/patients/", response_model=List[PatientModel])
def get_patients(db: Session = Depends(get_db)):
    try:
        # ترتيب حسب تاريخ الإنشاء تنازلياً (من الأحدث للأقدم)
        patients = (
            db.query(Patient)
            .order_by(desc(Patient.createAt))  # ترتيب تنازلي حسب تاريخ الإنشاء
            .offset(0)
            .limit(1000)
            .all()
        )

        # معالجة مسارات الصور
        for patient in patients:
            if patient.rays is not None:
                try:
                    cleaned_rays = patient.rays.strip('"\'')
                    rays_list = cleaned_rays.replace("[", "").replace("]", "").split(", ")
                    patient.rays = [ray.strip('"\'') for ray in rays_list if ray]
                except Exception as e:
                    logging.error(f"Error processing rays for patient {patient.id}: {str(e)}")
                    patient.rays = []
            else:
                patient.rays = []


        logging.info(f"Retrieved {len(patients)} patients")
        if patients:
            logging.debug(f"First patient data: {vars(patients[0])}")
        
        return patients

    except Exception as e:
        logging.error(f"Error retrieving patients: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# الحصول على جميع المرضى
# @app.get("/patients/", response_model=list[PatientModel])
# def get_patients(db: Session = Depends(get_db)):
#     try:
#         patients = db.query(Patient).order_by(desc(Patient.createAt) ).offset(0).limit(1000).all()
#         for patient in patients:
#             if patient.rays:
#                 patient.rays = patient.rays.replace("[", "").replace("]", "").split(", ")

#         print(vars(patients[0]))
#         return patients
#     except Exception as e:
#         raise e


# الحصول على جميع المرضى
@app.get("/api/get_all/", response_class=JSONResponse)
def get_patients_api(db: Session = Depends(get_db)):
    try:
        patients = db.query(Patient).offset(0).limit(1000).all()
        print("patients: ", patients)
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
        patient_data = [PatientModel.from_orm(patient).model_dump() for patient in patients]
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


# @app.get("/api/search/", response_class=JSONResponse)
# def search_patients(name: str, db: Session = Depends(get_db)):
#     try:
#         # البحث عن المرضى الذين يحتوي اسمهم على النص المحدد
#         patients = db.query(Patient).filter(Patient.name.contains(name)).all()

#         # تحويل قائمة كائنات المرضى إلى قائمة من القواميس باستخدام Pydantic
#         patient_data = [PatientModel.model_validate(patient).model_dump() for patient in patients]

#         # تحضير النتيجة النهائية
#         response_data = {
#             "success": True,
#             "data": {"records": patient_data, "nums": len(patient_data)},
#         }

#         return JSONResponse(content=response_data)
#     except Exception as e:
#         raise e


@app.get("/api/search/", response_class=JSONResponse)
async def search_patients(name: str, db: Session = Depends(get_db)):
    try:
        # البحث عن المرضى الذين يحتوي اسمهم على النص المحدد
        # patients = db.query(Patient).filter(Patient.name.contains(name)).all()
        patients = db.query(Patient).filter(Patient.name.ilike(f"%{name}%")).all()
        # patients = db.query(Patient).offset(0).limit(1000).all()
        for patient in patients:
            patient.rays = patient.rays.replace("[", "").replace("]", "").split(", ")

        # print(vars(patients[0]))

        # تحويل قائمة كائنات المرضى إلى قائمة من القواميس باستخدام Pydantic
       
        print('patients: ',len(patients))

        # تحضير النتيجة النهائية
        # response_data = {
        #     "success": True,
        #     "data":   [patient.to_dict() for patient in patients],
        #     "nums": len(patients)
        # }
        # print('response_data: ', repr(response_data))

        # return JSONResponse(content=[patient.to_dict() for patient in patients])
        return  patients
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


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
        patients  = db.query(Patient).all()
        print("delete patient======>: ",  len(patients))
        return RedirectResponse(url="/", status_code=303)
