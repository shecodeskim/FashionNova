# fashionnova_app/views.py
# fashionnova_app/views.py - Update the imports section
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json
import requests
import time  # Add this import
from django.conf import settings
from .models import *
from .forms import *
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Avg, Q
from datetime import datetime, timedelta
from django.utils import timezone  


def home(request):
    featured_products = Product.objects.filter(is_active=True).order_by('-created_at')[:8]
    discounted_products = Product.objects.filter(
        discount_price__isnull=False, 
        is_active=True
    ).order_by('-created_at')[:6]
    categories = Category.objects.all()[:6]
    
    context = {
        'featured_products': featured_products,
        'discounted_products': discounted_products,
        'categories': categories,
    }
    return render(request, 'home.html', context)

def products(request):
    products_list = Product.objects.filter(is_active=True)
    
    # Filtering
    form = ProductFilterForm(request.GET)
    if form.is_valid():
        category = form.cleaned_data.get('category')
        brand = form.cleaned_data.get('brand')
        gender = form.cleaned_data.get('gender')
        min_price = form.cleaned_data.get('min_price')
        max_price = form.cleaned_data.get('max_price')
        discount_only = form.cleaned_data.get('discount_only')
        
        if category:
            products_list = products_list.filter(category=category)
        if brand:
            products_list = products_list.filter(brand=brand)
        if gender:
            products_list = products_list.filter(gender=gender)
        if min_price:
            products_list = products_list.filter(price__gte=min_price)
        if max_price:
            products_list = products_list.filter(price__lte=max_price)
        if discount_only:
            products_list = products_list.filter(discount_price__isnull=False)
    
    # Sorting
    sort = request.GET.get('sort', 'newest')
    if sort == 'price_low':
        products_list = products_list.order_by('price')
    elif sort == 'price_high':
        products_list = products_list.order_by('-price')
    elif sort == 'discount':
        products_list = products_list.filter(discount_price__isnull=False).order_by('-discount_price')
    else:  # newest
        products_list = products_list.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products_list, 12)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    context = {
        'products': products_page,
        'form': form,
        'sort': sort,
    }
    return render(request, 'products.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    reviews = product.reviews.all().order_by('-created_at')
    
    # Check if user has reviewed
    user_review = None
    if request.user.is_authenticated:
        try:
            user_review = Review.objects.get(product=product, user=request.user)
        except Review.DoesNotExist:
            pass
    
    # Related products
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True
    ).exclude(id=product.id)[:4]
    
    # Check wishlist
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()
    
    # Check cart
    in_cart = False
    cart_quantity = 0
    if request.user.is_authenticated:
        try:
            cart_item = Cart.objects.get(user=request.user, product=product)
            in_cart = True
            cart_quantity = cart_item.quantity
        except Cart.DoesNotExist:
            pass
    
    context = {
        'product': product,
        'reviews': reviews,
        'user_review': user_review,
        'related_products': related_products,
        'in_wishlist': in_wishlist,
        'in_cart': in_cart,
        'cart_quantity': cart_quantity,
    }
    return render(request, 'product_detail.html', context)

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{product.name} added to cart!')
    return redirect('cart')

@login_required
def remove_from_cart(request, cart_id):
    cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
    cart_item.delete()
    messages.success(request, 'Item removed from cart!')
    return redirect('cart')

@login_required
def update_cart_quantity(request):
    if request.method == 'POST':
        cart_id = request.POST.get('cart_id')
        quantity = int(request.POST.get('quantity', 1))
        
        cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
        
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required
def cart(request):
    cart_items = Cart.objects.filter(user=request.user)
    
    # Calculate totals
    subtotal = sum(item.get_total_price() for item in cart_items)
    shipping_fee = 200 if cart_items.exists() else 0  # Example flat rate
    total = subtotal + shipping_fee
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_fee': shipping_fee,
        'total': total,
    }
    return render(request, 'cart.html', context)

@login_required
def checkout(request):
    cart_items = Cart.objects.filter(user=request.user)
    if not cart_items.exists():
        messages.warning(request, 'Your cart is empty!')
        return redirect('cart')
    
    # Calculate totals
    subtotal = sum(item.get_total_price() for item in cart_items)
    shipping_fee = 200  # Example flat rate
    total = subtotal + shipping_fee
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Create order
            order = Order.objects.create(
                user=request.user,
                order_number = f"ORD-{request.user.id}-{int(timezone.now().timestamp())}",
                shipping_address=form.cleaned_data['shipping_address'],
                phone=form.cleaned_data['phone'],
                payment_method=form.cleaned_data['payment_method'],
                subtotal=subtotal,
                shipping_fee=shipping_fee,
                total=total,
            )
            
            # Create order items
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.get_final_price()
                )
            
            # Clear cart
            cart_items.delete()
            
            # Process payment
            if form.cleaned_data['payment_method'] == 'mpesa':
                return redirect('process_mpesa_payment', order_id=order.id)
            else:
                messages.success(request, 'Order placed successfully!')
                return redirect('order_detail', order_id=order.id)
    else:
        initial_data = {
            'phone': request.user.phone if request.user.phone else '',
            'shipping_address': request.user.address if request.user.address else '',
        }
        form = CheckoutForm(initial=initial_data)
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_fee': shipping_fee,
        'total': total,
    }
    return render(request, 'checkout.html', context)

@login_required
def wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user)
    return render(request, 'wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )
    if created:
        messages.success(request, f'{product.name} added to wishlist!')
    else:
        messages.info(request, f'{product.name} is already in your wishlist!')
    return redirect('wishlist')

@login_required
def remove_from_wishlist(request, wishlist_id):
    wishlist_item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    wishlist_item.delete()
    messages.success(request, 'Item removed from wishlist!')
    return redirect('wishlist')

@login_required
def move_to_cart(request, wishlist_id):
    wishlist_item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    
    # Add to cart
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=wishlist_item.product,
        defaults={'quantity': 1}
    )
    
    # Remove from wishlist
    wishlist_item.delete()
    
    messages.success(request, f'{wishlist_item.product.name} moved to cart!')
    return redirect('cart')

@login_required
def orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders.html', {'orders': orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_detail.html', {'order': order})

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status in ['pending', 'processing']:
        order.status = 'cancelled'
        order.save()
        messages.success(request, 'Order cancelled successfully!')
    else:
        messages.error(request, 'Cannot cancel order at this stage!')
    return redirect('order_detail', order_id=order_id)

@login_required
def seller_dashboard(request):
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied!')
        return redirect('home')
    
    try:
        seller_profile = SellerProfile.objects.get(user=request.user)
        products = Product.objects.filter(seller=seller_profile)
        
        # Get statistics
        total_products = products.count()
        active_products = products.filter(is_active=True).count()
        
        # Get orders for seller's products
        order_items = OrderItem.objects.filter(product__seller=seller_profile)
        total_sales = sum(item.get_total() for item in order_items)
        
        context = {
            'seller_profile': seller_profile,
            'products': products,
            'total_products': total_products,
            'active_products': active_products,
            'total_sales': total_sales,
        }
        return render(request, 'sellersdashboard.html', context)
    except SellerProfile.DoesNotExist:
        messages.error(request, 'Seller profile not found!')
        return redirect('home')

