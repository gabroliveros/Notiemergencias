# -*- coding: utf-8 -*-
"""
Diccionarios y listas geográficas/temáticas usadas por limpieza_clasificacion.py.
Extraídos y ordenados desde procesamiento_busquedas_motor_final.ipynb, sin cambios
de contenido (solo de organización).
"""

# --------------------------------------------------------------------------
# Categorías temáticas de emergencia (zonas, afectación, logística, eventos)
# --------------------------------------------------------------------------
EMERGENCIAS = {
    # Zonas geográficas y demográficas
    'capital': ['caracas', 'miranda', 'distrito capital', 'vargas', 'la guaira', 'chacao', 'baruta', 'el hatillo', 'petare', 'catia', 'gran caracas'],
    'andes': ['merida', 'tachira', 'trujillo', 'bocono', 'valera', 'san cristobal', 'el vigia', 'paramo', 'andes', 'cordillera andina'],
    'oriente': ['sucre', 'anzoategui', 'monagas', 'nueva esparta', 'margarita', 'cumana', 'lecheria', 'maturin', 'carupano', 'oriente'],
    'occidente': ['zulia', 'falcon', 'lara', 'yaracuy', 'maracaibo', 'punto fijo', 'barquisimeto', 'coro', 'occidente'],
    'llanos': ['apure', 'barinas', 'portuguesa', 'cojedes', 'guarico', 'san fernando', 'guanare', 'calabozo', 'llanos', 'apureño'],
    'costa': ['costa', 'litoral', 'playa', 'mar', 'choroni', 'ocumare', 'puerto cabello', 'costero', 'morrocoy'],
    'barrio': ['barrio', 'cerro', 'sector popular', 'rancho', 'vivienda precaria', 'asentamiento', 'comunidad', 'invasión'],
    'urbanizacion': ['urbanizacion', 'residencias', 'edificio', 'condominio', 'quinta', 'calle', 'avenida', 'conjunto'],

    # Nivel de afectación / consecuencias
    'daños': ['daño', 'destruccion', 'colapso', 'escombros', 'perdida', 'ruina', 'afectacion', 'grieta', 'desplome', 'siniestro', 'viviendas afectadas'],
    'victimas': ['victima', 'fallecido', 'muerto', 'herido', 'lesionado', 'desaparecido', 'damnificado', 'cadaver', 'atrapado', 'deceso'],
    'rescate': ['rescate', 'salvamento', 'evacuacion', 'bomberos', 'proteccion civil', 'paramedicos', 'busqueda', 'sobreviviente', 'inparques', 'voluntarios'],

    # Atención, salud y refugio
    'atencion': ['refugio', 'albergue', 'cancha', 'iglesia', 'hospital', 'clinica', 'cdi', 'ambulatorio', 'carpa', 'campamento', 'triaje', 'acopio', 'donacion', 'insumos', 'medicinas', 'alimentos', 'agua potable'],

    # Tipos de eventos y desastres
    'eventos': [
        'sismo', 'terremoto', 'temblor', 'replica', 'escala richter', 'inundacion', 'anegacion',
        'desbordamiento', 'crecida', 'deslave', 'derrumbe', 'deslizamiento', 'alud', 'barro',
        'aguacero', 'tormenta', 'precipitaciones', 'vaguada', 'lluvia', 'onda tropical',
        # Sequía (agregado)
        'sequia', 'racionamiento', 'escasez de agua', 'embalses bajos', 'nivel de embalses',
        # Huracán / ciclón tropical (agregado)
        'huracan', 'tormenta tropical', 'ciclon', 'vientos huracanados', 'marejada',
    ],
}

# Subcategorías usadas para agrupar/renombrar frecuencias (ver frecuencias() en limpieza_clasificacion.py)
EQUIVALENCIAS_FRECUENCIA = {
    'atencion': {
        'refugio': ['refugio', 'albergue', 'carpa', 'campamento'],
        'hospital': ['hospital', 'clinica', 'cdi', 'ambulatorio', 'barrio adentro', 'triaje'],
        'centro_acopio': ['acopio', 'donaciones', 'recoleccion'],
    },
    'eventos': {
        'sismo': ['tembl', 'tiembla', 'terremoto', 'replica', 'sismo', 'sismic', 'escala de richter', 'funvisis'],
        'lluvias': ['aguacero', 'tormenta', 'precipitaciones', 'vaguada', 'inund', 'aneg', 'desbordamiento', 'crecida del',
                    'deslave', 'deslizamiento', 'alud', 'onda tropical'],
        'huracan': ['huracan', 'huracanados', 'ventarron', 'tornado', 'rafagas de viento', 'ventisca'],
        'sequia': ['sequia', 'estres hidrico', 'deshidratacion', 'desierto']
    },
}

