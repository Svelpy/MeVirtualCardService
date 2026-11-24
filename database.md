# database.md

SQL de PostgreSQL del sistema de tarjetas digitales. Es la entrada del §25 de
`AGENTS.md`.

Convenciones de este archivo:

- Las columnas de auditoría (`created_at`, `created_by`, `updated_at`,
  `updated_by`, `is_deleted`, `deleted_at`, `deleted_by`) no se escriben: las
  aporta `BaseModel` en todas las tablas.
- Los `id` los genera `BaseModel`; no llevan `DEFAULT gen_random_uuid()`.
- Todo `UNIQUE` es único **solo entre registros no eliminados** (índice único
  parcial, §19).
- Los comentarios `-- contengo` y `-- apunto` adelantan la clasificación de la
  relación (§17).

```sql
-- =================================================================
-- Enums
-- =================================================================

CREATE TYPE rol_usuario AS ENUM ('user', 'admin', 'superadmin');
CREATE TYPE metodo_pago AS ENUM ('qr', 'transferencia', 'tarjeta', 'efectivo', 'otro');
CREATE TYPE posicion_nombre_empresa AS ENUM ('arriba', 'abajo', 'izquierda', 'derecha', 'oculto');
CREATE TYPE preset_theme AS ENUM (
    'claro', 'oscuro', 'elegante', 'salud', 'corporativo', 'calido', 'natural', 'belleza', 'creativo', 'energia'
);
CREATE TYPE forma_icono AS ENUM ('circulo', 'redondeado', 'cuadrado', 'ninguno');
CREATE TYPE posicion_fab AS ENUM ('derecha', 'izquierda');
CREATE TYPE clave_seccion AS ENUM (
    'acerca', 'contacto', 'vitrina', 'ubicacion', 'redes', 'educacion', 'certificaciones', 'faq'
);
CREATE TYPE tipo_contacto AS ENUM ('phone', 'email', 'website');
CREATE TYPE red_social AS ENUM (
    'facebook', 'instagram', 'tiktok', 'x', 'threads', 'bluesky', 'pinterest', 'linkedin',
    'youtube', 'twitch', 'vimeo', 'spotify', 'soundcloud', 'medium', 'substack', 'github',
    'gitlab', 'behance', 'dribbble', 'telegram', 'discord', 'calendly', 'doctoralia', 'otro'
);


-- =================================================================
-- Planes y pagos
-- =================================================================

-- Filas fijas: free, pro y business se siembran en la migración con claves
-- fijas. Un administrador ajusta todo menos el código.
CREATE TABLE plan (
    id            uuid PRIMARY KEY,
    codigo        varchar(10)   NOT NULL UNIQUE,              -- free | pro | business
    nombre        varchar(60)   NOT NULL,
    precio        numeric(12,2) NOT NULL CHECK (precio >= 0), -- free = 0, pro = 80, business = 200
    moneda        char(3)       NOT NULL DEFAULT 'USD',       -- ISO 4217
    duracion_dias smallint      NOT NULL CHECK (duracion_dias > 0), -- free = 7, pro = 365, business = 365
    is_visible    boolean       NOT NULL DEFAULT true
);

CREATE TABLE usuario (
    id            uuid PRIMARY KEY,
    email         varchar(255) NOT NULL UNIQUE,  -- se guarda en minúsculas
    password_hash text         NOT NULL,         -- argon2
    rol           rol_usuario  NOT NULL DEFAULT 'user',
    plan_id       uuid         NOT NULL REFERENCES plan(id),  -- apunto
    -- Estado actual del plan. Lo calcula el service en la misma transacción
    -- que inserta el pago; al registrarse: created_at + duracion_dias de free.
    plan_vence_at timestamptz  NOT NULL,
    -- Baja sin eliminar. Es un estado: solo cambia con endpoints de acción
    -- (dar de baja / reactivar). Un usuario inactivo no inicia sesión.
    is_active         boolean     NOT NULL DEFAULT true,
    -- NULL = email sin verificar. Vuelve a NULL al cambiar el email. Sin
    -- verificar, el usuario no puede publicar su tarjeta.
    email_verified_at timestamptz
);

-- Registro (kardex, §19): solo INSERT. Un reembolso o una anulación es un
-- asiento de reverso con reverses_id; el original no se toca.
CREATE TABLE pago (
    id                 uuid PRIMARY KEY,
    user_id            uuid          NOT NULL REFERENCES usuario(id),  -- apunto (bloquea eliminar al usuario)
    plan_id            uuid          NOT NULL REFERENCES plan(id),     -- apunto
    monto              numeric(12,2) NOT NULL,
    moneda             char(3)       NOT NULL,
    metodo             metodo_pago   NOT NULL,
    referencia_externa varchar(100),           -- id de la transacción en el banco o la pasarela
    comprobante_url    text,                   -- https
    periodo_inicio     timestamptz   NOT NULL,
    periodo_fin        timestamptz   NOT NULL,
    reverses_id        uuid UNIQUE REFERENCES pago(id),
    idempotency_key    varchar(64)   NOT NULL UNIQUE,
    CONSTRAINT periodo_valido CHECK (periodo_fin > periodo_inicio),
    -- Un pago es positivo; su reverso, negativo.
    CONSTRAINT signo_del_monto CHECK (
        (reverses_id IS NULL AND monto >= 0) OR (reverses_id IS NOT NULL AND monto <= 0)
    )
);


-- =================================================================
-- Tarjeta
-- =================================================================

CREATE TABLE tarjeta (
    id                       uuid PRIMARY KEY,
    user_id                  uuid         NOT NULL UNIQUE REFERENCES usuario(id), -- 1 tarjeta por usuario
    -- Se puede editar. Al cambiarlo o al eliminar la tarjeta, el slug anterior
    -- queda libre: los enlaces con el slug viejo dejan de funcionar, pero el QR
    -- no. El QR lo genera el frontend y codifica /t/{id}, que redirige al slug
    -- actual: nunca se rompe al cambiar el slug ni lleva a la tarjeta de otra
    -- persona.
    slug                     varchar(80)  NOT NULL UNIQUE,
    rubro                    varchar(150) NOT NULL,
    prefijo                  varchar(30),          -- Dr. Dra. Ing.
    nombres                  varchar(150) NOT NULL,
    apellidos                varchar(150),
    cargo                    varchar(150),
    nombre_empresa           varchar(200),
    acerca_de_mi             text,
    profile_url              text,                 -- https
    photo_usuario_url        text,                 -- https
    logo_empresa_url         text,                 -- https
    nombre_empresa_posicion  posicion_nombre_empresa NOT NULL DEFAULT 'derecha',
    cover_url                text,                 -- https
    qr_pago_url              text,                 -- https
    is_public                boolean      NOT NULL DEFAULT false,
    published_at             timestamptz,
    CONSTRAINT slug_formato CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(slug) BETWEEN 3 AND 80),
    CONSTRAINT publicada_con_fecha CHECK (NOT is_public OR published_at IS NOT NULL)
);
-- Extensiones 1:1: su id es el id de la tarjeta (§18).
CREATE TABLE tarjeta_theme (
    id                            uuid PRIMARY KEY REFERENCES tarjeta(id),  -- contengo uno
    preset                        preset_theme,
    tipografia                    smallint    NOT NULL DEFAULT 1,  -- id del par de fuentes en TIPOGRAFIAS_TARJETA del frontend
    -- Todos los color_*: #RRGGBB (validator_hex_color). Al crear, toman los
    -- valores del preset.
    color_fondo                   char(7)     NOT NULL,
    color_superficie              char(7)     NOT NULL,
    color_borde                   char(7)     NOT NULL,
    color_titulo                  char(7)     NOT NULL,
    color_texto                   char(7)     NOT NULL,
    color_texto_secundario        char(7)     NOT NULL,
    color_primario                char(7)     NOT NULL,
    color_texto_sobre_primario    char(7)     NOT NULL,
    color_secundario              char(7)     NOT NULL,
    color_texto_sobre_secundario  char(7)     NOT NULL,
    color_overlay_portada         char(7)     NOT NULL DEFAULT '#000000',
    overlay_opacidad              smallint    NOT NULL DEFAULT 40 CHECK (overlay_opacidad BETWEEN 0 AND 100),
    color_precio                  char(7)     NOT NULL,
    color_destacado               char(7)     NOT NULL,
    color_texto_sobre_destacado   char(7)     NOT NULL,
    color_icono                   char(7)     NOT NULL,
    color_fondo_icono             char(7)     NOT NULL,
    icono_forma                   forma_icono NOT NULL DEFAULT 'circulo',
    color_icono_social            char(7)     NOT NULL,
    color_fondo_icono_social      char(7)     NOT NULL,
    color_fab_fondo               char(7)     NOT NULL,
    color_fab_icono               char(7)     NOT NULL,
    fab_posicion                  posicion_fab NOT NULL DEFAULT 'derecha'
);

CREATE TABLE tarjeta_seo (
    id               uuid PRIMARY KEY REFERENCES tarjeta(id),  -- contengo uno
    meta_title       varchar(70),   -- NULL = se genera
    meta_description varchar(160),  -- NULL = se genera
    og_image_url     text,          -- NULL = profile_url
    robots_index     boolean NOT NULL DEFAULT true
);

-- Filas fijas por tarjeta: las 8 secciones se crean junto con la tarjeta.
CREATE TABLE tarjeta_seccion (
    id         uuid PRIMARY KEY,
    tarjeta_id uuid          NOT NULL REFERENCES tarjeta(id),  -- contengo, pocos (máx. 8)
    clave      clave_seccion NOT NULL,
    titulo     varchar(80),
    is_visible boolean       NOT NULL DEFAULT true,
    orden      smallint      NOT NULL DEFAULT 0,
    UNIQUE (tarjeta_id, clave)
);

CREATE TABLE tarjeta_contacto (
    id         uuid PRIMARY KEY,
    tarjeta_id uuid          NOT NULL REFERENCES tarjeta(id),  -- contengo
    tipo       tipo_contacto NOT NULL,
    valor      varchar(255)  NOT NULL,  -- número, correo o URL, según tipo
    etiqueta   varchar(60),             -- Celular, Consultorio
    is_wpp     boolean       NOT NULL DEFAULT false,
    is_primary boolean       NOT NULL DEFAULT false,
    is_visible boolean       NOT NULL DEFAULT true,
    orden      smallint      NOT NULL DEFAULT 0,
    CONSTRAINT wpp_solo_en_telefono CHECK (NOT is_wpp OR tipo = 'phone')
);
-- Un solo contacto principal por tipo en cada tarjeta.
CREATE UNIQUE INDEX uq_tarjeta_contacto_principal ON tarjeta_contacto (tarjeta_id, tipo) WHERE is_primary;

CREATE TABLE tarjeta_ubicacion (
    id           uuid PRIMARY KEY,
    tarjeta_id   uuid         NOT NULL REFERENCES tarjeta(id),  -- contengo
    nombre       varchar(150),         -- Consultorio Norte
    direccion    varchar(255) NOT NULL,
    ciudad       varchar(100),
    departamento varchar(100),
    pais         varchar(100),
    maps_url     text,                 -- ficha de Google
    lat          numeric(9,6),
    lng          numeric(9,6),
    is_visible   boolean      NOT NULL DEFAULT true,
    orden        smallint     NOT NULL DEFAULT 0,
    CONSTRAINT coordenadas_juntas CHECK ((lat IS NULL) = (lng IS NULL)),
    CONSTRAINT latitud_valida CHECK (lat BETWEEN -90 AND 90),
    CONSTRAINT longitud_valida CHECK (lng BETWEEN -180 AND 180)
);

-- No admite horarios que crucen la medianoche. El service rechaza tramos que
-- se solapan en un mismo día.
CREATE TABLE ubicacion_horario (
    id           uuid PRIMARY KEY,
    ubicacion_id uuid     NOT NULL REFERENCES tarjeta_ubicacion(id),  -- contengo, pocos (máx. 21)
    dia_semana   smallint NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),  -- 1 lunes a 7 domingo
    hora_inicio  time     NOT NULL,
    hora_fin     time     NOT NULL,
    CONSTRAINT tramo_valido CHECK (hora_fin > hora_inicio),
    UNIQUE (ubicacion_id, dia_semana, hora_inicio)
);

CREATE TABLE tarjeta_social (
    id         uuid PRIMARY KEY,
    tarjeta_id uuid       NOT NULL REFERENCES tarjeta(id),  -- contengo
    red        red_social NOT NULL,
    url        text       NOT NULL,  -- https
    username   varchar(100),
    is_visible boolean    NOT NULL DEFAULT true,
    orden      smallint   NOT NULL DEFAULT 0,
    UNIQUE (tarjeta_id, red)          -- una cuenta por red
);

CREATE TABLE tarjeta_educacion (
    id           uuid PRIMARY KEY,
    tarjeta_id   uuid         NOT NULL REFERENCES tarjeta(id),  -- contengo
    institucion  varchar(200) NOT NULL,
    titulo       varchar(200),
    area_estudio varchar(200),
    descripcion  text,
    fecha_inicio date,
    fecha_fin    date,
    is_actual    boolean      NOT NULL DEFAULT false,
    is_visible   boolean      NOT NULL DEFAULT true,
    orden        smallint     NOT NULL DEFAULT 0,
    CONSTRAINT fechas_ordenadas CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio),
    CONSTRAINT actual_sin_fin CHECK (NOT is_actual OR fecha_fin IS NULL)
);

CREATE TABLE tarjeta_certificacion (
    id                uuid PRIMARY KEY,
    tarjeta_id        uuid         NOT NULL REFERENCES tarjeta(id),  -- contengo
    nombre            varchar(200) NOT NULL,
    entidad_emisora   varchar(200),
    codigo_credencial varchar(150),
    url_credencial    text,         -- https
    fecha_emision     date,
    fecha_expiracion  date,
    no_expira         boolean      NOT NULL DEFAULT false,
    descripcion       text,
    is_visible        boolean      NOT NULL DEFAULT true,
    orden             smallint     NOT NULL DEFAULT 0,
    CONSTRAINT fechas_ordenadas CHECK (fecha_expiracion IS NULL OR fecha_emision IS NULL OR fecha_expiracion >= fecha_emision),
    CONSTRAINT sin_expiracion CHECK (NOT no_expira OR fecha_expiracion IS NULL)
);

CREATE TABLE tarjeta_faq (
    id         uuid PRIMARY KEY,
    tarjeta_id uuid         NOT NULL REFERENCES tarjeta(id),  -- contengo
    pregunta   varchar(300) NOT NULL,
    respuesta  text         NOT NULL,
    is_visible boolean      NOT NULL DEFAULT true,
    orden      smallint     NOT NULL DEFAULT 0
);


-- =================================================================
-- Vitrina
-- =================================================================

CREATE TABLE vitrina (
    id              uuid PRIMARY KEY REFERENCES tarjeta(id),  -- contengo uno
    mostrar_precios boolean NOT NULL DEFAULT true,
    moneda          char(3) NOT NULL DEFAULT 'BOB',  -- ISO 4217
    campo1_nombre   varchar(40),  -- NULL = campo no usado
    campo2_nombre   varchar(40),
    campo3_nombre   varchar(40),
    campo4_nombre   varchar(40)
);

CREATE TABLE vitrina_categoria (
    id         uuid PRIMARY KEY,
    vitrina_id uuid        NOT NULL REFERENCES vitrina(id),  -- contengo
    nombre     varchar(60) NOT NULL,
    is_visible boolean     NOT NULL DEFAULT true,
    orden      smallint    NOT NULL DEFAULT 0,
    UNIQUE (vitrina_id, nombre),
    -- Destino de la foreign key compuesta de vitrina_item: garantiza que un
    -- item solo use categorías de su misma vitrina.
    UNIQUE (id, vitrina_id)
);

CREATE TABLE vitrina_item (
    id              uuid PRIMARY KEY,
    vitrina_id      uuid          NOT NULL REFERENCES vitrina(id),  -- contengo, pocos (máx. 25)
    categoria_id    uuid,                                           -- apunto; un item en una sola categoría o en ninguna
    titulo          varchar(150)  NOT NULL,
    descripcion     text,
    precio          numeric(12,2),           -- NULL = Consultar
    precio_anterior numeric(12,2),
    precio_etiqueta varchar(50),             -- Desde, por sesión
    campo1          varchar(100),
    campo2          varchar(100),
    campo3          varchar(100),
    campo4          varchar(100),
    destacado       boolean       NOT NULL DEFAULT false,
    is_visible      boolean       NOT NULL DEFAULT true,
    orden           smallint      NOT NULL DEFAULT 0,
    FOREIGN KEY (categoria_id, vitrina_id) REFERENCES vitrina_categoria (id, vitrina_id),
    CONSTRAINT precio_no_negativo CHECK (precio IS NULL OR precio >= 0),
    CONSTRAINT precio_anterior_mayor CHECK (precio_anterior IS NULL OR (precio IS NOT NULL AND precio_anterior > precio))
);

CREATE TABLE vitrina_item_imagen (
    id      uuid PRIMARY KEY,
    item_id uuid         NOT NULL REFERENCES vitrina_item(id),  -- contengo, pocos (máx. 3)
    url     text         NOT NULL,  -- https
    alt     varchar(150),
    orden   smallint     NOT NULL DEFAULT 0  -- 0 = principal
);
-- Una sola imagen principal por item.
CREATE UNIQUE INDEX uq_vitrina_item_imagen_principal ON vitrina_item_imagen (item_id) WHERE orden = 0;
```
