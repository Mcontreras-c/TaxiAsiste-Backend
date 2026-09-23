import secrets

# Sin caracteres ambiguos (0/O, 1/l/I) -- se va a leer y tipear a mano desde
# un correo, en un celular, muchas veces por alguien que no es técnico.
ALFABETO_CLAVE = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
LARGO_CLAVE = 8


def generar_clave() -> str:
    return ''.join(secrets.choice(ALFABETO_CLAVE) for _ in range(LARGO_CLAVE))