# --------------------------------------------------------------------------
# Filtro de países distintos a Venezuela (para excluir ruido de otros países)
# --------------------------------------------------------------------------
AMERICANOS = {
    'bra': ['brasil', 'brazil'], 'chi': ['chile'], 'arg': ['argentin', 'buenos aires'],
    'col': ['colombia', 'medellin', 'bogota'], 'pan': ['panama', 'panameñ'], 'per': ['peru'],
    'uru': ['uruguay', 'montevideo'], 'ecu': ['ecuador', 'ecuatorian', 'manabi'],
    'prc': ['puerto rico', 'puertoriqueñ'], 'crc': ['costa rica', 'costaricense'],
    'usa': ['estados unidos', 'eeuu', 'estadounidense'], 'esp': ['españa', 'español'],
    'cub': ['cuba', 'cuban'], 'mex': ['mexico', 'mexican'], 'rdo': ['republica dominicana', 'dominican'],
    'gua': ['guatemala', 'guatemaltec'], 'bar': ['barbados', 'barbadens'], 'bol': ['bolivia'],
    'par': ['paraguay'], 'sal': ['el salvador', 'salvadoreñ'], 'tri': ['trinidad y tobago', 'trinitari'],
    'bel': ['belice'], 'hon': ['honduras', 'hondureñ'], 'nic': ['nicaragua', 'nicaragüense', 'nicaraguense'],
    'gra': ['granada', 'granadin'], 'guy': ['guyana', 'guyanes'], 'sur': ['surinam'], 'hai': ['haiti'],
    'can': ['canad'], 'cur': ['curaz'], 'aru': ['aruba', 'arube'],
}

OTROS_LUGARES_NO_VZLA = (
    r'espana|mar caribe|europa|italia|nueva segovia|cordoba|francia| nong|veracruz|valparaiso|yucatan|'
    r'portugal|venecia|monte alegre|tenerife|vietnam|australia|america del sur|rio de janeiro|miami|'
    r'istmo caribe| lima|madrid|baja california|bariloche|manongo|alaska|america|santa fe|'
    r'el quisco|aruba|antioquia|costa azul|santiago del estero|san jose|punta palma| china|'
    r'santiago de chile|valle del cauca|cartagena|canada|sudamerica|alemania|cucuta|rusia|grecia|curazao|'
    r'nahuel huapi|destructor|armada|militar|narcotrafico|ataque|trump|next day cargo|matanzas| fallec|'
    r'terrorista|criminal|atentado|explosion|incendio|cuartel moncada|petrole| migra| migro| inmigr| emigr'
)

EXTRA_RUIDO = (
    r'shop| tienda|trabajo|empleo|vacante|contratamos|postula| curso| clase| beca|inscripci[oó]n|'
    r'chavismo|oposici[oó]n|elecciones|protest|manifest|notici|asesin| robo|secuestr| herido|balacera|'
    r'accident|emergencia|sexo|porn| eroti|sensual|concierto|[aá]lbum|periodico|unlimited|4x2|4x4|'
    r'multiventas|repuestos| envio|todo jeep|envios maritimos|expobici|endoparasitos|resonancia'
)

# --------------------------------------------------------------------------
# División político-territorial de Venezuela
# --------------------------------------------------------------------------
ESTADOS = [
    'amazonas', 'anzoategui', 'apure', 'aragua', 'barinas', 'bolivar', 'carabobo', 'cojedes', 'delta amacuro',
    'dependencias federales', 'distrito capital', 'falcon', 'guarico', 'lara', 'la guaira', 'merida', 'miranda',
    'monagas', 'nueva esparta', 'portuguesa', 'sucre', 'tachira', 'trujillo', 'yaracuy', 'zulia',
]

