from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Brand, Product, Review, Category, CampusZone, University

from decimal import Decimal


class CustomerSignupForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'input-field', 'placeholder': 'your@email.com'}))
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Full Name'}))
    matric_number = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Matric / Registration Number (optional)'}))
    university = forms.ModelChoiceField(
        queryset=University.objects.filter(is_active=True),
        required=False, empty_label='-- Select your university (optional) --',
        widget=forms.Select(attrs={'class': 'input-field', 'id': 'id_university_customer'})
    )

    class Meta:
        model = User
        fields = ('first_name', 'email', 'matric_number', 'university', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.user_type = 'customer'
        user.matric_number = self.cleaned_data.get('matric_number', '')
        uni = self.cleaned_data.get('university')
        user.university = uni.name if uni else ''
        if commit:
            user.save()
        return user


class SellerSignupForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'input-field', 'placeholder': 'your@email.com'}))
    first_name = forms.CharField(max_length=100, label='Full Name', widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Full Name'}))
    matric_number = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Matric / Registration Number'}))
    university = forms.ModelChoiceField(
        queryset=University.objects.filter(is_active=True),
        required=True, empty_label='-- Select your university --',
        widget=forms.Select(attrs={'class': 'input-field', 'id': 'id_university_seller'})
    )
    student_id_image = forms.ImageField(label='Upload Student ID', widget=forms.FileInput(attrs={'class': 'input-field', 'accept': 'image/*'}))
    brand_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Your Store / Brand Name'}))
    brand_description = forms.CharField(widget=forms.Textarea(attrs={'class': 'input-field', 'rows': 3, 'placeholder': 'Describe your store...'}))

    class Meta:
        model = User
        fields = ('first_name', 'email', 'matric_number', 'university', 'student_id_image', 'brand_name', 'brand_description', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.user_type = 'seller'
        user.matric_number = self.cleaned_data['matric_number']
        uni = self.cleaned_data['university']
        user.university = uni.name if uni else ''
        if commit:
            user.save()
            if self.cleaned_data.get('student_id_image'):
                user.student_id_image = self.cleaned_data['student_id_image']
                user.save()
            Brand.objects.create(
                seller=user,
                name=self.cleaned_data['brand_name'],
                description=self.cleaned_data['brand_description'],
            )
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'class': 'input-field', 'placeholder': 'your@email.com', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input-field', 'placeholder': 'Password'}))


class SellerOnboardStep1Form(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ('business_category', 'business_type', 'website')
        widgets = {
            'business_category': forms.Select(choices=[
                ('', 'Select category'), ('fashion', 'Fashion & Apparel'),
                ('electronics', 'Electronics & Tech'), ('food', 'Food & Beverages'),
                ('beauty', 'Beauty & Personal Care'), ('home', 'Home & Living'),
                ('books', 'Books & Stationery'), ('art', 'Art & Crafts'), ('other', 'Other'),
            ], attrs={'class': 'input-field'}),
            'business_type': forms.Select(choices=[
                ('', 'Select type'), ('individual', 'Individual'),
                ('registered', 'Registered Business'), ('enterprise', 'Enterprise'),
            ], attrs={'class': 'input-field'}),
            'website': forms.URLInput(attrs={'class': 'input-field', 'placeholder': 'https://'}),
        }


class SellerOnboardStep2Form(forms.ModelForm):
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'input-field', 'placeholder': '+234 xxx xxx xxxx'}))

    class Meta:
        model = Brand
        fields = ('address', 'city', 'country', 'tax_id')
        widgets = {
            'address': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Street / Hostel Room'}),
            'city': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'City'}),
            'country': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Country'}),
            'tax_id': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'CAC / Tax ID (optional)'}),
        }