@login_required
def add_product(request):
    """View to add new product - connects to products.html"""
    if request.method == 'POST':
        form = ProductForm()
        if form.is_valid():
            form.save()
            messages.success(request, 'product added successfully')
            return redirect('products')
        else:
           
            messages.error(request, 'product did not add successfully')
    else:
        form = ProductForm()
    return render (request, 'add_product.html', {'form':form})
    '''if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            stock = request.POST.get('stock', 0)
            
            # Handle category
            category_id = request.POST.get('category')
            category = None
            if category_id and category_id.isdigit():
                try:
                    category = Category.objects.get(id=int(category_id))
                except Category.DoesNotExist:
                    pass
            
            # If no category selected, create a default one
            if not category:
                category, created = Category.objects.get_or_create(
                    name='General',
                    defaults={'is_active': True}
                )
            
            # Handle brand
            brand_id = request.POST.get('brand')
            brand = None
            if brand_id and brand_id.isdigit():
                try:
                    brand = Brand.objects.get(id=int(brand_id))
                except Brand.DoesNotExist:
                    pass
            
            # Create product
            product = Product.objects.create(
                seller=request.user,
                name=name,
                description=description,
                category=category,
                brand=brand,
                price=price,
                discount_price=request.POST.get('discount_price') or None,
                stock=stock,
                gender=request.POST.get('gender', 'U'),
                is_active=request.POST.get('is_active') == 'on',
                is_featured=request.POST.get('is_featured') == 'on',
                is_new=request.POST.get('is_new') == 'on',
                low_stock_threshold=request.POST.get('low_stock_threshold', 10),
            )
            
            # Handle image upload
            if 'main_image' in request.FILES:
                product.image = request.FILES['main_image']
                product.save()
            
            messages.success(request, f'Product "{name}" has been published successfully!')
            
            # Redirect to products page where the new product will be visible
            return redirect('products')
            
        except Exception as e:
            messages.error(request, f'Error creating product: {str(e)}')
            return redirect('add_product')
    
    # GET request - show form
    # Get existing categories and brands for dropdowns
    categories = Category.objects.filter(is_active=True).order_by('name')
    brands = Brand.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'add_product.html', {
        'categories': categories,
        'brands': brands,
    })'''

def products_view(request):
    """View to display all products - shows published products"""
    # Get all active products (including newly published ones)
    products_list = Product.objects.filter(is_active=True).order_by('-created_at')
    
    # Apply filters
    category_id = request.GET.get('category')
    if category_id:
        products_list = products_list.filter(category_id=category_id)
    
    brand_id = request.GET.get('brand')
    if brand_id:
        products_list = products_list.filter(brand_id=brand_id)
    
    gender = request.GET.get('gender')
    if gender:
        products_list = products_list.filter(gender=gender)
    
    # Price filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products_list = products_list.filter(price__gte=min_price)
    if max_price:
        products_list = products_list.filter(price__lte=max_price)
    
    # Discount filter
    if request.GET.get('discount_only'):
        products_list = products_list.filter(discount_price__isnull=False)
    
    # Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_low':
        products_list = products_list.order_by('price')
    elif sort_by == 'price_high':
        products_list = products_list.order_by('-price')
    elif sort_by == 'discount':
        products_list = products_list.filter(discount_price__isnull=False).order_by('-discount_price')
    elif sort_by == 'rating':
        products_list = products_list.order_by('-average_rating')
    else:  # newest
        products_list = products_list.order_by('-created_at')
    
    # Get categories and brands for filters
    categories = Category.objects.filter(is_active=True).order_by('name')
    brands = Brand.objects.filter(is_active=True).order_by('name')
    
    # Count products per category
    for category in categories:
        category.product_count = Product.objects.filter(category=category, is_active=True).count()
    
    # Selected category for breadcrumb
    selected_category = None
    if category_id:
        try:
            selected_category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            pass
    
    # Pagination
    paginator = Paginator(products_list, 12)  # 12 products per page
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)
    
    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'selected_category': selected_category,
        'sort': sort_by,
    }
    
    return render(request, 'products.html', context)
def categories(request):
    categories_list = Category.objects.all()
    return render(request, 'categories.html', {'categories': categories_list})

def brands(request):
    brands_list = Brand.objects.all()
    return render(request, 'brands.html', {'brands': brands_list})

def about(request):
    return render(request, 'about.html')

def search(request):
    query = request.GET.get('q', '')
    products = Product.objects.filter(
        Q(name__icontains=query) | 
        Q(description__icontains=query) |
        Q(category__name__icontains=query) |
        Q(brand__name__icontains=query)
    ).filter(is_active=True)
    
    context = {
        'products': products,
        'query': query,
    }
    return render(request, 'search.html', context)
def about_view(request):
    """About page view"""
    context = {
        'page_title': 'About Us',
    }
    return render(request, 'about.html', context)

def brands_view(request):
    """Brands page view"""
    # Get all brands
    brands = Brand.objects.filter(is_active=True).annotate(
        product_count=Count('product', filter=Q(product__is_active=True)),
        average_rating=Avg('product__average_rating')
    ).order_by('name')
    
    # Group brands by first letter
    brands_by_letter = {}
    for brand in brands:
        first_letter = brand.name[0].upper() if brand.name else 'Other'
        if first_letter not in brands_by_letter:
            brands_by_letter[first_letter] = []
        brands_by_letter[first_letter].append(brand)
    
    # Sort letters alphabetically
    brands_by_letter = dict(sorted(brands_by_letter.items()))
    
    # Get featured brands
    featured_brands = brands.filter(is_featured=True)[:12]
    
    # Get new brands (added in last 30 days)
    from datetime import timedelta
    from django.utils import timezone
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_brands = brands.filter(created_at__gte=thirty_days_ago)[:12]
    
    # Brand categories counts (you would need to add category field to Brand model)
    # For now, using dummy counts
    luxury_count = brands.filter(name__icontains='designer').count() or 8
    sports_count = brands.filter(name__icontains='sport').count() or 6
    casual_count = brands.filter(name__icontains='casual').count() or 15
    local_count = brands.filter(country='Kenya').count() or 10
    
    context = {
        'brands': brands,
        'brands_by_letter': brands_by_letter,
        'featured_brands': featured_brands,
        'new_brands': new_brands,
        'luxury_count': luxury_count,
        'sports_count': sports_count,
        'casual_count': casual_count,
        'local_count': local_count,
    }
    return render(request, 'brands.html', context)