MUNICIPIOS = [
    'alto orinoco', 'atures', 'autana', 'manapiare', 'maroa', 'rio negro', 'anaco', 'aragua', 'manuel ezequiel bruzual',
    'diego bautista urbaneja', 'fernando penalver', 'francisco del carmen carvajal', 'general sir arthur mcgregor',
    'guanta', 'independencia', 'jose gregorio monagas', 'juan antonio sotillo', 'juan manuel cajigal',
    'francisco de miranda', 'pedro maria freites', 'piritu', 'san jose de guanipa', 'san juan de capistrano',
    'santa ana', 'simon bolivar', 'simon rodriguez', 'achaguas', 'biruaca', 'munoz', 'paez', 'pedro camejo',
    'romulo gallegos', 'san fernando', 'atanasio girardot', 'bolivar', 'camatagua', 'francisco linares alcantara',
    'jose angel lamas', 'jose felix ribas', 'jose rafael revenga', 'libertador', 'mario briceno iragorry',
    'ocumare de la costa de oro', 'san casimiro', 'san sebastian', 'santiago marino', 'santos michelena',
    'urdaneta', 'zamora', 'alberto arvelo torrealba', 'andres eloy blanco', 'antonio jose de sucre', 'arismendi',
    'barinas', 'cruz paredes', 'ezequiel zamora', 'obispos', 'pedraza', 'rojas', 'sosa', 'caroni', 'cedeno',
    'el callao', 'gran sabana', 'heres', 'piar', 'angostura', 'roscio', 'sifontes', 'padre pedro chien', 'bejuma',
    'carlos arvelo', 'diego ibarra', 'guacara', 'juan jose mora', 'los guayos', 'miranda', 'montalban',
    'naguanagua', 'puerto cabello', 'san diego', 'san joaquin', 'valencia', 'anzoategui', 'tinaquillo',
    'girardot', 'lima blanco', 'pao de san juan bautista', 'ricaurte', 'san carlos', 'tinaco', 'antonio diaz',
    'casacoima', 'pedernales', 'tucupita', 'buchivacoa', 'cacique manaure', 'carirubana', 'colina', 'dabajuro',
    'falcon', 'federacion', 'jacura', 'jose laurencio silva', 'los taques', 'mauroa', 'monsenor iturriza',
    'palmasola', 'petit', 'san francisco', 'tocopero', 'union', 'urumaco', 'camaguan', 'chaguaramas',
    'el socorro', 'jose tadeo monagas', 'juan german roscio', 'julian mellado', 'las mercedes', 'leonardo infante',
    'pedro zaraza', 'ortiz', 'san geronimo de guayabal', 'san jose de guaribe', 'santa maria de ipire',
    'sebastian francisco de miranda', 'crespo', 'iribarren', 'jimenez', 'moran', 'palavecino', 'simon planas',
    'torres', 'alberto adriani', 'andres bello', 'antonio pinto salinas', 'aricagua', 'arzobispo chacon',
    'campo elias', 'caracciolo parra olmedo', 'cardenal quintero', 'guaraque', 'julio cesar salas', 'justo briceno',
    'obispo ramos de lora', 'padre noguera', 'pueblo llano', 'rangel', 'rivas davila', 'santos marquina',
    'tulio febres cordero', 'zea', 'acevedo', 'baruta', 'brion', 'buroz', 'carrizal', 'chacao', 'cristobal rojas',
    'el hatillo', 'guaicaipuro', 'lander', 'los salias', 'paz castillo', 'pedro gual', 'plaza', 'aguasay',
    'caripe', 'maturin', 'punceres', 'santa barbara', 'sotillo', 'uracoa', 'antolin del campo', 'garcia',
    'gomez', 'maneiro', 'marcano', 'marino', 'peninsula de macanao', 'tubores', 'villalba', 'diaz',
    'agua blanca', 'araure', 'esteller', 'guanare', 'guanarito', 'monsenor jose vicente de unda', 'ospino',
    'papelon', 'san genaro de boconoito', 'san rafael de onoto', 'santa rosalia', 'turen', 'andres mata',
    'benitez', 'bermudez', 'cajigal', 'cruz salmeron acosta', 'mejia', 'montes', 'ribero', 'valdez',
    'antonio romulo costa', 'ayacucho', 'cardenas', 'cordoba', 'fernandez feo', 'garcia de hevia', 'guasimos',
    'jauregui', 'jose maria vargas', 'junin', 'lobatera', 'michelena', 'panamericano', 'pedro maria urena',
    'rafael urdaneta', 'samuel dario maldonado', 'san cristobal', 'seboruco', 'torbes', 'uribante',
    'san judas tadeo', 'bocono', 'candelaria', 'carache', 'escuque', 'jose felipe marquez canizalez',
    'juan vicente campos elias', 'la ceiba', 'monte carmelo', 'motatan', 'pampan', 'pampanito',
    'rafael rangel', 'san rafael de carvajal', 'trujillo', 'valera', 'vargas', 'aristides bastidas',
    'bruzual', 'cocorote', 'jose antonio paez', 'la trinidad', 'manuel monge', 'nirgua', 'pena', 'san felipe',
    'urachiche', 'jose joaquin veroes', 'almirante padilla', 'baralt', 'cabimas', 'catatumbo', 'colon',
    'francisco javier pulgar', 'jesus enrique losada', 'jesus maria semprun', 'la canada de urdaneta',
    'lagunillas', 'machiques de perija', 'mara', 'maracaibo', 'rosario de perija', 'santa rita',
    'valmore rodriguez',
]

