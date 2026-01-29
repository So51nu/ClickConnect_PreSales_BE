from django.contrib import admin
from .models import (
    ProjectType, TowerType, UnitType, Facing, ParkingType,
    BankType, BankCategory, LoanProduct,OfferingType,UnitConfiguration
)
admin.site.register([ProjectType, TowerType, UnitType, Facing, ParkingType, BankType, BankCategory, LoanProduct,OfferingType,UnitConfiguration])


