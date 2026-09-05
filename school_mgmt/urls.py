from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT Authentication Endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # Core API Endpoints
    path('api/', include('core.urls')),
    # Core Portal & System Web Endpoints
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# دائماً تقديم ملفات الوسائط (الشعارات) بغض النظر عن وضع DEBUG
# هذا تطبيق مكتبي محلي - لا يوجد خطر أمني من تقديم الميديا
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)