PARROQUIAS = [
    'huachamacare acanana', 'marawaka toky shamanana', 'mavaka mavaka', 'sierra parima parimabe',
    'ucata laja lisa', 'yapacana macuruco', 'caname guarinuma', 'fernando giron tovar', 'luis alberto gomez',
    'pahuena limon de parhuena', 'platanillal platanillal', 'samariapo', 'sipapo', 'munduapo', 'guayapo',
    'alto ventuari', 'medio ventuari', 'bajo ventuari', 'victorino', 'comunidad', 'casiquiare', 'cocuy',
    'san carlos de rio negro', 'solano', 'cachipo', 'aragua de barcelona', 'lecheria', 'el morro',
    'puerto piritu', 'san miguel', 'valle de guanape', 'el chaparro', 'tomas alfaro', 'calatrava', 'chorreron',
    'mamo', 'soledad', 'mapire', 'santa clara', 'san diego de cabrutica', 'uverito', 'zuata', 'puerto la cruz',
    'pozuelos', 'onoto', 'san pablo', 'san mateo', 'el carito', 'santa ines', 'la romerena', 'atapirire',
    'boca del pao', 'el pao', 'pariaguan', 'cantaura', 'santa rosa', 'urica', 'boca de uchire', 'boca de chavez',
    'pueblo nuevo', 'bergantin', 'caigua', 'el carmen', 'el pilar', 'naricual', 'san crsitobal', 'edmundo barrios',
    'miguel otero silva', 'apurito', 'el yagual', 'guachara', 'mucuritas', 'queseras del medio', 'mantecal',
    'quintero', 'rincon hondo', 'san vicente', 'guasdualito', 'aramendi', 'el amparo', 'san camilo',
    'san juan de payara', 'codazzi', 'cunaviche', 'elorza', 'el recreo', 'penalver', 'san rafael de atamaica',
    'pedro jose ovalles', 'joaquin crespo', 'jose casanova godoy', 'madre maria de san jose', 'los tacarigua',
    'las delicias', 'choroni', 'carmen de cura', 'mosenor feliciano gonzalez', 'santa cruz', 'castor nieves rios',
    'las guacamayas', 'pao de zarate', 'palo negro', 'san martin de porres', 'el limon', 'cana de azucar',
    'ocumare de la costa', 'guiripa', 'ollas de caramacate', 'valle morin', 'san sebastian', 'turmero',
    'arevalo aponte', 'chuao', 'saman de guere', 'alfredo pacheco miranda', 'tiara', 'cagua', 'bella vista',
    'las penitas', 'san francisco de cara', 'taguay', 'magdaleno', 'san francisco de asis',
    'valles de tucutunemo', 'augusto mijares', 'sabaneta', 'juan antonio rodriguez dominguez', 'el canton',
    'santa cruz de guacas', 'puerto vivas', 'ticoporo', 'nicolas pulido', 'guadarrama', 'la union',
    'san antonio', 'alberto arvelo larriva', 'san silvestre', 'santa lucia', 'torumos', 'romulo betancourt',
    'corazon de jesus', 'ramon ignacio mendez', 'alto barinas', 'manuel palacio fajardo', 'dominga ortiz de paez',
    'barinitas', 'altamira de caceres', 'calderas', 'barrancas', 'mazparrito', 'pedro briceno mendez',
    'jose ignacio del pumar', 'guasimitos', 'el real', 'la luz', 'ciudad bolivia', 'jose ignacio briceno',
    'dolores', 'palacio fajardo', 'ciudad de nutrias', 'el regalo', 'puerto nutrias', 'santa catalina',
    'cachamay', 'chirica', 'dalla costa', 'once de abril', 'unare', 'universidad', 'vista al sol', 'pozo verde',
    'yocoima', '5 de julio', 'altagracia', 'ascension farreras', 'guaniamo', 'la urbana', 'pijiguaos',
    'ikabaru', 'catedral', 'orinoco', 'marhuanta', 'agua salada', 'vista hermosa', 'la sabanita', 'panapana',
    'pedro cova', 'raul leoni', 'barceloneta', 'salom', 'san isidro', 'aripao', 'guarataro', 'las majadas',
    'moitaco', 'rio grande', 'canoabo', 'guigue', 'carabobo', 'tacarigua', 'mariara', 'aguas calientes',
    'ciudad alianza', 'yagua', 'moron', 'tocuyito', 'bartolome salom', 'fraternidad', 'goaigoaza',
    'juan jose flores', 'borburata', 'patanemo', 'miguel pena', 'san blas', 'san jose', 'negro primero',
    'cojedes', 'juan de mata suarez', 'el baul', 'la aguadita', 'macapo', 'libertad de cojedes',
    'san carlos de austria', 'juan angel bravo', 'manuel manrique', 'general en jefe jose laurencio silva',
    'curiapo', 'almirante luis brion', 'francisco aniceto lugo', 'manuel renaud', 'padre barral',
    'santos de abelgas', 'imataca', 'cinco de julio', 'juan bautista arismendi', 'manuel piar',
    'luis beltran prieto figueroa', 'jose vidal marcano', 'juan millan', 'leonardo ruiz pineda',
    'mariscal antonio jose de sucre', 'monsenor argimiro garcia', 'san rafael', 'virgen del valle',
    'clarines', 'guanape', 'sabana de uchire', 'capadare', 'la pastora', 'san juan de los cayos', 'aracua',
    'la pena', 'san luis', 'bariro', 'borojo', 'capatarida', 'guajiro', 'seque', 'zazarida', 'valle de eroa',
    'urbana punta cardon', 'la vela de coro', 'acurigua', 'guaibacoa', 'las calderas', 'macoruca',
    'agua clara', 'avaria', 'pedregal', 'piedra grande', 'purureche', 'adaure', 'adicora', 'baraived',
    'buena vista', 'jadacaquiva', 'el vinculo', 'el hato', 'moruy', 'agua larga', 'el pauji', 'maparari',
    'agua linda', 'araurima', 'tucacas', 'boca de aroa', 'judibana', 'mene de mauroa', 'san felix', 'casigua',
    'guzman guillermo', 'mitare', 'rio seco', 'san gabriel', 'boca del tocuyo', 'chichiriviche',
    'tocuyo de la costa', 'cabure', 'curimagua', 'san jose de la costa', 'pecaya', 'el charal',
    'las vegas del tuy', 'santa cruz de bucaral', 'puerto cumarebo', 'la cienaga', 'la soledad',
    'pueblo cumarebo', 'churuguara', 'puerto miranda', 'tucupido', 'san rafael de laya',
    'altagracia de orituco', 'san rafael de orituco', 'san francisco javier de lezama',
    'paso real de macaira', 'carlos soublette', 'san francisco de macaira', 'libertad de orituco',
    'cantaclaro', 'san juan de los morros', 'parapara', 'el sombrero', 'cabruta', 'santa rita de manapire',
    'valle de la pascua', 'espino', 'san jose de unare', 'zaraza', 'san jose de tiznados',
    'san francisco de tiznados', 'san lorenzo de tiznados', 'ortiz', 'guayabal', 'cazorla', 'uveral',
    'altamira', 'el calvario', 'el rastro', 'guardatinajas', 'capital urbana calabozo',
    'quebrada honda de guache', 'pio tamayo', 'yacambu', 'freitez', 'jose maria blanco', 'concepcion',
    'el cuji', 'juan de villegas', 'tamaca', 'aguedo felipe alvarado', 'juarez', 'juan bautista rodriguez',
    'cuara', 'diego de lozada', 'paraiso de san jose', 'tintorero', 'jose bernardo dorante',
    'coronel mariano peraza ', 'guarico', 'hilario luna y luna', 'humocaro alto', 'humocaro bajo',
    'la candelaria', 'cabudare', 'jose gregorio bastidas', 'agua viva', 'sarare', 'buria',
    'gustavo vegas leon', 'trinidad samuel', 'camacaro', 'castaneda', 'cecilio zubillaga', 'chiquinquira',
    'el blanco', 'espinoza de los monteros', 'lara', 'manuel morillo', 'montana verde', 'montes de oca',
    'heriberto arroyo', 'reyes vargas', 'siquisique', 'moroturo', 'xaguas', 'presidente betancourt',
    'presidente paez', 'presidente romulo gallegos', 'gabriel picon gonzalez', 'hector amable mora',
    'jose nucete sardi', 'pulido mendez', 'la azulita', 'santa cruz de mora', 'mesa bolivar',
    'mesa de las palmas', 'canagua', 'capuri', 'chacanta', 'el molino', 'guaimaral', 'mucutuy',
    'mucuchachi', 'fernandez pena', 'matriz', 'acequias', 'jaji', 'la mesa', 'san jose del sur', 'tucani',
    'florencio ramirez', 'santo domingo', 'las piedras', 'mesa de quintero', 'arapuey', 'palmira',
    'san cristobal de torondoy', 'torondoy', 'antonio spinetti dini', 'arias', 'caracciolo parra perez',
    'domingo pena', 'el llano', 'gonzalo picon febres', 'jacinto plaza', 'juan rodriguez suarez',
    'lasso de la vega', 'mariano picon salas', 'milla', 'osuna rodriguez', 'sagrario', 'los nevados',
    'la venta', 'pinango', 'timotes', 'eloy paredes', 'san rafael de alcazar', 'santa elena de arenales',
    'santa maria de caparo', 'cacute', 'la toma', 'mucuchies', 'mucuruba', 'geronimo maldonado',
    'bailadores', 'tabay', 'chiguara', 'estanquez', 'la trampa', 'pueblo nuevo del sur', 'san juan',
    'maria de la concepcion palacios blanco', 'nueva bolivia', 'santa apolonia', 'cano el tigre',
    'araguita', 'arevalo gonzalez', 'capaya', 'caucagua', 'panaquire', 'ribas', 'el cafe', 'marizapa',
    'cumbo', 'san jose de barlovento', 'el cafetal', 'las minas', 'nuestra senora del rosario',
    'higuerote', 'curiepe', 'tacarigua de brion', 'mamporal', 'charallave', 'las brisas',
    'altagracia de la montana', 'cecilio acosta', 'los teques', 'el jarillo', 'san pedro', 'tacata',
    'paracotos', 'cartanal', 'santa teresa del tuy', 'la democracia', 'ocumare del tuy',
    'san antonio de los altos', 'rio chico', 'el guapo', 'tacarigua de la laguna', 'paparo',
    'san fernando del guapo', 'santa lucia del tuy', 'cupira', 'machurucuto', 'guarenas',
    'san antonio de yare', 'san francisco de yare', 'leoncio martinez', 'petare', 'caucaguita',
    'filas de mariche', 'la dolorita', 'cua', 'nueva cua', 'guatire', 'san antonio de maturin',
    'san francisco de maturin', 'caripito', 'el guacharo', 'la guanota', 'sabana de piedra',
    'san agustin', 'teresen', 'areo', 'capital cedeno', 'san felix de cantalicio', 'viento fresco',
    'el tejero', 'punta de mata', 'las alhuacas', 'tabasca', 'temblador', 'alto de los godos',
    'boqueron', 'las cocuizas', 'la cruz', 'san simon', 'el corozo', 'el furrial', 'jusepin',
    'la pica', 'aparicio', 'aragua de maturin', 'chaguamal', 'el pinto', 'guanaguana', 'la toscana',
    'taguaya', 'quiriquire', 'los barrancos de fajardo', 'francisco fajardo', 'guevara', 'matasiete',
    'aguirre', 'adrian', 'juan griego', 'yaguaraparo', 'porlamar', 'san francisco de macanao',
    'boca de rio', 'los baleales', 'vicente fuentes', 'san juan bautista', 'zabala', 'capital araure',
    'rio acarigua', 'capital esteller', 'san jose de la montana', 'san juan de guanaguanare',
    'virgen de la coromoto', 'trinidad de la capilla', 'divina pastora', 'pena blanca',
    'capital ospino', 'aparicion', 'la estacion', 'payara', 'pimpinela', 'ramon peraza',
    'cano delgadito', 'san genaro de boconoito', 'antolin tovar', 'santa fe', 'thermo morles',
    'san rafael de palo alzado', 'uvencio antonio velasquez', 'san jose de saguaz', 'villa rosa',
    'canelones', 'san isidro labrador', 'san jose de aerocuar', 'tavera acosta', 'rio caribe',
    'el morro de puerto santo', 'puerto santo', 'san juan de las galdonas', 'el rincon',
    'general francisco antonio vaquez', 'guaraunos', 'tunapuicito', 'santa teresa', 'maracapana',
    'el paujil', 'chacopata', 'manicuare', 'tunapuy', 'irapa', 'campo claro', 'maraval',
    'san antonio de irapa', 'soro', 'cumanacoa', 'arenas', 'cogollar', 'san lorenzo', 'villa frontado',
    'catuaro', 'rendon', 'san cruz', 'santa maria', 'valentin valiente', 'gran mariscal', 'cristobal colon',
    'bideau', 'punta de piedras', 'guiria', 'rivas berti', 'san pedro del rio', 'palotal',
    'general juan vicente gomez', 'isaias medina angarita', 'amenodoro angel lamus', 'la florida',
    'boca de grita', 'roman cardenas', 'emilio constantino guerrero', 'monsenor miguel antonio salas',
    'la petrolea', 'quinimari', 'bramon', 'cipriano castro', 'manuel felipe rugeles', 'doradas',
    'emeterio ochoa', 'san joaquin de navay', 'constitucion', 'la palmita', 'nueva arcadia', 'delicias',
    'hernandez', 'la concordia', 'pedro maria morantes', 'dr. francisco romero lobo',
    'eleazar lopez contreras', 'juan pablo penalosa', 'potosi', 'araguaney', 'el jaguito',
    'la esperanza', 'santa isabel', 'mosquey', 'burbusay', 'general ribas', 'guaramacal',
    'vega de guaramacal', 'monsenor jauregui', 'sabana grande', 'cheregue', 'granados',
    'arnoldo gabaldon', 'carrillo', 'cegarra', 'chejende', 'manuel salvador ulloa', 'la concepcion',
    'cuicas', 'panamericana', 'sabana libre', 'los caprichos', 'el progreso', 'tres de febrero',
    'el dividive', 'agua santa', 'agua caliente', 'el cenizo', 'valerita', 'santa maria del horcon',
    'el bano', 'jalisco', 'flor de patria', 'la paz', 'pampanito ii', 'betijoque',
    'jose gregorio hernandez', 'la pueblita', 'los cedros', 'carvajal', 'campo alegre',
    'antonio nicolas briceno', 'jose leonardo suarez', 'sabana de mendoza', 'el paraiso',
    'andres linares', 'cristobal mendoza', 'cruz carrillo', 'monsenor carrillo', 'tres esquinas',
    'cabimbu', 'jajo', 'la mesa de esnujaque', 'santiago', 'tuname', 'la quebrada',
    'juan ignacio montilla', 'la beatriz', 'la puerta', 'mendoza del valle de momboy', 'mercedes diaz',
    'caraballeda', 'carayaca', 'caruao chuspa', 'catia la mar', 'el junko', 'la guaira', 'macuto',
    'maiquetia', 'naiguata', 'urimare', 'chivacoa', 'temerla', 'san andres', 'yaritagua', 'san javier',
    'albarico', 'el guayabo', 'farriar', 'isla de toas', 'monagas', 'san timoteo', 'general urdaneta',
    'marcelino briceno', 'manuel guanipa matos', 'ambrosio', 'carmen herrera', 'la rosa',
    'german rios linares', 'san benito', 'jorge hernandez', 'punta gorda', 'aristides calvani',
    'encontrados', 'udon perez', 'moralito', 'san carlos del zulia', 'santa cruz del zulia',
    'urribarri', 'carlos quevedo', 'guamo-gavilanes', 'mariano parra leon', 'jose ramon yepez',
    'bari', 'el carmelo', 'potreritos', 'alonso de ojeda', 'venezuela', 'campo lara',
    'bartolome de las casas', 'san jose de perija', 'la sierrita', 'las parcelas', 'luis de vicente',
    'monsenor marcos sergio godoy', 'tamare', 'antonio borjas romero', 'cacique mara',
    'carracciolo parra perez', 'cristo de aranza', 'coquivacoa', 'francisco eugenio bustamante',
    'idelfonzo vasquez', 'juana de avila', 'luis hurtado higuera', 'manuel dagnino',
    'olegario villalobos', 'venancio pulgar', 'faria', 'ana maria campos', 'donaldo garcia',
    'el rosario', 'sixto zambrano', 'el bajo', 'domitila flores', 'francisco ochoa', 'los cortijos',
    'marcial hernandez', 'el mene', 'pedro lucas urribarri', 'jose cenobio urribarri',
    'rafael maria baralt', 'bobures', 'gibraltar', 'heras', 'monsenor arturo alvarez', 'el batey',
    'la victoria', 'raul cuenca', 'sinamaica', 'alta guajira', 'elias sanchez rubio', 'guajira',
    'antimano', 'caricuao', 'coche', 'el junquito', 'el valle', 'la vega', 'macarao',
    'san bernardino', '23 de enero',
]

