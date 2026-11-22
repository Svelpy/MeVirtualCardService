from fastapi import APIRouter

from app.core.system_router import router as system_router
from app.domains.auth.routes import router as auth_router
from app.domains.imagenes.routes import router as imagenes_router
from app.domains.pago.routes import router as pago_router
from app.domains.plan.routes import router as plan_router
from app.domains.tarjeta.routes import router as tarjeta_router
from app.domains.tarjeta_certificacion.routes import router as tarjeta_certificacion_router
from app.domains.tarjeta_contacto.routes import router as tarjeta_contacto_router
from app.domains.tarjeta_educacion.routes import router as tarjeta_educacion_router
from app.domains.tarjeta_faq.routes import router as tarjeta_faq_router
from app.domains.tarjeta_seccion.routes import router as tarjeta_seccion_router
from app.domains.tarjeta_seo.routes import router as tarjeta_seo_router
from app.domains.tarjeta_social.routes import router as tarjeta_social_router
from app.domains.tarjeta_theme.routes import router as tarjeta_theme_router
from app.domains.tarjeta_ubicacion.routes import router as tarjeta_ubicacion_router
from app.domains.ubicacion_horario.routes import router as ubicacion_horario_router
from app.domains.usuario.routes import router as usuario_router
from app.domains.vitrina.routes import router as vitrina_router
from app.domains.vitrina_categoria.routes import router as vitrina_categoria_router
from app.domains.vitrina_item.routes import router as vitrina_item_router
from app.domains.vitrina_item_imagen.routes import router as vitrina_item_imagen_router


no_system_router = APIRouter(prefix="/api/v1")
no_system_router.include_router(auth_router)
no_system_router.include_router(imagenes_router)
no_system_router.include_router(plan_router)
no_system_router.include_router(usuario_router)
no_system_router.include_router(pago_router)
no_system_router.include_router(tarjeta_router)
no_system_router.include_router(tarjeta_theme_router)
no_system_router.include_router(tarjeta_seo_router)
no_system_router.include_router(tarjeta_seccion_router)
no_system_router.include_router(tarjeta_contacto_router)
no_system_router.include_router(tarjeta_ubicacion_router)
no_system_router.include_router(ubicacion_horario_router)
no_system_router.include_router(tarjeta_social_router)
no_system_router.include_router(tarjeta_educacion_router)
no_system_router.include_router(tarjeta_certificacion_router)
no_system_router.include_router(tarjeta_faq_router)
no_system_router.include_router(vitrina_router)
no_system_router.include_router(vitrina_categoria_router)
no_system_router.include_router(vitrina_item_router)
no_system_router.include_router(vitrina_item_imagen_router)

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(no_system_router)
