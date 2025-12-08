# users/views.py
# users/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import View
from .forms import UserRegisterForm, UserLoginForm, UserUpdateForm
from .models import SellerProfile

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # Create user
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email')
            user.phone = form.cleaned_data.get('phone')
            user.user_type = form.cleaned_data.get('user_type')
            user.save()
            
            # If user is seller, create seller profile
            if user.user_type == 'seller':
                store_name = form.cleaned_data.get('store_name')
                SellerProfile.objects.create(
                    user=user,
                    store_name=store_name,
                    business_registration='',
                    description=''
                )
            
            # Login user
            login(request, user)
            
            # Show success message
            if user.user_type == 'seller':
                messages.success(request, f'Your seller account has been created! Welcome to FashionNova!')
                return redirect('seller_dashboard')
            else:
                messages.success(request, f'Your account has been created! Welcome to FashionNova!')
                return redirect('home')
    else:
        form = UserRegisterForm()
    
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                
                # Redirect based on user type
                if user.user_type == 'seller':
                    return redirect('seller_dashboard')
                else:
                    return redirect('home')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()
    
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        form = UserUpdateForm(instance=request.user)
    
    return render(request, 'users/profile.html', {'form': form})