CIUDADES = [
    'el cafetal', 'puerto ayacucho', 'atabapo', 'la esmeralda', 'parhueña', 'isla raton', 'barcelona',
    'lecheria', 'clarines', 'pariapán', 'biruaca', 'maracay', 'colonia tovar', 'ocumare', 'turiamo',
    'socopo', 'sabaneta', 'barinitas', 'guayana', 'puerto ordaz', 'ciudad bolivar', 'upata', 'tumeremo',
    'el callao', 'guacipati', ' uairen', 'caicara', 'maripa', 'las claritas', ' moron ', 'bejumá',
    'sierra imataca', 'piacoa', 'sacupana', 'capure', 'araguaimujo', 'macareo', 'mirimire', 'adicora',
    'valle la pascua', 'cubiro', ' osma', ' chuspa', 'carmen de uria', 'el vigia', ' tabay', 'higuerote',
    'caucagua', 'capayacuar', 'macanao', 'acarigua', 'cariaco', 'yaguaraparo', 'tunapuy', ' irapa',
    ' araya', 'capacho', 'bocono', ' monay', 'ciudad ojeda', 'machiques',
]

VENEZUELA = ESTADOS + MUNICIPIOS + PARROQUIAS + CIUDADES + ['venezuela', 'venezolan', 'vzla']
VZLA_PATTERN = r'|'.join(VENEZUELA)

