from fastapi import APIRouter

from app.api.v1.auth.admin_driver_link import router as admin_driver_link_router
from app.api.v1.auth.admin_verification import router as admin_verification_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.bookings.router import router as bookings_router
from app.api.v1.core.health import router as health_router
from app.api.v1.core.root import router as root_router
from app.api.v1.drivers.router import router as drivers_router
from app.api.v1.invoices.admin_router import router as admin_invoices_router
from app.api.v1.invoices.router import router as invoices_router
from app.api.v1.logs.router import router as logs_router
from app.api.v1.mail.router import router as mail_router
from app.api.v1.payments.router import router as payments_router
from app.api.v1.routing.router import router as routing_router
from app.api.v1.users.router import router as users_router
from app.api.v1.viator.router import router as viator_router


def build_v1_router() -> APIRouter:
    router = APIRouter()
    router.include_router(root_router)
    router.include_router(health_router)
    router.include_router(logs_router)
    router.include_router(auth_router)
    router.include_router(admin_verification_router)
    router.include_router(admin_driver_link_router)
    router.include_router(admin_invoices_router)
    router.include_router(bookings_router)
    router.include_router(drivers_router)
    router.include_router(invoices_router)
    router.include_router(users_router)
    router.include_router(mail_router)
    router.include_router(routing_router)
    router.include_router(payments_router)
    router.include_router(viator_router)
    return router
