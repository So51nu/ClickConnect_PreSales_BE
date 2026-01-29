from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from .models import BankType, BankCategory, LoanProduct
from .serializers import BankTypeSerializer, BankCategorySerializer, LoanProductSerializer
from rest_framework import viewsets, filters
from setup.models import UnitConfiguration
from .serializers import UnitConfigurationSerializer
class BankTypeViewSet(ModelViewSet):
    queryset = BankType.objects.all()
    serializer_class = BankTypeSerializer
    permission_classes = [IsAuthenticated]

class BankCategoryViewSet(ModelViewSet):
    queryset = BankCategory.objects.all()
    serializer_class = BankCategorySerializer
    permission_classes = [IsAuthenticated]

class LoanProductViewSet(ModelViewSet):
    queryset = LoanProduct.objects.all()
    serializer_class = LoanProductSerializer
    permission_classes = [IsAuthenticated]



class UnitConfigurationViewSet(viewsets.ModelViewSet):
    queryset = UnitConfiguration.objects.all().order_by("name")
    serializer_class = UnitConfigurationSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "code"]

    def get_queryset(self):
        qs = super().get_queryset()

        if "is_active" in self.request.query_params:
            val = self.request.query_params.get("is_active").lower()
            qs = qs.filter(is_active=(val == "true"))

        return qs


