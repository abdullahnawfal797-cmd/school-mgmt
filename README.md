# School Management System (Backend API)

نظام إدارة مدرسية متكامل مبني باستخدام:
- **Python 3.11** / **Django 4.2+**
- **Django REST Framework (DRF)**
- **JWT Authentication** (SimpleJWT)
- **PostgreSQL 15**
- **Redis 7** & **Celery**
- **Docker** & **Docker Compose**

---

## 🚀 التشغيل السريع باستخدام Docker (Quickstart with Docker)

```bash
docker-compose up --build
```

سيتم تشغيل الخدمات التالية تلقائياً:
* خادم الويب وواجهات الـ API: `http://localhost:8000/`
* قاعدة البيانات PostgreSQL: المنفذ `5432`
* وسيط الرسائل Redis: المنفذ `6379`
* عامل المهام الخلفية Celery Worker

### إنشاء حساب المشرف (Superuser):
```bash
docker-compose exec web python manage.py createsuperuser
```

---

## 🔑 المصادقة والحسابات (JWT Authentication)

| الطريقة (Method) | المسار (Endpoint) | الوصف |
| :--- | :--- | :--- |
| `POST` | `/api/token/` | تسجيل الدخول واستخراج (Access & Refresh Tokens) |
| `POST` | `/api/token/refresh/` | تجديد التوكن عند انتهاء الصلاحية |
| `POST` | `/api/token/verify/` | التحقق من صحة التوكن |

**ملاحظة**: يجب إرسال التوكن في الـ Header لكل طلب محمي:
```
Authorization: Bearer <your_access_token>
```

---

## 📚 واجهات برمجة التطبيقات (API Endpoints)

| المسار | النموذج | العمليات المتاحة |
| :--- | :--- | :--- |
| `/api/users/` | المستخدمين | `GET`, `POST`, `GET /me/` |
| `/api/parents/` | أولياء الأمور | CRUD كامل + بحث |
| `/api/teachers/` | المعلمين | CRUD كامل + بحث بالاسم والمواد |
| `/api/classes/` | الفصول الدراسية | CRUD كامل + عرض الشعب المندرجة |
| `/api/sections/` | الشعب الدراسية | CRUD كامل + تصفية بالفصل `?school_class=ID` |
| `/api/students/` | الطلاب | CRUD + تصفية بالفصل والشعبة + `GET /{id}/grades/` + `GET /{id}/attendance/` |
| `/api/enrollments/` | قيود وتسجيل الطلاب | CRUD كامل |
| `/api/subjects/` | المواد الدراسية | CRUD كامل |
| `/api/attendance/` | الحضور والغياب | CRUD + تصفية `?student=ID&date=YYYY-MM-DD` + `POST /bulk_record/` |
| `/api/grades/` | الدرجات والنتائج | CRUD + تصفية بالطالب والمادة والفصل |
| `/api/timetable/` | الجداول المدرسية | CRUD + تصفية بالفصل والمعلم واليوم |
| `/api/invoices/` | الفواتير والرسوم | CRUD + `POST /{id}/mark_as_paid/` + `POST /{id}/send_reminder/` |

---

## ⚡ المهام الخلفية (Celery Tasks)

* **`send_absence_notification`**: إرسال تنبيه آلي لولي الأمر عند تسجيل غياب الطالب.
* **`send_invoice_reminder`**: جدولة تنبيه لسداد الفواتير المستحقة.
* **`generate_monthly_attendance_summary`**: تجميع إحصائيات الحضور والغياب الشهرية.
