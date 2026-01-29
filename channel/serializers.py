# channel/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.utils import timezone

from .models import (
    AgentType,
    PartnerTier,
    CrmIntegration,
    ChannelPartnerProfile,
    ChannelPartnerProjectAuthorization,
    ChannelPartnerAttachment,
)

User = get_user_model()


# ---------- Master Serializers ----------

class AgentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentType
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class PartnerTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerTier
        fields = ['id', 'code', 'name', 'description', 'is_global', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class CrmIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrmIntegration
        fields = ['id', 'name', 'slug', 'api_base_url', 'auth_type', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


# ---------- Nested Read Serializers ----------

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested serialization"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields


class LeadSourceBasicSerializer(serializers.Serializer):
    """Basic lead source info for nested serialization"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    project_name = serializers.CharField(source='project.name', read_only=True)


# ---------- Project Authorization Serializers ----------

class ProjectAuthorizationSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = ChannelPartnerProjectAuthorization
        fields = ['id', 'project', 'project_name', 'start_date', 'end_date', 'status', 'created_at']
        read_only_fields = ['created_at']


class ProjectAuthorizationBulkUpdateSerializer(serializers.Serializer):
    """For bulk toggling projects"""
    project_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of project IDs to authorize"
    )
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=ChannelPartnerProjectAuthorization.status.field.choices,
        default='ACTIVE'
    )


# ---------- Attachment Serializers ----------

class AttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ChannelPartnerAttachment
        fields = ['id', 'file', 'file_url', 'file_type', 'description', 'created_at']
        read_only_fields = ['created_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


# ---------- Channel Partner Profile Serializers ----------

class ChannelPartnerProfileDetailSerializer(serializers.ModelSerializer):
    """For GET operations - includes all nested data"""
    referral_code = serializers.CharField(read_only=True)
    user = UserBasicSerializer(read_only=True)
    parent_agent = UserBasicSerializer(read_only=True)
    agent_type = AgentTypeSerializer(read_only=True)
    partner_tier = PartnerTierSerializer(read_only=True)
    crm_integration = CrmIntegrationSerializer(read_only=True)
    source = LeadSourceBasicSerializer(read_only=True)
    project_authorizations = ProjectAuthorizationSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    created_by_user = UserBasicSerializer(source='created_by', read_only=True)
    last_modified_by_user = UserBasicSerializer(source='last_modified_by', read_only=True)

    class Meta:
        model = ChannelPartnerProfile
        fields = [
            'id', 'user', 'source', 'parent_agent', 'agent_type', 'partner_tier',
            'crm_integration', 'mobile_number', 'address', 'pan_number', 'gst_in',
            'company_name', 'commission_text', 'rera_number', 'last_update_date',
            'program_start_date', 'program_end_date', 'enable_lead_sharing',
            'regulatory_compliance_approved', 'onboarding_status',
            'dedicated_support_contact_email', 'technical_setup_notes',
            'annual_revenue_target', 'q1_performance_text', 'status',
            'project_authorizations', 'attachments',
            'created_by_user', 'last_modified_by_user', 'last_modified_at',
            'created_at', 'updated_at',"referral_code", 
        ]
        read_only_fields = ['created_at', 'updated_at']


class ChannelPartnerProfileListSerializer(serializers.ModelSerializer):
    """For LIST operations - lightweight"""
    user = UserBasicSerializer(read_only=True)
    agent_type_name = serializers.CharField(source='agent_type.name', read_only=True)
    partner_tier_name = serializers.CharField(source='partner_tier.name', read_only=True)
    source_name = serializers.CharField(source='source.name', read_only=True)

    class Meta:
        model = ChannelPartnerProfile
        fields = [
            'id', 'user', 'source_name', 'agent_type_name', 'partner_tier_name',
            'mobile_number', 'company_name', 'onboarding_status', 'status',
            'created_at', 'updated_at'
        ]



from .models import ChannelPartnerProfile  # already imported hai

# ---- Mini serializer: dropdown / list ke liye ----

class ChannelPartnerMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ChannelPartnerProfile
        fields = [
            "id",
            "full_name",
            "email",
            "mobile_number",
            "company_name",
            "referral_code",
            "status",
        ]

    def get_full_name(self, obj):
        u = obj.user
        return u.get_full_name() or u.username or u.email




class ChannelPartnerQuickCreateSerializer(serializers.Serializer):
    """
    Minimal data to create a CP + authorize on one project.

    Required:
      - project_id
      - partner_tier_id
      - name
      - (email or mobile_number)

    Optional:
      - source_id (LeadSource.for_cp=True)
      - company_name
      - pan_number
      - rera_number
    """
    project_id = serializers.IntegerField()
    source_id = serializers.IntegerField(required=False, allow_null=True)

    partner_tier_id = serializers.IntegerField()   # 👈 compulsory

    name = serializers.CharField(max_length=255)
    email = serializers.EmailField(required=False, allow_blank=True)
    mobile_number = serializers.CharField(
        required=False, allow_blank=True, max_length=32
    )

    company_name = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    pan_number = serializers.CharField(
        required=False, allow_blank=True, max_length=32
    )
    rera_number = serializers.CharField(
        required=False, allow_blank=True, max_length=64
    )

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip()
        mobile = (attrs.get("mobile_number") or "").strip()

        if not email and not mobile:
            raise serializers.ValidationError(
                "At least one of email or mobile_number is required."
            )

        # partner_tier_id compulsory
        if not attrs.get("partner_tier_id"):
            raise serializers.ValidationError(
                {"partner_tier_id": "This field is required."}
            )

        return attrs







class ChannelPartnerCreateUpdateSerializer(serializers.Serializer):
    """
    For POST/PUT/PATCH operations - handles User + Profile creation/update.

    NOTE:
    - On create: email + password required. Email is used as username.
    - Duplicate email/username returns 400 with JSON error:
      {"email": ["A user with this email already exists."]}
    """
    referral_code = serializers.CharField(read_only=True)
    user_id = serializers.IntegerField(required=False, allow_null=True, help_text="Leave empty to create new user")
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    # Profile fields - Foreign Keys
    source_id = serializers.IntegerField(required=False, allow_null=True)
    parent_agent_id = serializers.IntegerField(required=False, allow_null=True)
    agent_type_id = serializers.IntegerField(required=False, allow_null=True)
    partner_tier_id = serializers.IntegerField(required=False, allow_null=True)
    crm_integration_id = serializers.IntegerField(required=False, allow_null=True)

    # Profile fields - Identity
    mobile_number = serializers.CharField(required=False, allow_blank=True, max_length=32)
    address = serializers.CharField(required=False, allow_blank=True)
    pan_number = serializers.CharField(required=False, allow_blank=True, max_length=32)
    gst_in = serializers.CharField(required=False, allow_blank=True, max_length=32)
    company_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    commission_text = serializers.CharField(required=False, allow_blank=True, max_length=255)
    rera_number = serializers.CharField(required=False, allow_blank=True, max_length=64)
    last_update_date = serializers.DateField(required=False, allow_null=True)

    # Profile fields - Program
    program_start_date = serializers.DateField(required=False, allow_null=True)
    program_end_date = serializers.DateField(required=False, allow_null=True)

    # Profile fields - Lead Management
    enable_lead_sharing = serializers.BooleanField(required=False, default=False)

    # Profile fields - Compliance
    regulatory_compliance_approved = serializers.BooleanField(required=False, default=False)

    # Profile fields - Operational
    onboarding_status = serializers.ChoiceField(
        choices=ChannelPartnerProfile.onboarding_status.field.choices,
        required=False,
        default='PENDING'
    )
    dedicated_support_contact_email = serializers.EmailField(required=False, allow_blank=True)
    technical_setup_notes = serializers.CharField(required=False, allow_blank=True)

    # Profile fields - Targets
    annual_revenue_target = serializers.DecimalField(
        required=False, allow_null=True, max_digits=14, decimal_places=2
    )
    q1_performance_text = serializers.CharField(required=False, allow_blank=True, max_length=100)

    # Profile fields - Status
    status = serializers.ChoiceField(
        choices=ChannelPartnerProfile.status.field.choices,
        required=False,
        default='ACTIVE'
    )

    # Project Authorization
    project_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of project IDs to authorize"
    )

    def validate(self, attrs):
        """
        - Enforce email + password required on create (when no user_id).
        - Enforce unique email/username for both create and update.
        """
        # For creation, email is required
        if not self.instance and not attrs.get('user_id'):
            if not attrs.get('email'):
                raise serializers.ValidationError({"email": "Email is required for new channel partner"})
            if not attrs.get('password'):
                raise serializers.ValidationError({"password": "Password is required for new user"})

        # Email uniqueness check for both create & update
        email = attrs.get('email')
        user_id = attrs.get('user_id')

        if email:
            qs = User.objects.filter(username=email)
            # For update, ignore current user
            if self.instance and self.instance.user_id:
                qs = qs.exclude(pk=self.instance.user_id)
            elif user_id:
                qs = qs.exclude(pk=user_id)

            if qs.exists():
                raise serializers.ValidationError(
                    {"email": "A user with this email already exists."}
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        current_user = request.user if request else None

        # Extract user data
        user_data = {
            'email': validated_data.pop('email', ''),
            'password': validated_data.pop('password', ''),
            'first_name': validated_data.pop('first_name', ''),
            'last_name': validated_data.pop('last_name', ''),
        }

        # Extract project_ids
        project_ids = validated_data.pop('project_ids', [])

        # ---------- Create user (email used as username) ----------
        try:
            user = User.objects.create_user(
                username=user_data['email'],
                email=user_data['email'],
                password=user_data['password'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
            )
        except IntegrityError:
            # DB-level uniqueness violation on username/email
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )

        # Set role to CHANNEL_PARTNER (adjust according to your User model)
        if hasattr(user, 'role'):
            user.role = 'CHANNEL_PARTNER'
            user.save()

        # Convert FK IDs to instances
        self._resolve_foreign_keys(validated_data)

        # Create profile
        profile = ChannelPartnerProfile.objects.create(
            user=user,
            created_by=current_user,
            last_modified_by=current_user,
            last_modified_at=timezone.now(),
            **validated_data
        )

        # Create project authorizations
        if project_ids:
            self._create_project_authorizations(profile, project_ids, current_user)

        return profile

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get('request')
        current_user = request.user if request else None

        # Update user if data provided
        user = instance.user

        # Email change (we already checked in validate, but double-safe here)
        if 'email' in validated_data:
            new_email = validated_data.pop('email')
            if User.objects.filter(username=new_email).exclude(pk=user.pk).exists():
                raise serializers.ValidationError(
                    {"email": "A user with this email already exists."}
                )
            user.email = new_email
            user.username = new_email

        if 'first_name' in validated_data:
            user.first_name = validated_data.pop('first_name')
        if 'last_name' in validated_data:
            user.last_name = validated_data.pop('last_name')
        if 'password' in validated_data:
            user.set_password(validated_data.pop('password'))

        try:
            user.save()
        except IntegrityError:
            # Just in case, catch DB uniqueness again
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )

        # Handle project authorizations
        project_ids = validated_data.pop('project_ids', None)
        if project_ids is not None:
            self._update_project_authorizations(instance, project_ids, current_user)

        # Convert FK IDs to instances
        self._resolve_foreign_keys(validated_data)

        # Update profile
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.last_modified_by = current_user
        instance.last_modified_at = timezone.now()
        instance.save()

        return instance

    def _resolve_foreign_keys(self, validated_data):
        """Convert ID fields to model instances"""
        from leadmanage.models import LeadSource

        if 'source_id' in validated_data:
            source_id = validated_data.pop('source_id')
            validated_data['source'] = LeadSource.objects.get(id=source_id) if source_id else None

        if 'parent_agent_id' in validated_data:
            parent_id = validated_data.pop('parent_agent_id')
            validated_data['parent_agent'] = User.objects.get(id=parent_id) if parent_id else None

        if 'agent_type_id' in validated_data:
            agent_type_id = validated_data.pop('agent_type_id')
            validated_data['agent_type'] = AgentType.objects.get(id=agent_type_id) if agent_type_id else None

        if 'partner_tier_id' in validated_data:
            tier_id = validated_data.pop('partner_tier_id')
            validated_data['partner_tier'] = PartnerTier.objects.get(id=tier_id) if tier_id else None

        if 'crm_integration_id' in validated_data:
            crm_id = validated_data.pop('crm_integration_id')
            validated_data['crm_integration'] = CrmIntegration.objects.get(id=crm_id) if crm_id else None

    def _create_project_authorizations(self, profile, project_ids, user):
        """Create project authorizations for given project IDs"""
        from clientsetup.models import Project

        for project_id in project_ids:
            try:
                project = Project.objects.get(id=project_id)
                ChannelPartnerProjectAuthorization.objects.get_or_create(
                    channel_partner=profile,
                    project=project,
                    defaults={
                        'status': 'ACTIVE',
                        'created_by': user
                    }
                )
            except Project.DoesNotExist:
                pass

    def _update_project_authorizations(self, profile, project_ids, user):
        """Update project authorizations - remove old, add new"""
        from clientsetup.models import Project

        # Remove authorizations not in the list
        profile.project_authorizations.exclude(project_id__in=project_ids).delete()

        # Add new authorizations
        for project_id in project_ids:
            try:
                project = Project.objects.get(id=project_id)
                ChannelPartnerProjectAuthorization.objects.get_or_create(
                    channel_partner=profile,
                    project=project,
                    defaults={
                        'status': 'ACTIVE',
                        'created_by': user
                    }
                )
            except Project.DoesNotExist:
                pass


class ChannelPartnerBulkCreateSerializer(serializers.Serializer):
    """For bulk creating multiple channel partners"""
    partners = ChannelPartnerCreateUpdateSerializer(many=True)

    def create(self, validated_data):
        partners_data = validated_data.get('partners', [])
        results = {
            'success': [],
            'failed': []
        }

        for idx, partner_data in enumerate(partners_data):
            try:
                serializer = ChannelPartnerCreateUpdateSerializer(
                    data=partner_data,
                    context=self.context
                )
                serializer.is_valid(raise_exception=True)
                profile = serializer.save()
                results['success'].append({
                    'index': idx,
                    'id': profile.id,
                    'email': profile.user.email
                })

            except serializers.ValidationError as e:
                # 👇 Proper JSON errors per partner
                results['failed'].append({
                    'index': idx,
                    'email': partner_data.get('email', 'N/A'),
                    'error': e.detail,
                })

            except IntegrityError as e:
                # Fallback, though create() already converts most IntegrityErrors
                results['failed'].append({
                    'index': idx,
                    'email': partner_data.get('email', 'N/A'),
                    'error': {
                        "non_field_errors": [f"Database integrity error: {str(e)}"]
                    },
                })

            except Exception as e:
                results['failed'].append({
                    'index': idx,
                    'email': partner_data.get('email', 'N/A'),
                    'error': {
                        "non_field_errors": [str(e)]
                    },
                })

        return results


class SectionUpdateSerializer(serializers.Serializer):
    """For updating specific sections of channel partner"""
    section = serializers.ChoiceField(choices=[
        'identity', 'program', 'product_auth', 'lead_mgmt',
        'compliance', 'operational', 'target', 'status'
    ])
    data = serializers.JSONField()

    def update(self, instance, validated_data):
        section = validated_data.get('section')
        data = validated_data.get('data', {})
        request = self.context.get('request')
        current_user = request.user if request else None

        if section == 'identity':
            self._update_identity(instance, data)
        elif section == 'program':
            self._update_program(instance, data)
        elif section == 'product_auth':
            self._update_product_auth(instance, data, current_user)
        elif section == 'lead_mgmt':
            self._update_lead_mgmt(instance, data)
        elif section == 'compliance':
            self._update_compliance(instance, data)
        elif section == 'operational':
            self._update_operational(instance, data)
        elif section == 'target':
            self._update_target(instance, data)
        elif section == 'status':
            self._update_status(instance, data)

        instance.last_modified_by = current_user
        instance.last_modified_at = timezone.now()
        instance.save()

        return instance

    def _update_identity(self, instance, data):
        # Update user
        user = instance.user
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            new_email = data['email']
            # Optional: duplicate check yahan bhi daal sakte ho if needed
            user.email = new_email
            user.username = new_email
        user.save()

        # Update profile identity fields
        identity_fields = [
            'mobile_number', 'address', 'pan_number', 'gst_in',
            'company_name', 'commission_text', 'rera_number'
        ]
        for field in identity_fields:
            if field in data:
                setattr(instance, field, data[field])

        # Handle FKs
        if 'agent_type_id' in data:
            instance.agent_type_id = data['agent_type_id']
        if 'parent_agent_id' in data:
            instance.parent_agent_id = data['parent_agent_id']
        if 'source_id' in data:
            instance.source_id = data['source_id']

    def _update_program(self, instance, data):
        if 'partner_tier_id' in data:
            instance.partner_tier_id = data['partner_tier_id']
        if 'program_start_date' in data:
            instance.program_start_date = data['program_start_date']
        if 'program_end_date' in data:
            instance.program_end_date = data['program_end_date']

    def _update_product_auth(self, instance, data, user):
        if 'project_ids' in data:
            from clientsetup.models import Project
            project_ids = data['project_ids']

            # Remove old authorizations
            instance.project_authorizations.exclude(project_id__in=project_ids).delete()

            # Add new ones
            for project_id in project_ids:
                try:
                    project = Project.objects.get(id=project_id)
                    ChannelPartnerProjectAuthorization.objects.get_or_create(
                        channel_partner=instance,
                        project=project,
                        defaults={'status': 'ACTIVE', 'created_by': user}
                    )
                except Project.DoesNotExist:
                    pass

    def _update_lead_mgmt(self, instance, data):
        if 'enable_lead_sharing' in data:
            instance.enable_lead_sharing = data['enable_lead_sharing']
        if 'crm_integration_id' in data:
            instance.crm_integration_id = data['crm_integration_id']

    def _update_compliance(self, instance, data):
        if 'regulatory_compliance_approved' in data:
            instance.regulatory_compliance_approved = data['regulatory_compliance_approved']

    def _update_operational(self, instance, data):
        if 'onboarding_status' in data:
            instance.onboarding_status = data['onboarding_status']
        if 'dedicated_support_contact_email' in data:
            instance.dedicated_support_contact_email = data['dedicated_support_contact_email']
        if 'technical_setup_notes' in data:
            instance.technical_setup_notes = data['technical_setup_notes']

    def _update_target(self, instance, data):
        if 'annual_revenue_target' in data:
            instance.annual_revenue_target = data['annual_revenue_target']
        if 'q1_performance_text' in data:
            instance.q1_performance_text = data['q1_performance_text']

    def _update_status(self, instance, data):
        if 'status' in data:
            instance.status = data['status']
