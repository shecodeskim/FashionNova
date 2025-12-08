# users/forms.py
# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, SellerProfile

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False)
    user_type = forms.ChoiceField(
        choices=CustomUser.USER_TYPES,
        widget=forms.RadioSelect,
        initial='customer'
    )
    store_name = forms.CharField(
        max_length=100,
        required=False,
        label='Store Name',
        help_text='Required only if you are registering as a seller'
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'username',
            'email',
            'phone',
            'user_type',
            'password1',
            'password2'
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        store_name = cleaned_data.get('store_name')
        
        if user_type == 'seller' and not store_name:
            raise forms.ValidationError("Store name is required for sellers")
        
        return cleaned_data

class UserLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    
    class Meta:
        fields = ['username', 'password']

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'phone', 'address', 'profile_picture']