def brand_products_view(request, slug):
    """Products by specific brand"""
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    
    products = Product.objects.filter(
        brand=brand,
        is_active=True
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 12)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    context = {
        'brand': brand,
        'products': products_page,
    }
    return render(request, 'brand_products.html', context)

# M-Pesa Integration
import base64
from datetime import datetime, time

@login_required
def process_mpesa_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Daraja API credentials (configure in settings)
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    
    # Generate access token
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    auth = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth}"
    }
    
    try:
        response = requests.get(api_url, headers=headers)
        access_token = response.json().get("access_token")
        
        # Initiate STK Push
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
        
        stk_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(order.total),
            "PartyA": order.phone,
            "PartyB": shortcode,
            "PhoneNumber": order.phone,
            "CallBackURL": "https://yourdomain.com/mpesa-callback/",
            "AccountReference": order.order_number,
            "TransactionDesc": f"Payment for order {order.order_number}"
        }
        
        response = requests.post(stk_url, json=payload, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200:
            # Save transaction details
            MpesaTransaction.objects.create(
                order=order,
                checkout_request_id=response_data.get('CheckoutRequestID'),
                merchant_request_id=response_data.get('MerchantRequestID'),
                phone_number=order.phone,
                amount=order.total
            )
            
            messages.success(request, 'Payment request sent to your phone!')
            return redirect('order_detail', order_id=order.id)
        else:
            messages.error(request, 'Failed to initiate payment!')
            return redirect('checkout')
            
    except Exception as e:
        messages.error(request, f'Payment error: {str(e)}')
        return redirect('checkout')

@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        
        # Process callback
        result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        result_desc = data.get('Body', {}).get('stkCallback', {}).get('ResultDesc')
        checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        
        try:
            transaction = MpesaTransaction.objects.get(checkout_request_id=checkout_request_id)
            transaction.result_code = result_code
            transaction.result_desc = result_desc
            
            if result_code == 0:
                # Payment successful
                callback_metadata = data['Body']['stkCallback']['CallbackMetadata']['Item']
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        transaction.receipt_number = item.get('Value')
                    elif item.get('Name') == 'TransactionDate':
                        transaction.transaction_date = datetime.strptime(str(item.get('Value')), "%Y%m%d%H%M%S")
                
                transaction.order.payment_status = True
                transaction.order.status = 'processing'
                transaction.order.save()
            else:
                # Payment failed
                transaction.order.status = 'cancelled'
                transaction.order.save()
            
            transaction.save()
            
        except MpesaTransaction.DoesNotExist:
            pass
        
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
    
    from django.db.models import Count, Sum, Avg, Q
from datetime import datetime, timedelta

@login_required
def wishlist_view(request):
    """User's wishlist page"""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product', 'product__category', 'product__brand'
    ).order_by('-added_at')
    
    # Calculate statistics
    total_items = wishlist_items.count()
    in_stock_count = wishlist_items.filter(product__stock__gt=0).count()
    out_of_stock_count = total_items - in_stock_count
    in_stock_percentage = (in_stock_count / total_items * 100) if total_items > 0 else 0
    out_of_stock_percentage = 100 - in_stock_percentage
    
    # Calculate price range
    prices = [item.product.get_final_price() for item in wishlist_items]
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0
    total_value = sum(prices)
    
    # Get categories with counts
    from django.db.models import Count
    categories = Category.objects.filter(
        product__wishlist__user=request.user
    ).annotate(
        count=Count('product__wishlist')
    ).distinct()[:8]
    
    # Get popular categories for empty state
    popular_categories = Category.objects.annotate(
        product_count=Count('product', filter=Q(product__is_active=True))
    ).filter(product_count__gt=0).order_by('-product_count')[:8]
    
    # Get recommendations (products from same categories)
    if wishlist_items.exists():
        category_ids = wishlist_items.values_list('product__category_id', flat=True).distinct()
        recommendations = Product.objects.filter(
            category_id__in=category_ids,
            is_active=True
        ).exclude(
            id__in=wishlist_items.values_list('product_id', flat=True)
        )[:6]
    else:
        recommendations = Product.objects.filter(is_active=True).order_by('?')[:6]
    
    context = {
        'wishlist_items': wishlist_items,
        'total_items': total_items,
        'in_stock_count': in_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'in_stock_percentage': round(in_stock_percentage, 1),
        'out_of_stock_percentage': round(out_of_stock_percentage, 1),
        'min_price': min_price,
        'max_price': max_price,
        'total_value': total_value,
        'categories': categories,
        'popular_categories': popular_categories,
        'recommendations': recommendations,
    }
    return render(request, 'wishlist.html', context)

