# setup/models
from django.db import models
from django.core.validators import RegexValidator
from django.utils.text import slugify

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
class NamedLookup(TimeStamped):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        validators=[RegexValidator(r"^[A-Z0-9_]+$", "Use only A–Z, 0–9 and _")],
        help_text="Stable programmatic code, e.g. RESIDENTIAL, MIXED_USE",
    )
    is_active = models.BooleanField(default=True)
    class Meta:
        abstract = True
        ordering = ["name"]
    def __str__(self):
        return self.name
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name or "").replace("-", "_").upper()
        else:
            self.code = self.code.strip().replace("-", "_").upper()
        super().save(*args, **kwargs)

class ProjectType(NamedLookup): pass
class TowerType(NamedLookup): pass
class UnitType(NamedLookup): pass
class Facing(NamedLookup): pass
class ParkingType(NamedLookup): pass
class UnitConfiguration(NamedLookup):pass
class BankType(NamedLookup): pass
class BankCategory(NamedLookup): pass
class LoanProduct(NamedLookup): pass
class MilestoneStatus(NamedLookup): pass
class OfferingType(NamedLookup):pass
class VisitingHalf(NamedLookup): pass
class FamilySize(NamedLookup):pass
class ResidencyOwnerShip(NamedLookup):pass
class PossienDesigned(NamedLookup):pass
class Occupation(NamedLookup):pass
class Designation(NamedLookup):pass