VALORES_AMERICANOS = [v for lista in AMERICANOS.values() for v in lista]
AMER_PATTERN = OTROS_LUGARES_NO_VZLA + '|' + '|'.join(VALORES_AMERICANOS) + '|' + EXTRA_RUIDO

SIGNOS_PATTERN = r'[@#\-_"!\¡\?\(\)\/\|*]'

REDES_SOCIALES = ['facebook', 'instagram', 'x.com', 'tiktok', 'threads', 'youtube']

# --------------------------------------------------------------------------
# Blacklist y equivalencias para limpieza de entidades NER (lugares)
# --------------------------------------------------------------------------
BLACKLIST_LUGARES = [
    'nan', 'venezuela', 'vzla', 'posts', 'ubicacion', 'siguenos', 'descubre', 'encuentra', 'visitanos',
    'hospedaje', 'reserva', 'reservas', 'tripadvisor', 'kayak', 'urb', 'edo', '☎', '🈴', 'yeiber', 'av',
    'aqui', 'airbnb', 'book homes', 'ensueno', 'rios', 'town house', 'ninas', 'jeep', 'cabana',
    'rio smart', 'camaras', 'alli', 'armonia', 'zelle', 'audubon de', 'audubon de venezuela', 'closet',
    'travesia', 'hotel', 'republica bolivariana de', 'republica bolivariana de venezuela', 'asiaafrica',
    'en estados unidos', 'munecas', 'golfo de', '!unete', 'la av', 'gavidia', 'jhonathan miranda', 'paseo',
    'avion', 'lian', 'tealca', 'Meridalosandesverdegreen', 'metro chorrillos', 'lavanderia',
    'copa venezuela bahia', 'de colombia', 'playa de', 'edo.', 'pais', 'sabado', '1 vzla', 'youtube',
    'ovr7', 'miss', 'ninos', 'caracas maracay', 'mister', 'tours', '6:30 am', 'alla', 'montanabeach',
    'meridalosandesverdegreen', 'parrillera', 'merida c.a', 'carmen', 'bano', 'unete', 'mar!',
    'primaderm', 'senora', 'venaventours', 'urb.', 'soygruporoelroel', 'millas', '!reserva',
    'maracay valencia', 'travel', 'turismovenezuela', 'luchaalmada15 leticiagomezve', 'conocevenezuela',
    'johancolmenaresc', 'venezolano', 'carabobo aragua', 'caracas aragua', '0424 3109693 barquisimeto',
    'kayakvenezuela', 'leticiagomezve', 'on july', 'minturvzla', 'av r 8', 'Lian', 'parapentemeridacom',
    'turis', 'caracas valencia', 'adventures', 'santorinibdu', 'enamorate siguenos', 'tepuy travel',
    'minimalfurgo', 'meridaven', 'tuscany', 'via guarico sector', 'cagua maracay valencia',
    'venezuela unete', 'town house urbanizacion', 'aragua carabobo', 'santiago', 'relax',
    'merida caracas', 'aguila', 'aguilas', 'cascadadelvino', 'caracas valencia travel', 'roque',
    'maracay caracas', 'laromerena on instagram', 'expo', 'venezuela motoadventurecamp',
    'missvenezuela', 'lena', 'guadalupe', 'santa rita montereal hotel', 'cienagamia', 'fullday',
    'mara', 'sierra de santiago nl',
]

