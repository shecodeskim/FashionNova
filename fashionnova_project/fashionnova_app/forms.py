# fashionnova_app/forms.py
from django import forms
from .models import Product, Review, Order

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'discount_price', 'category', 
                 'brand', 'gender', 'stock', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your review here...'}),
        }

class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter your full address'}),
        required=True
    )
    phone = forms.CharField(max_length=15, required=True)
    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_CHOICES,
        widget=forms.RadioSelect
    )
    
class ProductFilterForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Categories"
    )
    brand = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Brands"
    )
    gender = forms.ChoiceField(
        choices=[('', 'All Genders')] + list(Product.GENDER_CHOICES),
        required=False
    )
    min_price = forms.DecimalField(required=False, decimal_places=2)
    max_price = forms.DecimalField(required=False, decimal_places=2)
    discount_only = forms.BooleanField(required=False, label='Discount Only')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Category, Brand
        self.fields['category'].queryset = Category.objects.all()
        self.fields['brand'].queryset = Brand.objects.all()