@login_required
def orders_view(request):
    """User's orders page"""
    orders = Order.objects.filter(user=request.user).prefetch_related(
        'items', 'items__product'
    ).order_by('-created_at')
    
    # Apply status filter
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Apply time filter
    days_filter = request.GET.get('days')
    if days_filter and days_filter.isdigit():
        days = int(days_filter)
        start_date = datetime.now() - timedelta(days=days)
        orders = orders.filter(created_at__gte=start_date)
    
    # Apply sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        orders = orders.order_by('created_at')
    elif sort_by == 'price_high':
        orders = orders.order_by('-total_amount')
    elif sort_by == 'price_low':
        orders = orders.order_by('total_amount')
    
    # Calculate statistics
    total_orders = Order.objects.filter(user=request.user).count()
    pending_orders = Order.objects.filter(user=request.user, status='pending').count()
    processing_orders = Order.objects.filter(user=request.user, status='processing').count()
    shipped_orders = Order.objects.filter(user=request.user, status='shipped').count()
    delivered_orders = Order.objects.filter(user=request.user, status='delivered').count()
    cancelled_orders = Order.objects.filter(user=request.user, status='cancelled').count()
    
    # Calculate financial statistics
    total_spent = Order.objects.filter(
        user=request.user, 
        status='delivered'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    avg_order_value = total_spent / delivered_orders if delivered_orders > 0 else 0
    success_rate = (delivered_orders / total_orders * 100) if total_orders > 0 else 0
    
    # Get popular products for empty state
    popular_products = Product.objects.filter(
        is_active=True,
        orderitem__order__user=request.user
    ).annotate(
        order_count=Count('orderitem')
    ).order_by('-order_count')[:8]
    
    # Pagination
    paginator = Paginator(orders, 10)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    context = {
        'orders': orders_page,
        'status_filter': status_filter,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'total_spent': total_spent,
        'avg_order_value': round(avg_order_value, 2),
        'success_rate': round(success_rate, 1),
        'popular_products': popular_products,
    }
    return render(request, 'orders.html', context)

@login_required
def order_detail_view(request, order_id):
    """Order detail page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    context = {
        'order': order,
    }
    return render(request, 'order_detail.html', context)

@login_required
def cancel_order_view(request, order_id):
    """Cancel an order"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        # Only allow cancellation for pending/processing orders
        if order.status in ['pending', 'processing']:
            order.status = 'cancelled'
            order.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Order cancelled successfully'})
            else:
                messages.success(request, 'Order cancelled successfully')
                return redirect('orders')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Cannot cancel order at this stage'})
            else:
                messages.error(request, 'Cannot cancel order at this stage')
                return redirect('order_detail', order_id=order_id)
    
    return redirect('orders')

@login_required
def move_to_cart_view(request, wishlist_id):
    """Move item from wishlist to cart"""
    if request.method == 'POST':
        wishlist_item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
        
        # Add to cart
        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            product=wishlist_item.product,
            defaults={'quantity': 1}
        )
        
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        
        # Remove from wishlist
        wishlist_item.delete()
        
        cart_count = Cart.objects.filter(user=request.user).count()
        
        return JsonResponse({
            'success': True,
            'message': 'Item moved to cart',
            'cart_count': cart_count
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def remove_from_wishlist_view(request, wishlist_id):
    """Remove item from wishlist"""
    if request.method == 'POST':
        wishlist_item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
        wishlist_item.delete()
        
        return JsonResponse({'success': True, 'message': 'Item removed from wishlist'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def clear_wishlist_view(request):
    """Clear all items from user's wishlist"""
    if request.method == 'POST':
        try:
            # Get count before deletion for response
            items_count = Wishlist.objects.filter(user=request.user).count()
            
            # Delete all wishlist items for this user
            deleted_count, _ = Wishlist.objects.filter(user=request.user).delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Wishlist cleared successfully',
                'deleted_count': deleted_count
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error clearing wishlist: {str(e)}'
            }, status=500)
    
    # If not POST request, redirect to wishlist page
    return redirect('wishlist')
@login_required
def move_selected_to_cart_view(request):
    """Move selected wishlist items to cart"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            wishlist_ids = data.get('wishlist_ids', [])
            
            moved_count = 0
            
            for wishlist_id in wishlist_ids:
                try:
                    wishlist_item = Wishlist.objects.get(id=wishlist_id, user=request.user)
                    
                    # Add to cart or update quantity
                    cart_item, created = Cart.objects.get_or_create(
                        user=request.user,
                        product=wishlist_item.product,
                        defaults={'quantity': 1}
                    )
                    
                    if not created:
                        cart_item.quantity += 1
                        cart_item.save()
                    
                    # Remove from wishlist
                    wishlist_item.delete()
                    moved_count += 1
                    
                except Wishlist.DoesNotExist:
                    continue
            
            cart_count = Cart.objects.filter(user=request.user).count()
            
            return JsonResponse({
                'success': True,
                'message': f'{moved_count} item(s) moved to cart',
                'moved_count': moved_count,
                'cart_count': cart_count
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error moving items: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=400)

@login_required
def remove_selected_wishlist_view(request):
    """Remove selected items from wishlist"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            wishlist_ids = data.get('wishlist_ids', [])
            
            # Delete selected wishlist items
            deleted_count, _ = Wishlist.objects.filter(
                id__in=wishlist_ids,
                user=request.user
            ).delete()
            
            return JsonResponse({
                'success': True,
                'message': f'{deleted_count} item(s) removed from wishlist',
                'removed_count': deleted_count
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error removing items: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=400)
@login_required
def track_order_view(request, order_id):
    """Track order details and shipping information"""
    try:
        # Get the order (ensure it belongs to the user)
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        # Get tracking information (you can integrate with shipping APIs here)
        tracking_info = get_tracking_information(order)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return JSON for AJAX requests
            context = {
                'order': order,
                'tracking_info': tracking_info,
            }
            return render(request, 'partials/tracking_info.html', context)
        else:
            # Return full page for regular requests
            context = {
                'order': order,
                'tracking_info': tracking_info,
                'page_title': f'Track Order #{order.order_number}'
            }
            return render(request, 'track_order.html', context)
            
    except Order.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Order not found'
            }, status=404)
        else:
            messages.error(request, 'Order not found')
            return redirect('orders')
    except Exception as e:
        print(f"Error tracking order: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while tracking your order'
            }, status=500)
        else:
            messages.error(request, 'An error occurred while tracking your order')
            return redirect('orders')