class SellerOnboardStep3Form(forms.ModelForm):
    class Meta:
        model = User
        fields = ('bank_name', 'account_number', 'account_holder_name', 'bank_code')
        widgets = {
            'bank_name': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'e.g. GTBank'}),
            'account_number': forms.TextInput(attrs={'class': 'input-field', 'placeholder': '10-digit account number'}),
            'account_holder_name': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Account holder name'}),
            'bank_code': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Bank code'}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('name', 'category', 'description', 'price', 'original_price',
                  'stock', 'image', 'shipping_info', 'warranty', 'return_policy', 'status')
        exclude = ('discount',)  # auto-calculated in Product.save()
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Product name'}),
            'category': forms.Select(attrs={'class': 'input-field'}),
            'description': forms.Textarea(attrs={'class': 'input-field', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'input-field', 'step': '0.01', 'placeholder': '0.00'}),
            'original_price': forms.NumberInput(attrs={'class': 'input-field', 'step': '0.01', 'placeholder': '0.00'}),
            'stock': forms.NumberInput(attrs={'class': 'input-field', 'placeholder': '0'}),
            'image': forms.FileInput(attrs={'class': 'input-field'}),
            'shipping_info': forms.TextInput(attrs={'class': 'input-field'}),
            'warranty': forms.TextInput(attrs={'class': 'input-field'}),
            'return_policy': forms.TextInput(attrs={'class': 'input-field'}),
            'status': forms.Select(attrs={'class': 'input-field'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # category is optional — seller may not have any categories set up yet
        self.fields['category'].required = False
        self.fields['category'].empty_label = 'No category (optional)'
        # original_price is optional — defaults to price if blank
        self.fields['original_price'].required = False
        self.fields['description'].required = False
        self.fields['image'].required = False
        self.fields['shipping_info'].required = False
        self.fields['warranty'].required = False
        self.fields['return_policy'].required = False


class BrandProfileForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ('name', 'description', 'logo', 'whatsapp', 'instagram', 'twitter', 'tiktok', 'location')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-field'}),
            'description': forms.Textarea(attrs={'class': 'input-field', 'rows': 3}),
            'logo': forms.FileInput(attrs={'class': 'input-field'}),
            'whatsapp': forms.TextInput(attrs={'class': 'input-field', 'placeholder': '+234...'}),
            'instagram': forms.TextInput(attrs={'class': 'input-field', 'placeholder': '@handle'}),
            'twitter': forms.TextInput(attrs={'class': 'input-field', 'placeholder': '@handle'}),
            'tiktok': forms.TextInput(attrs={'class': 'input-field', 'placeholder': '@handle'}),
            'location': forms.TextInput(attrs={'class': 'input-field', 'placeholder': 'Lagos, Nigeria'}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('rating', 'text')
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} Star{"s" if i>1 else ""}') for i in range(1, 6)], attrs={'class': 'input-field'}),
            'text': forms.Textarea(attrs={'class': 'input-field', 'rows': 4, 'placeholder': 'Share your experience...'}),
        }


class CheckoutForm(forms.Form):
    phone = forms.CharField(
        max_length=20, required=True,
        widget=forms.TextInput(attrs={
            'class': 'input-field', 'placeholder': '+234 xxx xxx xxxx',
            'id': 'id_phone', 'type': 'tel'
        })
    )
    delivery_zone = forms.ModelChoiceField(
        queryset=CampusZone.objects.filter(is_active=True),
        required=True, empty_label='-- Select your delivery zone --',
        widget=forms.Select(attrs={'class': 'input-field', 'id': 'id_delivery_zone'})
    )
    delivery_address = forms.CharField(
        max_length=300, required=True,
        widget=forms.TextInput(attrs={
            'class': 'input-field', 'id': 'id_delivery_address',
            'placeholder': 'Room / block number, hostel name or landmark'
        })
    )
    delivery_lat = forms.DecimalField(required=False, max_digits=10, decimal_places=7,
        widget=forms.HiddenInput(attrs={'id': 'id_delivery_lat'}))
    delivery_lng = forms.DecimalField(required=False, max_digits=10, decimal_places=7,
        widget=forms.HiddenInput(attrs={'id': 'id_delivery_lng'}))
    runner_note = forms.CharField(
        max_length=300, required=False,
        widget=forms.Textarea(attrs={'class': 'input-field', 'rows': 2, 'placeholder': 'Any notes for the runner? (optional)'})
    )

    def __init__(self, *args, campus_zones=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if campus_zones is not None:
            self.fields['delivery_zone'].queryset = campus_zones
        # Pre-fill phone from user profile
        if user and user.phone:
            self.fields['phone'].initial = user.phone


class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('500'),
        widget=forms.NumberInput(attrs={'class': 'input-field', 'placeholder': 'Amount (min ₦500)', 'step': '0.01'})
    )