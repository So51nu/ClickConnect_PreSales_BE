from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BankTypeViewSet, BankCategoryViewSet, LoanProductViewSet
from .views import UnitConfigurationViewSet


router = DefaultRouter()
router.register(r'bank-types', BankTypeViewSet, basename='bank-type')
router.register(r'bank-categories', BankCategoryViewSet, basename='bank-category')
router.register(r'loan-products', LoanProductViewSet, basename='loan-product')
router.register("unit-configurations", UnitConfigurationViewSet)


urlpatterns = [path('', include(router.urls))]