def get_tracking_information(order):
    """
    Helper function to get tracking information.
    This can be extended to integrate with actual shipping APIs.
    """
    # Mock tracking data - replace with actual API calls
    tracking_steps = []
    
    if order.status == 'pending':
        tracking_steps = [
            {'status': 'Order Placed', 'description': 'Your order has been received', 
             'date': order.created_at.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Order Confirmed', 'description': 'We are processing your order', 
             'date': 'Pending', 'completed': False},
            {'status': 'Shipped', 'description': 'Your order is on its way', 
             'date': 'Pending', 'completed': False},
            {'status': 'Out for Delivery', 'description': 'Your order is out for delivery', 
             'date': 'Pending', 'completed': False},
            {'status': 'Delivered', 'description': 'Your order has been delivered', 
             'date': 'Pending', 'completed': False},
        ]
    elif order.status == 'processing':
        processing_date = order.created_at + timedelta(hours=1)
        tracking_steps = [
            {'status': 'Order Placed', 'description': 'Your order has been received', 
             'date': order.created_at.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Order Confirmed', 'description': 'We are processing your order', 
             'date': processing_date.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Shipped', 'description': 'Your order is on its way', 
             'date': 'Pending', 'completed': False},
            {'status': 'Out for Delivery', 'description': 'Your order is out for delivery', 
             'date': 'Pending', 'completed': False},
            {'status': 'Delivered', 'description': 'Your order has been delivered', 
             'date': 'Pending', 'completed': False},
        ]
    elif order.status == 'shipped':
        shipped_date = order.created_at + timedelta(days=1)
        estimated_delivery = shipped_date + timedelta(days=3)
        tracking_steps = [
            {'status': 'Order Placed', 'description': 'Your order has been received', 
             'date': order.created_at.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Order Confirmed', 'description': 'We are processing your order', 
             'date': (order.created_at + timedelta(hours=1)).strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Shipped', 'description': 'Your order is on its way', 
             'date': shipped_date.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Out for Delivery', 'description': 'Your order is out for delivery', 
             'date': 'Pending', 'completed': False},
            {'status': 'Delivered', 'description': 'Your order has been delivered', 
             'date': 'Pending', 'completed': False},
        ]
        # Add estimated delivery
        tracking_info = {
            'steps': tracking_steps,
            'tracking_number': order.tracking_number or 'FNTK' + str(order.id).zfill(8),
            'carrier': 'FashionNova Express',
            'estimated_delivery': estimated_delivery.strftime('%B %d, %Y'),
            'current_step': 2,  # 0-indexed, step 2 is "Shipped"
        }
        return tracking_info
    elif order.status == 'delivered' and order.delivered_at:
        delivered_date = order.delivered_at
        shipped_date = delivered_date - timedelta(days=2)
        processing_date = shipped_date - timedelta(hours=3)
        tracking_steps = [
            {'status': 'Order Placed', 'description': 'Your order has been received', 
             'date': order.created_at.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Order Confirmed', 'description': 'We are processing your order', 
             'date': processing_date.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Shipped', 'description': 'Your order is on its way', 
             'date': shipped_date.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Out for Delivery', 'description': 'Your order is out for delivery', 
             'date': (delivered_date - timedelta(hours=2)).strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Delivered', 'description': 'Your order has been delivered', 
             'date': delivered_date.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
        ]
    else:
        # Default tracking steps
        tracking_steps = [
            {'status': 'Order Placed', 'description': 'Your order has been received', 
             'date': order.created_at.strftime('%b %d, %Y %I:%M %p'), 'completed': True},
            {'status': 'Order Confirmed', 'description': 'We are processing your order', 
             'date': 'Pending', 'completed': False},
            {'status': 'Shipped', 'description': 'Your order is on its way', 
             'date': 'Pending', 'completed': False},
            {'status': 'Out for Delivery', 'description': 'Your order is out for delivery', 
             'date': 'Pending', 'completed': False},
            {'status': 'Delivered', 'description': 'Your order has been delivered', 
             'date': 'Pending', 'completed': False},
        ]
    
    # Default tracking info
    tracking_info = {
        'steps': tracking_steps,
        'tracking_number': order.tracking_number or 'FNTK' + str(order.id).zfill(8),
        'carrier': 'FashionNova Express',
        'estimated_delivery': order.estimated_delivery.strftime('%B %d, %Y') if order.estimated_delivery else 'Calculating...',
        'current_step': get_current_step_index(order.status),
    }
    
    return tracking_info


def get_current_step_index(status):
    """Helper to get the current step index based on order status"""
    status_mapping = {
        'pending': 0,
        'processing': 1,
        'shipped': 2,
        'delivered': 4,
        'cancelled': -1,
    }
    return status_mapping.get(status, 0)

@login_required
def reorder_items_view(request):
    """Get previous order items for reordering"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get last 5 delivered orders
        recent_orders = Order.objects.filter(
            user=request.user,
            status='delivered'
        ).order_by('-created_at')[:5]
        
        reorder_items = []
        
        for order in recent_orders:
            for item in order.items.all():
                product = item.product
                
                # Check if product is still active and in stock
                if product.is_active and product.stock > 0:
                    reorder_items.append({
                        'order_id': order.id,
                        'order_date': order.created_at.strftime('%b %d, %Y'),
                        'product_id': product.id,
                        'name': product.name,
                        'category': product.category.name if product.category else 'Uncategorized',
                        'image': product.image.url if product.image else '/static/images/products/default-product.jpg',
                        'previous_price': float(item.unit_price),
                        'current_price': float(product.get_final_price()),
                        'quantity': item.quantity,
                        'in_stock': product.stock > 0,
                        'stock_quantity': product.stock,
                        'has_price_change': float(item.unit_price) != float(product.get_final_price())
                    })
        
        # Limit to 20 items
        reorder_items = reorder_items[:20]
        
        return JsonResponse({
            'success': True,
            'items': reorder_items,
            'count': len(reorder_items)
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})
@login_required
def add_reorder_to_cart_view(request):
    """Add reorder items to cart"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            
            added_count = 0
            errors = []
            
            for item_data in items:
                try:
                    product_id = item_data.get('product_id')
                    quantity = int(item_data.get('quantity', 1))
                    
                    product = Product.objects.get(id=product_id, is_active=True)
                    
                    # Check stock availability
                    if product.stock <= 0:
                        errors.append(f"{product.name} is out of stock")
                        continue
                    
                    if quantity > product.stock:
                        errors.append(f"Only {product.stock} units available for {product.name}")
                        quantity = product.stock
                    
                    # Add to cart
                    cart_item, created = Cart.objects.get_or_create(
                        user=request.user,
                        product=product,
                        defaults={'quantity': quantity}
                    )
                    
                    if not created:
                        new_quantity = cart_item.quantity + quantity
                        if new_quantity > product.stock:
                            errors.append(f"Maximum stock reached for {product.name}")
                            cart_item.quantity = product.stock
                        else:
                            cart_item.quantity = new_quantity
                        cart_item.save()
                    
                    added_count += 1
                    
                except Product.DoesNotExist:
                    errors.append(f"Product not found")
                except ValueError:
                    errors.append(f"Invalid quantity for product {product_id}")
                except Exception as e:
                    errors.append(f"Error adding product {product_id}: {str(e)}")
            
            cart_count = Cart.objects.filter(user=request.user).count()
            
            response_data = {
                'success': added_count > 0,
                'added_count': added_count,
                'cart_count': cart_count,
                'errors': errors[:5] if len(errors) > 5 else errors
            }
            
            if len(errors) > 5:
                response_data['error_count'] = len(errors)
                response_data['message'] = f'Added {added_count} items, {len(errors)} errors occurred'
            elif errors:
                response_data['message'] = f'Added {added_count} items, some errors occurred'
            else:
                response_data['message'] = f'Successfully added {added_count} items to cart'
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Server error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})
@login_required
def export_orders_view(request):
    """Export orders to CSV"""
    try:
        # Get filter parameters
        status_filter = request.GET.get('status')
        days_filter = request.GET.get('days')
        
        # Base queryset
        orders = Order.objects.filter(user=request.user)
        
        # Apply filters
        if status_filter:
            orders = orders.filter(status=status_filter)
        
        if days_filter and days_filter.isdigit():
            days = int(days_filter)
            start_date = time.timezone.now() - timedelta(days=days)
            orders = orders.filter(created_at__gte=start_date)
        
        # Create CSV data
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="fashionnova-orders-{time.timezone.now().date()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Order Number', 'Date', 'Status', 'Payment Method', 
                        'Total Amount', 'Items Count', 'Shipping Address'])
        
        for order in orders:
            writer.writerow([
                order.order_number,
                order.created_at.strftime('%Y-%m-%d %H:%M'),
                order.get_status_display(),
                order.get_payment_method_display(),
                f"Ksh {order.total_amount}",
                order.items.count(),
                order.shipping_address[:50] + '...' if len(order.shipping_address) > 50 else order.shipping_address
            ])
        
        return response
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'Error exporting orders: {str(e)}'
            })
        else:
            messages.error(request, f'Error exporting orders: {str(e)}')
            return redirect('orders')

def seller_required(view_func):
    """Decorator to ensure user is a seller"""
    decorated_view_func = login_required(view_func)
    return user_passes_test(lambda u: u.user_type == 'seller')(decorated_view_func)

