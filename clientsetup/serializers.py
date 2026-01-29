from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import (
    Project, Tower, Floor, FloorDocument, Unit,
    MilestonePlan, MilestoneSlab,
    ProjectStatus, ApprovalStatus, FloorStatus, UnitStatus, MilestonePlanStatus, CalcMode
)
from accounts.models import Role

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    # write-only helper when staff creates: which admin owns this project
    admin_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    total_inventory = serializers.IntegerField(read_only=True)  # 👈 new

    class Meta:
        model = Project
        fields = [
            "id", "name", "location", "developer", "rera_no",
            "start_date", "end_date", "possession_date","is_pricing_balcony_carpert",
            "project_type", "status", "approval_status", "notes",
            "belongs_to",   # read-only via output (we set it), but allow read expose
            "admin_id",     # write-only input helper
            "total_inventory","price_per_sqft","is_pricing_balcony_carpert"
        ]
        read_only_fields = ["id", "belongs_to", "total_inventory"]

    def validate(self, data):
        req = self.context["request"]
        user: User = req.user
        admin_id = data.pop("admin_id", None)  # consume here; we'll use in create()

        # Staff: must supply admin_id (points to an ADMIN)
        if user.is_staff:
            if not admin_id:
                raise serializers.ValidationError("admin_id is required when staff creates a project.")
            try:
                admin_user = User.objects.get(id=admin_id, role=Role.ADMIN)
            except User.DoesNotExist:
                raise serializers.ValidationError("admin_id must refer to a valid ADMIN user.")
            # stash resolved admin on serializer instance for create()
            self._resolved_admin = admin_user

        # Admin: belongs_to will be the requester, ignore any admin_id
        elif getattr(user, "role", None)in(Role.ADMIN,Role.FULL_CONTROL):
            self._resolved_admin = user

        else:
            raise serializers.ValidationError("Only staff or admin users can create projects.")

        # Date validations mirrored from model (kept defensive)
        sd, ed, pd = data.get("start_date"), data.get("end_date"), data.get("possession_date")
        if sd and ed and sd > ed:
            raise serializers.ValidationError("Start date cannot be after end date.")
        if ed and pd and ed > pd:
            raise serializers.ValidationError("End date cannot be after possession date.")

        return data

    def create(self, validated_data):
        # Inject belongs_to decided in validate()
        validated_data["belongs_to"] = self._resolved_admin
        return super().create(validated_data)


class TowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tower
        fields = ["id", "project", "name", "tower_type", "total_floors", "status", "notes"]
        read_only_fields = ["id"]

    def validate(self, data):
        req = self.context["request"]
        user: User = req.user
        project = data.get("project") or getattr(self.instance, "project", None)

        if not project:
            return data

        # Staff can operate on any; Admin only on own projects
        if not user.is_staff and getattr(user, "role", None) == Role.ADMIN:
            if project.belongs_to_id != user.id:
                raise serializers.ValidationError("Admins can only manage towers of their own projects.")
        elif not user.is_staff and getattr(user, "role", None) != Role.ADMIN:
            raise serializers.ValidationError("Insufficient permission.")
        return data


class FloorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Floor
        fields = ["id", "tower", "number", "total_units", "status", "notes"]
        read_only_fields = ["id"]

    def validate(self, data):
        req = self.context["request"]
        user: User = req.user
        tower = data.get("tower") or getattr(self.instance, "tower", None)
        if not tower:
            return data

        project_admin_id = tower.project.belongs_to_id
        if user.is_staff:
            return data
        if getattr(user, "role", None) == Role.ADMIN and Role.FULL_CONTROL and user.id == project_admin_id:
            return data
        raise serializers.ValidationError("Insufficient permission for this tower.")


class FloorDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FloorDocument
        fields = ["id", "floor", "file", "created_at"]
        read_only_fields = ["id", "created_at"]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = [
            "id", "project", "tower", "floor", "unit_no",
            "unit_type", "carpet_sqft", "builtup_sqft", "rera_sqft",
            "facing", "parking_type", "agreement_value",
            "construction_start", "completion_date",
            "status", "notes",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        # Relationship consistency
        project = data.get("project") or getattr(self.instance, "project", None)
        tower = data.get("tower") or getattr(self.instance, "tower", None)
        floor = data.get("floor") or getattr(self.instance, "floor", None)

        if project and tower and tower.project_id != project.id:
            raise serializers.ValidationError("Tower does not belong to the given project.")
        if floor and tower and floor.tower_id != tower.id:
            raise serializers.ValidationError("Floor does not belong to the given tower.")

        # Permissions
        req = self.context["request"]
        user: User = req.user
        if user.is_staff:
            return data
        if getattr(user, "role", None) == Role.ADMIN and project and project.belongs_to_id == user.id:
            return data
        raise serializers.ValidationError("Insufficient permission for this project.")



class MilestoneSlabSerializer(serializers.ModelSerializer):
    # yaha required = True -> standalone API me plan dena compulsory
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=MilestonePlan.objects.all(),
        source="plan",
        write_only=True,
    )
    plan = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = MilestoneSlab
        fields = [
            "id",
            "plan_id",   # input (required)
            "plan",      # output
            "order_index",
            "name",
            "percentage",
            "amount",
            "remarks",
        ]



class MilestoneSlabNestedSerializer(serializers.ModelSerializer):
    """
    Ye sirf MilestonePlan ke nested slabs ke liye use hoga.
    Yaha plan_id nahi chahiye – parent plan se link hoga.
    """
    class Meta:
        model = MilestoneSlab
        fields = ["id", "order_index", "name", "percentage", "amount", "remarks"]
        read_only_fields = ["id"]



