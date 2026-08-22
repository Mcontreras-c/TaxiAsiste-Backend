from rest_framework.routers import SimpleRouter


class DecimalPkRouter(SimpleRouter):
    """
    Todas las PK del proyecto son FloatField (managed=False sobre Oracle
    NUMBER sin escala fija — ver utils/oracle_seq.py) y por lo tanto se
    serializan en JSON como '4.0', no '4'. El patron por defecto de DRF para
    la URL de detalle excluye el punto ('[^/.]+', pensado para poder
    distinguir la PK de un sufijo de formato como '.json'), asi que
    cualquier accion sobre un registro puntual armada con un ID que vino de
    una respuesta JSON anterior (el caso normal: el Frontend/Mobile jamas
    fabrican un ID a mano) devolvia 404 en vez de encontrar el registro.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_value_pattern = r'[^/]+'
