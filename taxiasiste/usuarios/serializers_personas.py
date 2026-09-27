import re

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Rol, Usuario
from .passwords import generar_clave
from .serializers import normalizar_telefono
from .validaciones import normalizar_patente, normalizar_rut, validar_correo_real


class VehiculoNuevoSerializer(serializers.Serializer):
    patente = serializers.CharField(max_length=10)
    marca = serializers.CharField(max_length=50)
    modelo = serializers.CharField(max_length=50)
    anio = serializers.IntegerField(min_value=1980, max_value=timezone.localdate().year + 1, required=False, allow_null=True)
    color = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_patente(self, valor):
        from taxiasiste.moviles.models import Movil

        patente = normalizar_patente(valor)
        if Movil.objects.filter(patente=patente).exists():
            raise serializers.ValidationError('Ya existe un vehículo con esa patente.')
        return patente


class ConductorNuevoSerializer(serializers.Serializer):
    """
    Alta completa de un conductor en una sola operacion: socio + vehiculo + cuenta
    de acceso. Todo o nada; las credenciales salen por correo (nunca se devuelven).
    """

    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    rut = serializers.CharField(max_length=14)
    email = serializers.EmailField(max_length=100)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    direccion = serializers.CharField(max_length=200, required=False, allow_blank=True)
    fecha_ingreso = serializers.DateField(required=False)
    username = serializers.CharField(max_length=50, required=False, allow_blank=True)
    vehiculo = VehiculoNuevoSerializer()

    def validate_rut(self, valor):
        from taxiasiste.socios.models import Socio

        rut = normalizar_rut(valor)
        if Socio.objects.filter(rut=rut).exists():
            raise serializers.ValidationError('Ya existe un socio con ese RUT.')
        return rut

    def validate_email(self, valor):
        return validar_correo_real(valor)

    def validate_telefono(self, valor):
        return normalizar_telefono(valor)

    def validate_username(self, valor):
        valor = valor.strip().lower()
        if valor and Usuario.objects.filter(username__iexact=valor).exists():
            raise serializers.ValidationError('Ese nombre de usuario ya existe.')
        return valor

    @staticmethod
    def _generar_username(nombre, apellido):
        base = re.sub(r'[^a-z0-9]', '', f'{nombre[:1]}{apellido.split()[0]}'.lower()) or 'conductor'
        candidato, n = base, 1
        while Usuario.objects.filter(username__iexact=candidato).exists():
            n += 1
            candidato = f'{base}{n}'
        return candidato

    @transaction.atomic
    def create(self, datos):
        from taxiasiste.moviles.models import Movil
        from taxiasiste.socios.models import Socio

        vehiculo = datos.pop('vehiculo')
        clave = generar_clave()
        usuario = Usuario.objects.create(
            rol=Rol.objects.get(nombre_rol='Conductor'),
            username=datos.get('username') or self._generar_username(datos['nombre'], datos['apellido']),
            email=datos['email'],
            password_hash=make_password(clave),
            fecha_creacion=timezone.localdate(),
        )
        socio = Socio.objects.create(
            usuario=usuario, rut=datos['rut'], nombre=datos['nombre'].strip(), apellido=datos['apellido'].strip(),
            telefono=datos.get('telefono'), direccion=datos.get('direccion') or None,
            fecha_ingreso=datos.get('fecha_ingreso') or timezone.localdate(),
        )
        movil = Movil.objects.create(
            socio=socio, patente=vehiculo['patente'], marca=vehiculo['marca'], modelo=vehiculo['modelo'],
            anio=vehiculo.get('anio'), color=vehiculo.get('color') or None,
            estado_operativo='DISPONIBLE', fecha_registro=timezone.localdate(),
        )
        return usuario, socio, movil, clave