class MilestonePlanSerializer(serializers.ModelSerializer):
    # Nested slabs – yaha wala serializer USE karo
    slabs = MilestoneSlabNestedSerializer(many=True, required=False)

    class Meta:
        model = MilestonePlan
        fields = [
            "id",
            "project", "tower",
            "name",
            "start_date", "end_date",
            "responsible_user",
            "calc_mode", "amount",
            "enable_pg_integration",
            "verified_by", "verified_date",
            "status",
            "notes",
            "slabs",                 # nested
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        """
        Model.clean() bhi chalega, par yaha basic validation repeat karna safe hai.
        """
        start_date = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        calc_mode = attrs.get("calc_mode") or getattr(self.instance, "calc_mode", None)
        amount = attrs.get("amount") if "amount" in attrs else getattr(self.instance, "amount", None)
        status = attrs.get("status") or getattr(self.instance, "status", None)
        verified_by = attrs.get("verified_by") or getattr(self.instance, "verified_by", None)
        verified_date = attrs.get("verified_date") or getattr(self.instance, "verified_date", None)

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Milestone start date cannot be after end date.")
        if status == MilestonePlanStatus.LOCKED and not (verified_by and verified_date):
            raise serializers.ValidationError("Locked plans must have Verified By and Verified Date.")

        if calc_mode == CalcMode.AMOUNT and amount is None:
            raise serializers.ValidationError("Amount is required in amount mode.")
        if calc_mode == CalcMode.PERCENTAGE and amount:
            raise serializers.ValidationError("Do not set amount in percentage mode.")

        return attrs

    def create(self, validated_data):
        slabs_data = validated_data.pop("slabs", [])
        plan = MilestonePlan.objects.create(**validated_data)

        for idx, s in enumerate(slabs_data, start=1):
            if not s.get("order_index"):
                s["order_index"] = idx
            MilestoneSlab.objects.create(plan=plan, **s)

        return plan

    def update(self, instance, validated_data):
        slabs_data = validated_data.pop("slabs", None)
        plan = super().update(instance, validated_data)

        if slabs_data is not None:
            plan.slabs.all().delete()
            for idx, s in enumerate(slabs_data, start=1):
                if not s.get("order_index"):
                    s["order_index"] = idx
                MilestoneSlab.objects.create(plan=plan, **s)

        return plan






from setup.models import LoanProduct
from .models import (
    PaymentPlan, PaymentSlab,
    Bank, BankBranch, ProjectBank, ProjectBankProduct,
    Notification, NotificationDispatchLog,
    ProjectBankStatus, NotificationType, NotificationPriority, DeliveryMethod, ReadStatus, RowStatus
)

# -------- Payment --------
class PaymentSlabSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentSlab
        fields = ["id", "plan", "order_index", "name", "percentage", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class PaymentPlanSerializer(serializers.ModelSerializer):
    slabs = PaymentSlabSerializer(many=True, read_only=True)
    total_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = PaymentPlan
        fields = ["id", "code", "name", "project", "slabs", "total_percentage", "created_at", "updated_at"]
        read_only_fields = ["id", "slabs", "total_percentage", "created_at", "updated_at"]

    def validate(self, data):
        # staff can create for any project; admin only for own project
        req = self.context["request"]
        user = req.user
        project = data.get("project") or getattr(self.instance, "project", None)
        if user.is_staff:
            return data
        if getattr(user, "role", None) == Role.ADMIN and project and project.belongs_to_id == user.id:
            return data
        raise serializers.ValidationError("Insufficient permission for this project.")


# -------- Bank Setup --------
class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = ["id", "code", "name", "bank_type", "bank_category", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class BankBranchSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source="bank.name", read_only=True)
    class Meta:
        model = BankBranch
        fields = [
            "id", "bank", "bank_name", "branch_name", "branch_code",
            "ifsc", "micr", "address", "contact_name", "contact_phone", "contact_email",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "bank_name", "created_at", "updated_at"]

class ProjectBankProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectBankProduct
        fields = ["id", "project_bank", "product", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class ProjectBankSerializer(serializers.ModelSerializer):
    # Accept list of loan product ids
    product_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    products = serializers.SerializerMethodField(read_only=True)

    def get_products(self, obj):
        return [{"id": pb.product_id, "name": pb.product.name} for pb in obj.products.select_related("product")]

    class Meta:
        model = ProjectBank
        fields = ["id", "project", "bank_branch", "apf_number", "status", "product_ids", "products", "created_at", "updated_at"]
        read_only_fields = ["id", "products", "created_at", "updated_at"]

    def validate(self, data):
        req = self.context["request"]
        user = req.user
        project = data.get("project") or getattr(self.instance, "project", None)
        if user.is_staff:
            return data
        if getattr(user, "role", None) == Role.ADMIN and project and project.belongs_to_id == user.id:
            return data
        raise serializers.ValidationError("Insufficient permission for this project.")

    def create(self, validated_data):
        product_ids = validated_data.pop("product_ids", [])
        obj = super().create(validated_data)
        if product_ids:
            for pid in product_ids:
                ProjectBankProduct.objects.get_or_create(project_bank=obj, product_id=pid)
        return obj

    def update(self, instance, validated_data):
        product_ids = validated_data.pop("product_ids", None)
        obj = super().update(instance, validated_data)
        if product_ids is not None:
            obj.products.all().delete()
            for pid in product_ids:
                ProjectBankProduct.objects.get_or_create(project_bank=obj, product_id=pid)
        return obj


# -------- Notifications --------
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "code", "project", "user", "notif_type", "message",
            "priority", "delivery_method", "scheduled_at", "expires_on",
            "read_status", "status", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "read_status", "created_at", "updated_at"]

    def validate(self, data):
        req = self.context["request"]
        u = req.user
        proj = data.get("project") or getattr(self.instance, "project", None)
        # staff can create any; admin only for own project/team
        if u.is_staff:
            return data
        if getattr(u, "role", None) == Role.ADMIN:
            if proj and proj.belongs_to_id != u.id:
                raise serializers.ValidationError("Admins can only create notifications for their own projects.")
            return data
        raise serializers.ValidationError("Insufficient permission.")

class NotificationDispatchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDispatchLog
        fields = ["id", "notification", "attempt_no", "channel", "sent_at", "success", "response_meta"]
        read_only_fields = ["id", "sent_at"]