@seller_required
def seller_dashboard_view(request):
    """Seller dashboard main view"""
    try:
        seller_profile = request.user.sellerprofile
    except SellerProfile.DoesNotExist:
        messages.error(request, 'Seller profile not found. Please update your profile.')
        return redirect('profile')
    
    # Calculate statistics
    total_revenue = OrderItem.objects.filter(
        seller=seller_profile,
        order__status='delivered'
    ).aggregate(total=Sum('total_price'))['total'] or 0
    
    total_orders = OrderItem.objects.filter(
        seller=seller_profile
    ).values('order').distinct().count()
    
    total_products = Product.objects.filter(seller=seller_profile).count()
    active_products = Product.objects.filter(seller=seller_profile, is_active=True).count()
    
    # Store rating
    store_rating = Review.objects.filter(
        product__seller=seller_profile
    ).aggregate(avg=Avg('rating'))['avg'] or 0
    
    total_reviews = Review.objects.filter(product__seller=seller_profile).count()
    
    # Recent orders
    recent_orders = Order.objects.filter(
        items__seller=seller_profile
    ).distinct().order_by('-created_at')[:5]
    
    # Recent products
    recent_products = Product.objects.filter(
        seller=seller_profile
    ).order_by('-created_at')[:10]
    
    # Recent reviews
    recent_reviews = Review.objects.filter(
        product__seller=seller_profile
    ).select_related('user', 'product').order_by('-created_at')[:5]
    
    # Additional stats
    today = datetime.now().date()
    today_revenue = OrderItem.objects.filter(
        seller=seller_profile,
        order__created_at__date=today,
        order__status='delivered'
    ).aggregate(total=Sum('total_price'))['total'] or 0
    
    pending_orders_count = OrderItem.objects.filter(
        seller=seller_profile,
        order__status='pending'
    ).values('order').distinct().count()
    
    low_stock_count = Product.objects.filter(
        seller=seller_profile,
        stock__lte=F('low_stock_threshold'),
        stock__gt=0
    ).count()
    
    # Categories for dropdown
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    # Visitor count (simulated - in real app, use analytics)
    visitor_count = 1245  # Simulated data
    conversion_rate = 3.2  # Simulated data
    satisfaction_rate = 94  # Simulated data
    
    context = {
        'seller_profile': seller_profile,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_products': total_products,
        'active_products': active_products,
        'store_rating': round(store_rating, 1),
        'total_reviews': total_reviews,
        'recent_orders': recent_orders,
        'recent_products': recent_products,
        'recent_reviews': recent_reviews,
        'today_revenue': today_revenue,
        'pending_orders_count': pending_orders_count,
        'low_stock_count': low_stock_count,
        'categories': categories,
        'brands': brands,
        'visitor_count': visitor_count,
        'conversion_rate': conversion_rate,
        'satisfaction_rate': satisfaction_rate,
    }
    return render(request, 'sellersdashboard.html', context)

@seller_required
def add_product_view(request):
    """Add new product view"""
    if request.method == 'POST':
        try:
            seller_profile = request.user.sellerprofile
            
            # Get form data
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            discount_price = request.POST.get('discount_price')
            category_id = request.POST.get('category')
            brand_id = request.POST.get('brand')
            gender = request.POST.get('gender', 'U')
            stock = request.POST.get('stock', 0)
            size = request.POST.get('size', '')
            color = request.POST.get('color', '')
            material = request.POST.get('material', '')
            weight = request.POST.get('weight')
            
            # Create product
            product = Product.objects.create(
                seller=seller_profile,
                name=name,
                description=description,
                price=price,
                discount_price=discount_price if discount_price else None,
                category_id=category_id,
                brand_id=brand_id if brand_id else None,
                gender=gender,
                stock=stock,
                size=size,
                color=color,
                material=material,
                weight=weight if weight else None,
                is_active=request.POST.get('is_active') == 'on',
                is_featured=request.POST.get('is_featured') == 'on',
                is_new=request.POST.get('is_new') == 'on',
                is_best_seller=request.POST.get('is_best_seller') == 'on',
            )
            
            # Handle main image
            if 'main_image' in request.FILES:
                product.image = request.FILES['main_image']
                product.save()
            
            # Handle gallery images
            gallery_images = request.FILES.getlist('gallery_images')
            for i, image in enumerate(gallery_images[:5]):  # Limit to 5 images
                ProductImage.objects.create(
                    product=product,
                    image=image,
                    display_order=i,
                    is_default=False
                )
            
            # Handle tags
            tags = request.POST.get('tags', '')
            if tags:
                # You would implement tag logic here
                pass
            
            messages.success(request, f'Product "{name}" added successfully!')
            
            if request.POST.get('is_draft'):
                return redirect('seller_dashboard')
            else:
                return redirect('product_detail', slug=product.slug)
                
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
            return redirect('add_product')
    
    # GET request - show form
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    context = {
        'categories': categories,
        'brands': brands,
    }
    return render(request, 'add_product.html', context)

