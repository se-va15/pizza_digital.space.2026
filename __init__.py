from .start import router as start_router
from .menu import router as menu_router
from .order import router as order_router
from .cancel import router as cancel_router
from .feedback import router as feedback_router
from .history import router as history_router
from .admin import router as admin_router

__all__ = [
    'start_router',
    'menu_router',
    'order_router',
    'cancel_router',
    'feedback_router',
    'history_router',
    'admin_router',
]