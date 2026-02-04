from django.shortcuts import redirect
from django.urls import reverse

class SessionExpiryMiddleware:
    """Middleware: Redirige suavemente sesiones expiradas SIN 404"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Solo para requests autenticados que fallan
        if (request.user.is_authenticated and 
            'sessionid' not in request.COOKIES):
            # Sesión expiró → login limpio
            return redirect(reverse('login') + '?expired=1')
        
        return response