@seller_required
def update_products_status_view(request):
    """Bulk update products status"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            product_ids = data.get('product_ids', [])
            action = data.get('action')  # 'activate' or 'deactivate'
            
            products = Product.objects.filter(
                id__in=product_ids,
                seller=request.user.sellerprofile
            )
            
            if action == 'activate':
                updated_count = products.update(is_active=True)
            elif action == 'deactivate':
                updated_count = products.update(is_active=False)
            else:
                return JsonResponse({'success': False, 'message': 'Invalid action'})
            
            return JsonResponse({
                'success': True,
                'updated_count': updated_count,
                'message': f'{updated_count} product(s) {action}d successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@seller_required
def delete_products_view(request):
    """Bulk delete products"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            product_ids = data.get('product_ids', [])
            
            # Delete products
            deleted_count, _ = Product.objects.filter(
                id__in=product_ids,
                seller=request.user.sellerprofile
            ).delete()
            
            return JsonResponse({
                'success': True,
                'deleted_count': deleted_count,
                'message': f'{deleted_count} product(s) deleted successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@seller_required
def seller_orders_view(request):
    """View all orders for seller"""
    seller_profile = request.user.sellerprofile
    
    orders = Order.objects.filter(
        items__seller=seller_profile
    ).distinct().order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    context = {
        'orders': orders_page,
        'status_filter': status_filter,
    }
    return render(request, 'seller_orders.html', context)

@seller_required
def update_order_status_view(request, order_id):
    """Update order status (seller side)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            # Get order items for this seller only
            order_items = OrderItem.objects.filter(
                order_id=order_id,
                seller=request.user.sellerprofile
            )
            
            if not order_items.exists():
                return JsonResponse({
                    'success': False,
                    'message': 'Order not found or not authorized'
                })
            
            # Update order
            order = order_items.first().order
            order.status = new_status
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Order status updated to {new_status}'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@seller_required
def toggle_product_status_view(request, product_id, action):
    """Toggle individual product status"""
    if request.method == 'POST':
        try:
            product = Product.objects.get(
                id=product_id,
                seller=request.user.sellerprofile
            )
            
            if action == 'activate':
                product.is_active = True
                message = 'Product activated successfully'
            elif action == 'deactivate':
                product.is_active = False
                message = 'Product deactivated successfully'
            else:
                return JsonResponse({'success': False, 'message': 'Invalid action'})
            
            product.save()
            
            return JsonResponse({'success': True, 'message': message})
            
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Product not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@seller_required
def delete_product_view(request, product_id):
    """Delete individual product"""
    if request.method == 'POST':
        try:
            product = Product.objects.get(
                id=product_id,
                seller=request.user.sellerprofile
            )
            product_name = product.name
            product.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Product "{product_name}" deleted successfully'
            })
            
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Product not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@seller_required
def edit_product_view(request, product_id):
    """Edit product view"""
    product = get_object_or_404(Product, id=product_id, seller=request.user.sellerprofile)
    
    if request.method == 'POST':
        # Similar to add_product_view but for editing
        # Implement edit logic here
        pass
    
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    context = {
        'product': product,
        'categories': categories,
        'brands': brands,
        'is_edit': True,
    }
    return render(request, 'add_product.html', context)

@seller_required
def save_store_settings_view(request):
    
    """Save store settings"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            seller_profile = request.user.sellerprofile
            
            # Update store info
            if 'store_name' in data:
                seller_profile.store_name = data['store_name']
            
            if 'description' in data:
                seller_profile.description = data['description']
            
            seller_profile.save()
            
            # Update user info
            user = request.user
            if 'notification_email' in data:
                user.email = data['notification_email']
            
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Store settings saved successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def seller_dashboard_view(request):
    """
    Seller Dashboard - Main view for sellers to manage their store
    """
    categories = Category.objects.filter(is_active=True).order_by('name')
    if not Category.objects.exists():
        # Create default categories
        default_categories = [
            {'name': "Women's Fashion", 'gender': 'F'},
            {'name': "Men's Fashion", 'gender': 'M'},
            {'name': "Kids' Fashion", 'gender': 'K'},
            {'name': 'Unisex Clothing', 'gender': 'U'},
        ]
        for cat_data in default_categories:
            Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': f'{cat_data["name"]} collection',
                    'is_active': True,
                    'gender': cat_data.get('gender', 'U')
                }
            )
    
    categories = Category.objects.filter(is_active=True).order_by('name')
    brands = Brand.objects.filter(is_active=True).order_by('name')

    if not brands.exists():
        # Create some default brands
        default_brands = [
            {'name': 'Nike', 'description': 'Sports and lifestyle brand'},
            {'name': 'Adidas', 'description': 'German sports brand'},
            {'name': 'Gucci', 'description': 'Italian luxury brand'},
            {'name': 'Zara', 'description': 'Spanish fast fashion'},
            {'name': 'H&M', 'description': 'Swedish fashion retailer'},
            {'name': 'FashionNova', 'description': 'Your store brand'},
        ]
        
        for brand_data in default_brands:
            Brand.objects.get_or_create(
                name=brand_data['name'],
                defaults={
                    'description': brand_data['description'],
                    'is_active': True
                }
            )
        
        brands = Brand.objects.filter(is_active=True).order_by('name')

        
    # Check if user is a seller
    if request.user.user_type != 'seller':
        messages.error(request, 'Access denied. Seller account required.')
        return redirect('home')
    
    try:
        # Get seller profile
        seller_profile = request.user.sellerprofile
    except:
        # If seller profile doesn't exist, create one
        from .models import SellerProfile
        seller_profile = SellerProfile.objects.create(
            user=request.user,
            store_name=f"{request.user.username}'s Store"
        )
        messages.info(request, 'Seller profile created. Please update your store information.')
    
    # Calculate total revenue (from delivered orders only)
    total_revenue = 0
    try:
        from .models import OrderItem
        revenue_data = OrderItem.objects.filter(
            seller=seller_profile,
            order__status='delivered'
        ).aggregate(total=Sum('total_price'))
        total_revenue = revenue_data['total'] or 0
    except:
        total_revenue = 0
    
    # Calculate total orders
    try:
        from .models import OrderItem
        total_orders = OrderItem.objects.filter(
            seller=seller_profile
        ).values('order').distinct().count()
    except:
        total_orders = 0
    
    # Get product statistics
    try:
        from .models import Product
        total_products = Product.objects.filter(seller=seller_profile).count()
        active_products = Product.objects.filter(
            seller=seller_profile,
            is_active=True
        ).count()
        
        # Get recent products (last 10 added)
        recent_products = Product.objects.filter(
            seller=seller_profile
        ).select_related('category', 'brand').order_by('-created_at')[:10]
    except:
        total_products = 0
        active_products = 0
        recent_products = []
    
    # Calculate store rating
    try:
        from .models import Review
        rating_data = Review.objects.filter(
            product__seller=seller_profile
        ).aggregate(avg=Avg('rating'), count=Count('id'))
        store_rating = rating_data['avg'] or 0
        total_reviews = rating_data['count'] or 0
    except:
        store_rating = 0
        total_reviews = 0
    
    # Get recent orders (last 5)
    try:
        from .models import Order, OrderItem
        # Get distinct orders that contain seller's products
        order_ids = OrderItem.objects.filter(
            seller=seller_profile
        ).values_list('order_id', flat=True).distinct()
        
        recent_orders = Order.objects.filter(
            id__in=order_ids
        ).select_related('user').order_by('-created_at')[:5]
    except:
        recent_orders = []
    
    # Get recent reviews
    try:
        from .models import Review
        recent_reviews = Review.objects.filter(
            product__seller=seller_profile
        ).select_related('user', 'product').order_by('-created_at')[:5]
    except:
        recent_reviews = []
    
    # Calculate today's revenue
    try:
        from .models import OrderItem
        today = time.timezone.now().date()
        today_revenue_data = OrderItem.objects.filter(
            seller=seller_profile,
            order__created_at__date=today,
            order__status='delivered'
        ).aggregate(total=Sum('total_price'))
        today_revenue = today_revenue_data['total'] or 0
    except:
        today_revenue = 0
    
    # Count pending orders
    try:
        from .models import OrderItem
        pending_orders_count = OrderItem.objects.filter(
            seller=seller_profile,
            order__status='pending'
        ).values('order').distinct().count()
    except:
        pending_orders_count = 0
    
    # Count low stock items
    try:
        from .models import Product
        low_stock_count = Product.objects.filter(
            seller=seller_profile,
            stock__lte=F('low_stock_threshold'),
            stock__gt=0,
            is_active=True
        ).count()
    except:
        low_stock_count = 0
    
    # Get categories for dropdown
    try:
        from .models import Category
        categories = Category.objects.all()
    except:
        categories = []
    
    # Get brands for dropdown
    try:
        from .models import Brand
        brands = Brand.objects.all()
    except:
        brands = []
    
    # Simulated visitor data (in production, use analytics)
    visitor_count = 1245
    conversion_rate = 3.2  # Percentage
    satisfaction_rate = 94  # Percentage
    
    # Calculate weekly revenue trend (last 7 days)
    weekly_revenue = []
    try:
        from .models import OrderItem
        for i in range(6, -1, -1):
            date = time.timezone.now().date() - timedelta(days=i)
            day_revenue = OrderItem.objects.filter(
                seller=seller_profile,
                order__created_at__date=date,
                order__status='delivered'
            ).aggregate(total=Sum('total_price'))['total'] or 0
            weekly_revenue.append({
                'date': date.strftime('%a'),
                'amount': day_revenue
            })
    except:
        weekly_revenue = [
            {'date': 'Mon', 'amount': 0},
            {'date': 'Tue', 'amount': 0},
            {'date': 'Wed', 'amount': 0},
            {'date': 'Thu', 'amount': 0},
            {'date': 'Fri', 'amount': 0},
            {'date': 'Sat', 'amount': 0},
            {'date': 'Sun', 'amount': 0},
        ]
    
    # Top selling products
    try:
        from .models import OrderItem
        top_products = OrderItem.objects.filter(
            seller=seller_profile
        ).values(
            'product__name', 
            'product__id'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_sold')[:5]
    except:
        top_products = []
    
    # Recent customer inquiries (simulated)
    recent_inquiries = [
        {'customer': 'John Doe', 'product': 'Nike T-Shirt', 'date': '2 hours ago', 'status': 'pending'},
        {'customer': 'Jane Smith', 'product': 'Adidas Shoes', 'date': '1 day ago', 'status': 'answered'},
        {'customer': 'Mike Johnson', 'product': 'Zara Jacket', 'date': '3 days ago', 'status': 'resolved'},
    ]
    
    # Stock alerts
    try:
        from .models import Product
        stock_alerts = Product.objects.filter(
            seller=seller_profile,
            stock__lte=F('low_stock_threshold'),
            is_active=True
        ).order_by('stock')[:5]
    except:
        stock_alerts = []
    
    # Prepare context
    context = {
        # Seller information
        'seller_profile': seller_profile,
        
        # Financial statistics
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'weekly_revenue': weekly_revenue,
        
        # Order statistics
        'total_orders': total_orders,
        'pending_orders_count': pending_orders_count,
        'recent_orders': recent_orders,
        
        # Product statistics
        'total_products': total_products,
        'active_products': active_products,
        'low_stock_count': low_stock_count,
        'recent_products': recent_products,
        'top_products': top_products,
        'stock_alerts': stock_alerts,
        
        # Store rating & reviews
        'store_rating': round(store_rating, 1),
        'total_reviews': total_reviews,
        'recent_reviews': recent_reviews,
        
        # Store performance
        'visitor_count': visitor_count,
        'conversion_rate': conversion_rate,
        'satisfaction_rate': satisfaction_rate,
        
        # Form data
        'categories': categories,
        'brands': brands,
        
        # Additional data
        'recent_inquiries': recent_inquiries,
        
        # Chart data for JavaScript
        'chart_labels': [day['date'] for day in weekly_revenue],
        'chart_data': [day['amount'] for day in weekly_revenue],
        
        # Monthly statistics (simulated)
        'monthly_stats': {
            'orders': 45,
            'revenue': 150000,
            'growth': 12.5,
            'customers': 38,
        },
        
        # Quick stats for cards
        'quick_stats': {
            'avg_order_value': round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
            'products_sold': sum(item['total_sold'] for item in top_products) if top_products else 0,
            'return_rate': 2.3,  # Simulated
            'response_time': '2.5 hours',  # Simulated
        }
    }
    
    # Handle AJAX requests for dashboard updates
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON data for AJAX updates
        ajax_data = {
            'total_revenue': total_revenue,
            'today_revenue': today_revenue,
            'total_orders': total_orders,
            'pending_orders': pending_orders_count,
            'active_products': active_products,
            'store_rating': round(store_rating, 1),
            'weekly_revenue': weekly_revenue,
            'top_products': list(top_products),
        }
        return JsonResponse(ajax_data)
    
    return render(request, 'sellersdashboard.html', context)

def brands_view(request):
    try:
        # Get all active brands with basic info
        brands = Brand.objects.filter(is_active=True).select_related().order_by('name')
        
        # Prepare brand data with statistics
        brand_list = []
        for brand in brands:
            product_count = brand.products.filter(is_active=True).count()
            
            # Calculate average rating
            avg_rating = Review.objects.filter(
                product__brand=brand,
                product__is_active=True,
                is_active=True
            ).aggregate(avg=Avg('rating'))['avg']
            
            avg_rating = float(avg_rating) if avg_rating else 0.0
            
            brand_data = {
                'id': brand.id,
                'name': brand.name,
                'slug': brand.slug,
                'description': brand.description,
                'logo': brand.logo,
                'website': brand.website,
                'product_count': product_count,
                'average_rating': avg_rating,
                'total_reviews': Review.objects.filter(
                    product__brand=brand,
                    product__is_active=True,
                    is_active=True
                ).count()
            }
            brand_list.append(brand_data)
        
        # Apply filters
        rating_filter = request.GET.get('rating')
        if rating_filter and rating_filter.isdigit():
            min_rating = float(rating_filter)
            brand_list = [b for b in brand_list if b['average_rating'] >= min_rating]
        
        # Apply sorting
        sort_by = request.GET.get('sort', 'name')
        if sort_by == 'rating':
            brand_list.sort(key=lambda x: x['average_rating'], reverse=True)
        elif sort_by == 'products':
            brand_list.sort(key=lambda x: x['product_count'], reverse=True)
        else:  # name
            brand_list.sort(key=lambda x: x['name'].lower())
        
        # Get featured brands
        featured_brands = sorted(
            [b for b in brand_list if b['average_rating'] >= 3.5],
            key=lambda x: x['average_rating'],
            reverse=True
        )[:6]
        
        # Organize alphabetically
        alphabetical_brands = {}
        for brand in brand_list:
            if brand['name']:
                first_letter = brand['name'][0].upper()
                if not first_letter.isalpha():
                    first_letter = '#'
            else:
                first_letter = '#'
            
            if first_letter not in alphabetical_brands:
                alphabetical_brands[first_letter] = []
            alphabetical_brands[first_letter].append(brand)
        
        # Sort alphabetically
        alphabetical_brands = dict(sorted(alphabetical_brands.items()))
        
        context = {
            'brands': brand_list,
            'featured_brands': featured_brands,
            'alphabetical_brands': alphabetical_brands,
            'total_brands': len(brand_list),
            'sort_by': sort_by,
        }
        
        return render(request, 'brands.html', context)
        
    except Exception as e:
        # For debugging
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
        return HttpResponse(f"Server error: {str(e)}", status=500)
    
    
# Create your views here.