EQUIVALENCIAS_LUGARES = {
    'parque n morrocoy': 'morrocoy', 'parque nacional morrocoy': 'morrocoy', 'parque nacional canaima': 'canaima',
    'mcbo': 'maracaibo', 'isla de margarita': 'margarita', 'gran caracas': 'caracas', 'andes': 'los andes',
    'manantial valencia': 'valencia', 'ordaz': 'pto. Ordaz', 'parque nacional el avila': 'el avila',
    'avila': 'el avila', 'parque nacional mochima': 'mochima', 'parque nacional sierra de la culata': 'sierra Nevada',
    'ee.uu': 'eeuu', 'ee.uu.': 'eeuu', 'parque nacional sierra nevada': 'sierra nevada', 'caracas-vzla': 'caracas',
    'isla margarita': 'margarita', 'puerto cruz': 'pto. la cruz', 'estados unidos': 'eeuu', 'montanas': 'montaña',
    'merida!!': 'merida', 'cienaga': 'la cienaga', 'bahia de pampatar #escamas #bodegon': 'bahia de pampatar',
    'merida and more': 'merida', 'losroques': 'los roques', 'archipielago de los roques': 'los roques',
    'Aragua turismoenaraguave on instagram': 'aragua', 'venezuela caracas': 'caracas',
    'valencia carabobo': 'valencia', 'san cristobal tachira': 'tachira', 'realtre caracas': 'caracas',
    'venezuela merida': 'merida', 'cienaga aragua': 'la cienaga', 'carabobo valencia': 'valencia',
    'aragua maracay': 'maracay', 'san juan de los morro': 'san juan de los morros',
    'playasdevenezuela falcon': 'falcon', 'anzoategui venezuela descripcion': 'anzoategui',
    'team caracas': 'caracas', 'nirgua edo yaracuy': 'nirgua', 'merida merida': 'merida',
    'maracay aragua': 'maracay', 'merida venezuela on instagram': 'merida', 'hotelbroadway': 'hotel broadway',
    'chichiriviche falcon': 'chichiriviche', 'lacienaga': 'la cienaga', 'chichiriviche edo falcon': 'chichiriviche',
    'archipielago de losroques': 'los roques', 'de valencia': 'valencia',
    'aragua turismoenaraguave on instagram': 'aragua', 'coro falcon': 'coro',
    'parque nacional medanos de coro': 'medanos de coro', 'san felipe yaracuy': 'san felipe',
    'pico avila': 'el avila', 'bahia de pampatar escamas bodegon restaurant': 'bahia de pampatar',
    'ojeda': 'ciudad ojeda', 'tinaquillo edo cojedes': 'tinaquillo', 'atvutvvalera atv barinas': 'barinas',
    'orinoco': 'rio orinoco',
}