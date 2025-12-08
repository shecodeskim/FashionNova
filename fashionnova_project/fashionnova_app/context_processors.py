# fashionnova_app/context_processors.py
from .models import Cart, Wishlist
from django.contrib.auth import get_user_model

User = get_user_model()

def cart_count(request):
    """Add cart and wishlist count to all templates"""
    if request.user.is_authenticated:
        try:
            cart_count = Cart.objects.filter(user=request.user).count()
            wishlist_count = Wishlist.objects.filter(user=request.user).count()
            return {
                'cart_count': cart_count,
                'wishlist_count': wishlist_count
            }
        except:
            # Handle case when models aren't migrated yet
            return {'cart_count': 0, 'wishlist_count': 0}
    return {'cart_count': 0, 'wishlist_count': 0}